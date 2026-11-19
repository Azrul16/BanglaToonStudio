'use strict';
const $=id=>document.getElementById(id), cards=new Map(), streams=new Map();
let historyRows=[],historyOffset=0;
const stopped=new Set(['completed','failed','cancelled','needs_input','needs_payment','needs_audio_review','waiting']);
const stageText={planning:'আপনার গল্প পড়ছি…',queued:'কার্টুন তৈরির প্রস্তুতি নিচ্ছি…',preparing_speech:'সংলাপ ও কণ্ঠ প্রস্তুত করছি…',generating_speech:'চরিত্রদের কণ্ঠ তৈরি হচ্ছে…',parsing:'চরিত্র ও দৃশ্য সাজাচ্ছি…',generating_audio:'সংলাপ প্রস্তুত হচ্ছে…',lip_sync:'কথার সঙ্গে মুখের নড়াচড়া মেলাচ্ছি…',rendering:'কার্টুনের দৃশ্য তৈরি হচ্ছে…',encoding:'দৃশ্য ও শব্দ একসঙ্গে সাজাচ্ছি…',validating:'শেষবার ভিডিওটি যাচাই করছি…',completed:'আপনার কার্টুন তৈরি।',cancelled:'কার্টুন তৈরি বন্ধ করা হয়েছে।'};
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function button(text,action,cls=''){const b=el('button',cls,text);b.type='button';b.onclick=()=>guard(action,b);return b;}
async function api(url,body,method='POST'){
  let response;try{response=await fetch(url,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}catch{throw new Error('সংযোগ পাওয়া যাচ্ছে না। গল্পটি রাখা হয়েছে; আবার পাঠাতে পারেন।');}
  let data;try{data=await response.json();}catch{throw new Error('সংযোগ পাওয়া যাচ্ছে না। আবার চেষ্টা করুন।');}
  if(!response.ok){const error=new Error('অনুরোধটি সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।');error.status=response.status;throw error;}
  return data;
}
async function guard(action,b){if(b)b.disabled=true;try{await action();}catch(error){$('connection-message').textContent=error.message;$('connection-message').hidden=false;}finally{if(b)b.disabled=false;controls();}}
function controls(){const busy=[...cards.values()].some(c=>!stopped.has(c.data.status));$('submit').disabled=busy||!$('prompt').value.trim();document.querySelectorAll('.regenerate-button').forEach(b=>b.disabled=busy);}
function timestamp(value){try{return new Intl.DateTimeFormat('bn-BD',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(value));}catch{return '';}}
function select(options,label,placeholder='নির্বাচন করুন'){
  const s=el('select');s.setAttribute('aria-label',label);const empty=el('option','',placeholder);empty.value='';s.append(empty);
  for(const item of options){const option=el('option','',item.label||item.name||item.value);option.value=item.value||item.voice_id;s.append(option);}return s;
}
function addField(parent,label,control){const wrapper=el('label','field-label',label);wrapper.append(control);parent.append(wrapper);return control;}
function closeStream(id){streams.get(id)?.close();streams.delete(id);}
function scrollCard(card){card.root.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});}

function mount(data,focus=false){
  $('welcome').hidden=true;
  let card=cards.get(data.id);
  if(!card){
    const root=el('article','turn');root.dataset.conversationId=data.id;
    const user=el('div','user-message'),text=el('p','prompt-text',data.prompt);user.append(text,el('time','',timestamp(data.created_at)));
    const assistant=el('div','assistant-message'),icon=el('span','assistant-icon','ব');icon.setAttribute('aria-hidden','true');
    const output=el('div','output-card'),status=el('div','status-line');status.setAttribute('role','status');
    const content=el('div','card-content');output.append(status,content);assistant.append(icon,output);root.append(user,assistant);$('messages').append(root);
    card={root,status,content,data,mode:null};cards.set(data.id,card);
  }
  update(card,data);if(focus)scrollCard(card);return card;
}
function update(card,data){
  card.data=data;card.status.replaceChildren();
  if(data.evaluation_only)card.status.append(el('span','quiet','Evaluation only · voice permissions unverified · '));
  const active=!stopped.has(data.status);
  if(active){const spinner=el('span','spinner');spinner.setAttribute('aria-hidden','true');card.status.append(spinner);}
  card.status.append(el('span','',active?(stageText[data.stage]||stageText[data.status]||'কার্টুন তৈরি হচ্ছে…'):(data.message||stageText[data.status]||'একটি বিষয় নিশ্চিত করুন।')));
  const signature=JSON.stringify([data.status==='completed'?'completed':active?'active':data.status,data.clarifications,data.payment,data.revision,data.video_url]);
  if(card.mode!==signature){
    card.mode=signature;card.content.replaceChildren();
    if(active){
      const progress=el('div','progress');progress.setAttribute('role','progressbar');progress.setAttribute('aria-label','Actual rendering progress');progress.append(el('span'));card.content.append(progress,el('p','quiet progress-detail'));
      card.content.append(button('Stop',async()=>{update(card,await api(`/api/conversations/${data.id}/cancel`,{}));watch(card);},'text-button'));
    }else if(data.status==='completed'&&data.video_url){
      const video=el('video');video.controls=true;video.preload='metadata';video.playsInline=true;video.src=data.video_url;video.setAttribute('aria-label','Generated cartoon');
      const info=el('p','video-info',`${Math.floor(data.duration_seconds/60)}:${String(Math.round(data.duration_seconds%60)).padStart(2,'0')} · ${data.width} × ${data.height}${data.processing_seconds?' · Render job '+Math.round(data.processing_seconds)+'s':''}`);
      const links=el('div','result-actions'),download=el('a','button-link primary','Download Video');download.href=data.video_url+'?download=true';download.download='Bangla-cartoon.mp4';links.append(download);if(!data.id.startsWith('legacy-'))links.append(button('Regenerate Video',async()=>{const request_id=crypto.randomUUID().replaceAll('-','');const next=await api(`/api/conversations/${data.id}/regenerate`,{prompt:data.prompt,request_id});const fresh=mount(next,true);watch(fresh);localStorage.setItem('toon-chat-selected-v5',next.id);await loadHistory();},'button-link regenerate-button'));card.content.append(video,info,links);
    }else if(data.status==='needs_audio_review'){
      const review=data.audio_review;card.content.append(el('p','','Listen before rendering. Audio metrics cannot establish Bengali pronunciation.'));
      for(const clip of review.clips){const row=el('details');row.append(el('summary','',clip.speaker+': '+clip.text));const audio=el('audio');audio.controls=true;audio.preload='none';audio.src=clip.audio_url;row.append(audio);for(const warning of clip.checks.warnings)row.append(el('p','quiet',warning));card.content.append(row);}
      const consent=el('input');consent.type='checkbox';const label=el('label','check');label.append(consent,document.createTextNode('I listened to every clip and accept the pronunciation and naturalness.'));card.content.append(label);
      card.content.append(button('Render reviewed speech',async()=>{if(!consent.checked)throw new Error('Listen to the clips and confirm your review first.');update(card,await api(`/api/conversations/${data.id}/approve-audio`,{token:review.token,listened:true}));watch(card);},'primary'));
      card.content.append(button('Edit story',async()=>{$('prompt').value=data.prompt;localStorage.setItem('toon-chat-draft-v5',data.prompt);$('prompt').focus();controls();},'text-button'));
      card.content.append(button('Stop',async()=>{update(card,await api(`/api/conversations/${data.id}/cancel`,{}));},'text-button'));
    }else if(data.status==='needs_input'){renderClarification(card);}
    else if(data.status==='needs_payment'){renderPayment(card);}
    else if(['failed','cancelled','waiting'].includes(data.status)&&!data.id.startsWith('legacy-')){
      card.content.append(button(data.job_id?'Resume unfinished scenes':'আবার চেষ্টা করুন',async()=>{const result=card.data.unsent?await api('/api/conversations',{prompt:card.data.prompt,request_id:card.data.id}):await api(`/api/conversations/${data.id}/retry`,{});localStorage.removeItem('toon-chat-pending-v5');$('connection-message').hidden=true;update(card,result);watch(card);},'button-link'));
    }
    if(['failed','cancelled','needs_input'].includes(data.status))card.content.append(button('Edit story',async()=>{$('prompt').value=data.prompt;localStorage.setItem('toon-chat-draft-v5',data.prompt);$('prompt').focus();controls();},'text-button'));
  }
  if(active){
    const progress=card.content.querySelector('.progress'),detail=card.content.querySelector('.progress-detail');
    if(data.progress!==null&&data.progress!==undefined){progress.hidden=false;progress.setAttribute('aria-valuenow',data.progress);progress.firstChild.style.width=data.progress+'%';detail.textContent=`${data.progress}%${data.scene_total?' · '+data.scene_completed+'/'+data.scene_total+' দৃশ্য সম্পন্ন':''}`;}
    else{progress.hidden=true;detail.textContent=data.speech_total?`${data.speech_completed||0}/${data.speech_total} সংলাপ প্রস্তুত`:'';}
    const last=data.scene_times?.at(-1);if(last)detail.textContent+=` · ${last.scene_id}: ${last.cached?'cached':Number(last.seconds||0).toFixed(1)+'s'}`;
  }else closeStream(data.id);
  controls();
}
function watch(card){
  closeStream(card.data.id);if(stopped.has(card.data.status)||card.data.id.startsWith('legacy-'))return;
  const source=new EventSource(`/api/conversations/${card.data.id}/events`);streams.set(card.data.id,source);
  source.addEventListener('update',event=>{try{update(card,JSON.parse(event.data));if(stopped.has(card.data.status))loadHistory();}catch{source.close();}});
  source.onerror=()=>{
    source.close();streams.delete(card.data.id);if(stopped.has(card.data.status))return;
    setTimeout(()=>guard(async()=>{update(card,await api('/api/conversations/'+card.data.id));$('connection-message').hidden=true;watch(card);}),1800);
  };
}
function renderPayment(card){
  const payment=card.data.payment,box=el('div','clarification');
  box.append(el('p','',`${payment.characters} অক্ষরের paid speech তৈরি হবে। ${payment.estimated_usd===null?'আপনার অ্যাকাউন্টের মূল্য প্রযোজ্য।':'Estimated $'+payment.estimated_usd}`));
  const lines=el('ol','payment-lines');for(const line of payment.lines)lines.append(el('li','',(line.cached?'✓ সংরক্ষিত · ':'')+line.speaker+': '+line.text));
  box.append(lines,button('Approve paid speech',async()=>{update(card,await api(`/api/conversations/${card.data.id}/resolve`,{revision:card.data.revision,paid_approved:true,approval_token:payment.approval_token}));watch(card);},'primary'),button('Cancel',async()=>{update(card,await api(`/api/conversations/${card.data.id}/cancel`,{}));}));card.content.append(box);
}
function renderClarification(card){
  const form=el('form'),readers=[];
  for(const question of card.data.clarifications||[]){
    const box=el('section','clarification');box.dataset.kind=question.kind;box.append(el('p','',question.question));
    if(question.source)box.append(el('p','source-quote',question.source));
    if(['character','background'].includes(question.kind)){
      const choice=addField(box,question.kind==='character'?'চরিত্র':'দৃশ্য',select(question.options,question.kind+' clarification'));choice.required=true;
      readers.push(body=>{body[question.kind==='character'?'character_mappings':'backgrounds'][question.key]=choice.value;});
    }else if(question.kind==='instruction'){
      const type=addField(box,'লাইনটির অর্থ',select(question.options,'Instruction meaning'));type.required=true;
      const actor=addField(box,'চরিত্র',select(question.characters,'Instruction character'));
      const action=addField(box,'কাজ',select(question.actions.map(a=>({value:a,label:({walk:'হাঁটা',run:'দৌড়ানো',talk:'কথা বলা',idle:'শান্ত থাকা',stop:'থামা',turn:'ফিরে তাকানো',fear:'ভয় পাওয়া',wave:'হাত নাড়া',look_around:'চারপাশে তাকানো'})[a]||a.replaceAll('_',' ')})),'Supported action'));
      const camera=addField(box,'ফ্রেম',select(question.shots.map(s=>({value:s,label:s.replaceAll('_',' ')})),'Camera framing'));
      const sound=addField(box,'শব্দ',select([],'Sound cue'));
      const text=el('textarea');text.value=question.text;text.setAttribute('aria-label','Clarified line text');box.append(text);
      function fields(){actor.parentElement.hidden=!['dialogue','action'].includes(type.value);actor.required=['dialogue','action'].includes(type.value);action.parentElement.hidden=type.value!=='action';action.required=type.value==='action';camera.parentElement.hidden=type.value!=='camera';sound.parentElement.hidden=type.value!=='sound_effect';camera.required=type.value==='camera';sound.required=type.value==='sound_effect';}
      type.onchange=fields;fields();
      guard(async()=>{for(const item of await api('/api/sounds')){const option=el('option','',item.name);option.value=item.id;sound.append(option);}});
      readers.push(body=>{body.corrections[question.key]={source_text:question.source_text,type:type.value,text:text.value,
        speaker_label:type.value==='dialogue'?actor.value:null,character_id:type.value==='action'?actor.value:null,
        action:type.value==='action'?action.value:null,camera_action:type.value==='camera'?camera.value:null,sound_id:type.value==='sound_effect'?sound.value:null};});
    }else if(['reference','category_reference'].includes(question.kind)){box.append(button('Configure Four Voices',()=>{ $('settings-toggle').click(); }));}else if(question.kind==='voice'){
      const provider=addField(box,'কণ্ঠের উৎস',select(question.providers,'Voice source'));
      const voice=addField(box,'কণ্ঠ',select([],'Available voice'));provider.required=true;voice.required=true;
      const audio=el('audio');audio.controls=true;audio.preload='none';audio.hidden=true;box.append(audio);
      let rows=[];
      async function catalog(){voice.replaceChildren();const blank=el('option','','একটি উপলব্ধ কণ্ঠ নির্বাচন করুন');blank.value='';voice.append(blank);if(!provider.value)return;rows=await api('/api/voices/'+provider.value+'/catalog');for(const row of rows){const option=el('option','',row.name);option.value=row.voice_id;voice.append(option);}}
      provider.onchange=()=>guard(catalog);voice.onchange=()=>{const selected=rows.find(v=>v.voice_id===voice.value);audio.hidden=!selected?.preview_url;if(selected?.preview_url)audio.src=selected.preview_url;};
      box.append(button('বাংলা নমুনা শুনুন',async()=>{if(!provider.value||!voice.value)throw new Error('আগে একটি উপলব্ধ কণ্ঠ নির্বাচন করুন।');await audition(provider.value,voice.value,box,audio);}));
      const alternative=el('label','check'),accept=el('input');accept.type='checkbox';alternative.append(accept,document.createTextNode('শুনে এই বিকল্প কণ্ঠটি মেনে নিচ্ছি; ভবিষ্যৎ কার্টুনেও ব্যবহার করুন।'));box.append(alternative);
      if(question.category.startsWith('child_')){accept.required=true;box.append(el('p','quiet','বয়সের লেবেল দিয়ে শিশু-কণ্ঠের মান নিশ্চিত করা যায় না। Offline voice সবার জন্য একই।'));}
      readers.push(body=>{body.voices.push({speaker_id:question.key,voice:{provider:provider.value,voice_id:voice.value,language:'bn',model:provider.value==='elevenlabs'?'eleven_v4':provider.value==='azure'?'azure-neural':'bangladeshi-vits'},accept_alternative:accept.checked});});
    }
    form.append(box);
  }
  if((card.data.clarifications||[]).some(q=>q.kind!=='notice')){const submit=el('button','primary','Continue cartoon');submit.type='submit';form.append(submit,button('Cancel',async()=>{update(card,await api(`/api/conversations/${card.data.id}/cancel`,{}));}));}
  form.onsubmit=event=>{event.preventDefault();guard(async()=>{const body={revision:card.data.revision,character_mappings:{},backgrounds:{},corrections:{},voices:[]};for(const read of readers)read(body);update(card,await api(`/api/conversations/${card.data.id}/resolve`,body));watch(card);},form.querySelector('button[type=submit]'));};
  card.content.append(form);
}
async function audition(provider,voiceId,box,audio){
  const backgrounds=await api('/api/backgrounds'),background=backgrounds.find(b=>b.status==='ready');if(!background)throw new Error('নমুনা তৈরি করা যাচ্ছে না।');
  const session=await api('/api/production',{story:'বর্ণনাকারী: তুমি কেমন আছ? চলো আমরা একসঙ্গে গল্প শুরু করি।',renderer:'pillow',scenes:[{scene_id:'scene_001',start_segment:0,end_segment:1,background_id:background.id,location_text:'Audio audition only'}]});
  const base=`/api/production/${session.session_id}/segments/segment_001`,identity={provider,voice_id:voiceId,language:'bn',model:provider==='elevenlabs'?'eleven_v4':provider==='azure'?'azure-neural':'bangladeshi-vits'};
  await api(base+'/voice',identity,'PUT');const estimate=await api(base+'/estimate');let approval={};
  if(estimate.paid){
    const accepted=await new Promise(resolve=>{const choice=el('div');choice.append(el('p','quiet',`${estimate.characters} অক্ষরের paid নমুনা। অ্যাকাউন্টের মূল্য প্রযোজ্য।`),button('Approve paid sample',async()=>{choice.remove();resolve(true);}),button('না',async()=>{choice.remove();resolve(false);}));box.append(choice);});
    if(!accepted)return;approval={paid_approved:true,approval_token:estimate.approval_token};
  }
  await api(base+'/takes',approval);const note=el('p','quiet','নমুনা তৈরি হচ্ছে…');box.append(note);
  for(let i=0;i<300;i++){const current=await api('/api/production/'+session.session_id),take=current.segments[0].takes[0];if(take.status==='failed'){note.textContent='নমুনা তৈরি করা যায়নি।';return;}if(take.status==='completed'){audio.src=take.audio_url;audio.hidden=false;note.remove();return;}await new Promise(r=>setTimeout(r,1000));}
  note.textContent='নমুনা এখনও প্রস্তুত নয়। এটি নিজে থেকে আবার তৈরি করা হবে না।';
}

async function loadHistory(reset=true){
  if(reset){historyRows=[];historyOffset=0;}
  const batch=await api('/api/conversations?limit=30&offset='+historyOffset);historyOffset+=batch.length;
  const rows=historyRows.concat(batch);historyRows=rows;$('history-list').replaceChildren();
  for(const row of rows){const item=button('',async()=>{const data=await api('/api/conversations/'+row.id);mount(data,true);watch(cards.get(data.id));localStorage.setItem('toon-chat-selected-v5',data.id);if(innerWidth<650)$('history').hidden=true;},'history-item');item.append(el('strong','',row.prompt.trim().split('\n').slice(0,2).join(' ').slice(0,70)),el('small','',timestamp(row.created_at)+(row.status==='completed'?' · ভিডিও':' · '+(stageText[row.status]||'অপেক্ষায়'))));$('history-list').append(item);}
  if(!rows.length)$('history-list').append(el('p','quiet','আপনার তৈরি কার্টুন এখানে থাকবে।'));
  if(batch.length===30)$('history-list').append(button('Older cartoons',async()=>{await loadHistory(false);},'text-button'));return rows;
}
$('composer').onsubmit=event=>{event.preventDefault();guard(async()=>{
  const prompt=$('prompt').value;if(!prompt.trim()||$('submit').disabled)return;
  $('connection-message').hidden=true;const id=crypto.randomUUID().replaceAll('-','');
  const card=mount({id,prompt,created_at:new Date().toISOString(),status:'planning',stage:'planning'},true);controls();
  $('prompt').value='';localStorage.setItem('toon-chat-pending-v5',JSON.stringify({prompt,request_id:id}));
  try{const data=await api('/api/conversations',{prompt,request_id:id});localStorage.removeItem('toon-chat-pending-v5');if(!$('prompt').value.trim())localStorage.removeItem('toon-chat-draft-v5');update(card,data);localStorage.setItem('toon-chat-selected-v5',id);watch(card);await loadHistory();}
  catch(error){update(card,{...card.data,status:'failed',message:error.message,unsent:true});throw error;}
});};
$('prompt').oninput=()=>{localStorage.setItem('toon-chat-draft-v5',$('prompt').value);controls();};
$('prompt').onkeydown=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();if(!$('submit').disabled)$('composer').requestSubmit();}};
$('history-toggle').onclick=()=>guard(async()=>{$('history').hidden=!$('history').hidden;if(!$('history').hidden)await loadHistory();});$('history-close').onclick=()=>$('history').hidden=true;
guard(async()=>{$('prompt').value=localStorage.getItem('toon-chat-draft-v5')||'';controls();const rows=await loadHistory(),selected=localStorage.getItem('toon-chat-selected-v5');const recent=rows.filter(r=>!stopped.has(r.status)||r.id===selected).reverse();for(const row of recent){mount(row);watch(cards.get(row.id));}if(selected&&!cards.has(selected)){try{const data=await api('/api/conversations/'+selected);mount(data);watch(cards.get(data.id));}catch{/* Historical files are never deleted by the chat. */}}const pending=JSON.parse(localStorage.getItem('toon-chat-pending-v5')||'null');if(pending&&!cards.has(pending.request_id)){try{const data=await api('/api/conversations/'+pending.request_id);mount(data);watch(cards.get(data.id));localStorage.removeItem('toon-chat-pending-v5');}catch{mount({id:pending.request_id,prompt:pending.prompt,created_at:new Date().toISOString(),status:'failed',message:'আগের গল্পটি পাঠানো যায়নি। এখান থেকে আবার পাঠাতে পারেন।',unsent:true});}}controls();});

