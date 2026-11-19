'use strict';
let fourVoiceData, previewPending=false;
const categoryNames={male:'Adult Male',female:'Adult Female',child_male:'Child Male',child_female:'Child Female'};
async function loadReferenceSetup(){
  fourVoiceData=await api('/api/default-voices');const root=$('four-voice-selectors');root.replaceChildren();
  const mode=select([{value:'evaluation',label:'Evaluation · permissions unverified'},{value:'production',label:'Production · licensed references'}],'Voice usage mode');mode.firstChild.remove();mode.id='voice-usage-mode';mode.value=fourVoiceData.mode;addField(root,'Usage',mode);
  for(const [category,name] of Object.entries(categoryNames)){
    const row=el('section','voice-row'),menu=select(fourVoiceData.references.map(r=>({value:r.id,label:r.label})),name);menu.dataset.voiceCategory=category;menu.id='base-voice-'+category;menu.value=fourVoiceData.base_voices[category]?.reference_id||'';addField(row,name,menu);
    row.append(button('Listen',async()=>{if(!menu.value)throw new Error('Select a recording first.');$('voice-audition').src='/api/default-voices/references/'+menu.value+'/audio';$('voice-audition').hidden=false;$('voice-audition-status').textContent=name+' · selected recording';await $('voice-audition').play();}));
    row.append(button('Bengali preview',()=>previewFour(category,menu.value)));
    const upload=el('details');upload.append(el('summary','','Licensed replacement'));const file=el('input');file.type='file';file.accept='.wav,audio/wav';file.setAttribute('aria-label','Upload '+name);upload.append(file,button('Upload WAV',async()=>{
      const selected=file.files[0];if(!selected||selected.size>10000000)throw new Error('Choose a PCM WAV smaller than 10 MB.');
      const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(selected);});
      const result=await api('/api/default-voices/references',{wav_base64:encoded,label:selected.name,authorization:$('four-voice-permission').value,consent:$('four-voice-consent').checked});
      const previous=Object.fromEntries([...root.querySelectorAll('[data-voice-category]')].map(m=>[m.dataset.voiceCategory,m.value]));const usage=mode.value;previous[category]=result.reference_id;
      await loadReferenceSetup();for(const [key,value] of Object.entries(previous))$('base-voice-'+key).value=value;$('voice-usage-mode').value=usage;$('four-voice-message').textContent='Recording stored. Save Four Voices to apply the selection.';
    }));row.append(upload);root.append(row);
  }
}
async function previewFour(category,reference){
  if(previewPending)throw new Error('Wait for the current preview.');previewPending=true;
  try{
    let job=await api('/api/default-voices/preview',{category,reference_id:reference||null});const deadline=Date.now()+25*60*1000;
    $('voice-audition-status').textContent='Waiting for local Bengali synthesis…';
    while(['queued','running'].includes(job.status)&&Date.now()<deadline){await new Promise(r=>setTimeout(r,1000));job=await api('/api/default-voices/previews/'+job.id);$('voice-audition-status').textContent=job.status==='running'?'Generating Bengali speech…':'Waiting for the current job…';}
    if(job.status!=='completed')throw new Error('Preview did not finish. See the console log.');
    $('voice-audition').src=job.audio_url;$('voice-audition').hidden=false;$('voice-audition-status').textContent=categoryNames[category]+' · generated Bengali preview';
  }finally{previewPending=false;}
}
function aiConsentVisibility(){$('ai-consent-label').hidden=$('setting-understanding').value!=='assisted';}
$('setting-understanding').onchange=aiConsentVisibility;
$('settings-toggle').onclick=()=>guard(async()=>{
  const data=await api('/api/preferences');$('setting-duration').value=data.format;$('setting-music').checked=data.music;$('setting-understanding').value=data.interpretation_mode;$('setting-understanding').querySelector('[value=assisted]').disabled=!data.semantic_ai_configured;$('setting-ai-consent').checked=data.semantic_ai_approved;aiConsentVisibility();
  await loadReferenceSetup();const storage=await api('/api/storage/disposable');$('storage-status').textContent=`${storage.files} files · ${(storage.bytes/1048576).toFixed(1)} MB`;$('settings-message').textContent='';$('settings-dialog').showModal();
});
$('settings-close').onclick=()=>$('settings-dialog').close();
$('settings-dialog').addEventListener('close',()=>{$('voice-audition').pause();});
$('settings-form').onsubmit=event=>{event.preventDefault();guard(async()=>{await api('/api/preferences',{format:$('setting-duration').value,voice_preference:'chatterbox_bangla',music:$('setting-music').checked,interpretation_mode:$('setting-understanding').value,semantic_ai_approved:$('setting-understanding').value==='assisted'&&$('setting-ai-consent').checked},'PUT');$('settings-message').textContent='Preferences saved for future cartoons.';});};
$('four-voice-save').onclick=()=>guard(async()=>{const base_voices=Object.fromEntries([...$('four-voice-selectors').querySelectorAll('[data-voice-category]')].map(m=>[m.dataset.voiceCategory,m.value]));await api('/api/default-voices',{base_voices,mode:$('voice-usage-mode').value},'PUT');await loadReferenceSetup();$('four-voice-message').textContent='Four category voices saved permanently.';});
$('storage-cleanup').onclick=()=>guard(async()=>{const result=await api('/api/storage/disposable',{});$('storage-status').textContent=`Removed ${result.removed_files} files · ${(result.removed_bytes/1048576).toFixed(1)} MB`;});
