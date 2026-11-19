// Optional, permanent choices; no fictional provider voices or age certifications.
const voiceStudio=node('section','panel');voiceStudio.id='voice-studio-panel';
voiceStudio.append(node('small','','VOICE STUDIO'),node('h2','','Saved character voices'));
const voiceTabs=node('div','voice-tabs');voiceTabs.setAttribute('role','tablist');voiceTabs.setAttribute('aria-label','Voice categories');
const categoryLabels={male:'Male',female:'Female',child_male:'Child Male',child_female:'Child Female'};
let studioCategory='male',studioData=null,studioVoices=[],studioProvider='vits';
const studioAuditions=new Map();
for(const [key,label] of Object.entries(categoryLabels)){const button=node('button','',label);button.setAttribute('role','tab');button.dataset.category=key;button.onclick=()=>guarded(async()=>{studioCategory=key;await showVoiceCategory();});voiceTabs.append(button);}
const providerChoice=selectOptions(['elevenlabs','azure','vits'],'vits','Voice Studio provider');
for(const option of providerChoice.options)option.textContent={elevenlabs:'ElevenLabs',azure:'Azure Speech',vits:'Offline VITS'}[option.value];
const voiceSearch=node('input');voiceSearch.type='search';voiceSearch.placeholder='Search available voices';voiceSearch.setAttribute('aria-label','Search available voices');
const voiceNotice=node('p','hint'),voiceCards=node('div','voice-cards');
const bengaliSample=node('input');bengaliSample.value='তুমি কেমন আছ? চলো, আমরা একসঙ্গে গল্পটা শুরু করি।';bengaliSample.setAttribute('aria-label','Bengali audition text');
voiceStudio.append(voiceTabs,providerChoice,voiceSearch,node('label','','Bengali audition sample'),bengaliSample,voiceNotice,voiceCards);document.querySelector('main').append(voiceStudio);

async function auditionVoice(voice,card,model){
  const session=await request('/api/production',{story:'বর্ণনাকারী: '+bengaliSample.value,renderer:'godot',
    scenes:[{scene_id:'scene_001',start_segment:0,end_segment:1,background_id:'mango_orchard_day',location_text:'Voice audition'}]});
  const line=session.segments[0],base=`/api/production/${session.session_id}/segments/${line.id}`;
  await request(base+'/voice',{provider:studioProvider,voice_id:voice.voice_id,model,language:'bn'},'PUT');
  const estimate=await request(base+'/estimate');let approval={};
  if(estimate.paid){if(!confirm(`${estimate.provider} · ${estimate.characters} characters. Account pricing applies.\n${bengaliSample.value}\n\nGenerate this paid audition?`))return;approval={paid_approved:true,approval_token:estimate.approval_token};}
  await request(base+'/takes',approval);const status=node('p','hint','Generating Bengali audition…');card.append(status);
  for(let i=0;i<600;i++){
    const current=await request('/api/production/'+session.session_id);const take=current.segments[0].takes[0];
    if(take.status==='failed')throw new Error(take.error);
    if(take.status==='completed'){const audio=node('audio');audio.controls=true;audio.src=take.audio_url;card.append(audio);status.textContent='Listen before choosing. This is an actual generated Bengali sample.';studioAuditions.set(studioProvider+':'+voice.voice_id,take.audio_url);return;}
    await new Promise(resolve=>setTimeout(resolve,1000));
  }throw new Error('Audition timed out. Check the saved take; it will not be retried automatically.');
}
function showVoiceCards(){
  voiceCards.replaceChildren();const query=voiceSearch.value.toLowerCase();
  for(const voice of studioVoices.filter(v=>[v.name,v.description,...Object.values(v.labels||{})].join(' ').toLowerCase().includes(query))){
    const card=node('article','voice-card');card.append(node('h3','',voice.name),node('p','hint',`${voice.provider} · ${Object.entries(voice.labels||{}).map(([k,v])=>k+': '+v).join(' · ')||'No age/gender metadata supplied'}`));
    if(voice.languages?.length)card.append(node('p','hint',JSON.stringify(voice.languages)));
    if(voice.preview_url?.startsWith('https://')){const audio=node('audio');audio.controls=true;audio.preload='none';audio.src=voice.preview_url;card.append(audio);}
    const model=studioProvider==='elevenlabs'?'eleven_v4':studioProvider==='azure'?'azure-neural':'bangladeshi-vits';
    const preview=node('button','','Generate Bengali sample');preview.onclick=()=>guarded(async()=>{preview.disabled=true;try{await auditionVoice(voice,card,model);}finally{preview.disabled=false;}});card.append(preview);
    const actors=studioData.characters.filter(c=>c.category===studioCategory).map(c=>({voice_id:c.id,name:c.name+(c.voice?' · saved':'')}));
    if(!studioCategory.startsWith('child_'))actors.push({voice_id:'narrator',name:'Narrator (explicit speech only)'});
    const actor=selectOptions(actors,actors[0]?.voice_id,'Assign voice to character');card.append(actor);
    const alternative=node('label','check'),accept=node('input');accept.type='checkbox';alternative.append(accept,document.createTextNode('I listened and accept this voice as an alternative for this category.'));card.append(alternative);
    const assigned=studioData.characters.filter(c=>c.voice?.voice_id===voice.voice_id&&c.voice?.provider===studioProvider).map(c=>c.name);if(assigned.length)card.append(node('p','hint','Assigned: '+assigned.join(', ')));
    const save=node('button','','Save character voice');save.onclick=()=>guarded(async()=>{
      const identity={provider:studioProvider,model,voice_id:voice.voice_id,language:'bn'};
      await request('/api/voice-studio/presets',{category:studioCategory,voice:identity,label:voice.name,bengali_reviewed:accept.checked,accept_alternative:accept.checked});
      const previous=studioData.characters.find(c=>c.id===actor.value)?.voice||studioData.narrator.voice;
      const confirm_change=!!previous&&JSON.stringify(previous)!==JSON.stringify(identity);
      if(confirm_change&&!confirm('Replace this character’s saved voice for future cartoons?'))return;
      await request('/api/voices/assignments/'+actor.value,{voice:identity,confirm_change});studioData=await request('/api/voice-studio');voiceNotice.textContent='Voice saved. Future cartoons reuse this identity. Existing approved takes remain unchanged.';
    });card.append(save);voiceCards.append(card);
  }
  if(!voiceCards.childElementCount)voiceCards.append(node('p','hint','No accessible voices match. No substitute has been assigned.'));
}
async function showVoiceCategory(){
  for(const button of voiceTabs.children)button.setAttribute('aria-selected',String(button.dataset.category===studioCategory));
  studioProvider=providerChoice.value;voiceCards.replaceChildren();
  if(!studioData.providers.find(p=>p.id===studioProvider)?.configured){voiceNotice.textContent='Provider credentials are not configured on this computer. Offline VITS is available. No provider call was made.';return;}
  voiceNotice.textContent=studioCategory.startsWith('child_')?'No voice is certified as a child voice from metadata. Audition and explicitly accept an alternative.':'Choose once; automatic cartoons reuse saved identities. Offline VITS has one shared voice.';
  studioVoices=await voiceCatalog(studioProvider);showVoiceCards();
}
providerChoice.onchange=()=>guarded(showVoiceCategory);voiceSearch.oninput=showVoiceCards;
guarded(async()=>{studioData=await request('/api/voice-studio');providerChoice.value=studioData.providers.find(p=>p.configured)?.id||'vits';await showVoiceCategory();});

const soundStudio=node('section','panel');soundStudio.id='sound-studio-panel';soundStudio.append(node('small','','SOUND STUDIO'),node('h2','','Automatic music & sound'),node('p','hint','Scene mood and location choose original music/ambience. Footsteps follow animation contacts. Music ducks under speech.'));
const levels=node('div','sound-levels');
for(const track of ['dialogue','narration','music','ambience','sfx','action']){const label=node('label','',track),input=node('input');input.type='range';input.min=0;input.max=2;input.step=.05;input.value=project.audio_levels?.[track]??1;input.setAttribute('aria-label',track+' volume');input.oninput=()=>{project.audio_levels={...(project.audio_levels||{}),[track]:Number(input.value)};saveProject();};label.append(input);levels.append(label);}
soundStudio.append(levels);const soundSelect=selectOptions([],null,'Preview registered sound'),soundPreview=node('audio');soundPreview.controls=true;soundPreview.preload='none';soundSelect.onchange=()=>{soundPreview.src='/api/sounds/'+encodeURIComponent(soundSelect.value)+'/audio';};soundStudio.append(soundSelect,soundPreview);document.querySelector('main').append(soundStudio);
guarded(async()=>{const sounds=await request('/api/sounds');for(const sound of sounds){const option=node('option','',sound.id+' · '+sound.license);option.value=sound.id;soundSelect.append(option);}soundSelect.onchange();});
