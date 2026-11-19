const $=id=>document.getElementById(id);
const projectKey='toon-review-project-v5', jobKey='toon-shorts-job-v3';
let project={story:$('story').value,character_mappings:{},scenes:null,manualScenes:false,duration_mode:'shorts',video_format:'auto',renderer:'godot'};
try { const saved=localStorage.getItem(projectKey);const old=JSON.parse(saved||localStorage.getItem('toon-review-project-v4')||'{}');project={...project,...old,...(!saved?{scenes:null,manualScenes:false,script_corrections:{}}:{})}; } catch {}
let review=null, libraries={characters:[],backgrounds:[]}, pick=null, selected=null;
let currentJob=null, token=0, initiated=false, running=false, reviewing=false;
const terminal=new Set(['completed','failed','cancelled']);
const labels={queued:'Queued',parsing:'Checking reviewed assets',generating_audio:'Generating Bengali speech',lip_sync:'Analyzing mouth movements',rendering:'Compositing sprites',encoding:'Finishing encoding',validating:'Validating MP4',completed:'Your cartoon is ready',failed:'Generation failed',cancelled:'Cancelled'};
function node(tag,cls,text) { const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e; }
function saveProject(){localStorage.setItem(projectKey,JSON.stringify(project));}
function showError(message){$('error').textContent=message;$('error').hidden=!message;}
function controls(){ $('generate').disabled=running||reviewing||!review?.ready||(project.renderer==='godot'&&review?.spoken_segments?.length>0&&!window.productionApproved?.()); $('analyze').disabled=reviewing; $('cancel').hidden=!running||!currentJob; $('new-project').disabled=running; for(const id of ['duration-mode','video-format','renderer','sound-effects','music'])$(id).disabled=running||reviewing; }
async function request(url,body,method='POST'){
  const response=await fetch(url,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok){ const detail=data.detail||data; const error=new Error(typeof detail==='string'?detail:detail.message||detail.issues?.map(i=>i.message).join('\n')||JSON.stringify(detail));error.status=response.status;error.detail=detail;throw error; }
  return data;
}
async function guarded(action){try{await action();}catch(e){showError(e.message);if($('picker').open){$('picker-error').textContent=e.message;$('picker-error').hidden=false;}if(e.detail?.issues)showIssues(e.detail.issues);if(e.status===409&&review){review.ready=false;$('review-status').textContent='Selections or assets changed. Analyze again.';controls();}}}
function selectedScenes(){ return (review?.scenes||project.scenes||[]).map(s=>({scene_id:s.scene_id,start_segment:s.start_segment,end_segment:s.end_segment,background_id:s.background_id,location_text:s.location_text||''})); }
function modeOptions(){return {duration_mode:project.duration_mode,video_format:project.video_format,renderer:project.renderer||'godot',sound_effects:project.sound_effects!==false,music:!!project.music,script_corrections:project.script_corrections||{},audio_levels:project.audio_levels||{}};}
function payload(explicit=true){return {...modeOptions(),story:$('story').value,character_mappings:project.character_mappings,scenes:explicit?selectedScenes():(project.manualScenes?project.scenes:null)};}
function showMode(){const mini=project.duration_mode==='mini';$('renderer').value=project.renderer||'godot';$('duration-mode').value=project.duration_mode;$('video-format').value=project.video_format==='vertical'?'vertical':'landscape';$('format-label').hidden=!mini;$('sound-effects').checked=project.sound_effects!==false;$('music').checked=!!project.music;const fps=project.renderer==='pillow'?24:30;$('format-summary').textContent=(mini&&project.video_format!=='vertical'?'1280 × 720':'720 × 1280')+` · ${fps} fps`;$('duration-hint').textContent=mini?'Target: 2–3 minutes.':'Target: 30–40 seconds.';}
function changeMode(){project.duration_mode=$('duration-mode').value;project.video_format=project.duration_mode==='mini'?$('video-format').value:'auto';review=null;saveProject();showMode();$('review-status').textContent='Duration or format changed. Analyze again.';controls();}
$('duration-mode').onchange=changeMode;$('video-format').onchange=changeMode;$('renderer').onchange=()=>{project.renderer=$('renderer').value;review=null;saveProject();showMode();controls();$('review-status').textContent='Renderer changed. Analyze again.';};showMode();
$('sound-effects').checked=project.sound_effects!==false;$('music').checked=!!project.music;
for(const id of ['sound-effects','music'])$(id).onchange=()=>{project.sound_effects=$('sound-effects').checked;project.music=$('music').checked;review=null;saveProject();controls();$('review-status').textContent='Sound settings changed. Analyze again.';};
function count(){ $('count').textContent=`${$('story').value.length.toLocaleString()} characters`; }
function image(url,cls='row-preview'){ if(!url)return node('div',cls+' missing-preview','Preview unavailable'); const img=node('img',cls);img.src=url;img.alt='';img.loading='lazy';return img; }
function state(value){return node('span','state '+value,value.replaceAll('_',' '));}
function asset(kind,id){return libraries[kind].find(a=>a.id===id);}
function showIssues(issues){
  const box=$('issues');box.replaceChildren();box.hidden=!issues.length;
  if(issues.length)box.append(node('p','',`${issues.length} item${issues.length===1?'':'s'} need attention before generation.`));
  for(const issue of issues){ const link=node('button','issue-link',`${issue.source_text}: ${issue.message}`);
    link.onclick=()=>{ const rows=issue.type==='character'?review?.characters:review?.scenes;const index=rows?.findIndex(r=>issue.type==='character'?r.speaker_text===issue.source_text:r.scene_id===issue.scene_id);
      if(issue.event_id){const event=document.querySelector(`[data-event-id="${CSS.escape(issue.event_id)}"]`);if(event){event.open=true;event.scrollIntoView({behavior:'smooth',block:'center'});return;}}
      if(index>=0)$(issue.type==='character'?`character-${index}`:`scene-${index}`).scrollIntoView({behavior:'smooth',block:'center'});else $('status').scrollIntoView({behavior:'smooth'});};box.append(link); }
}
function renderReview(data){
  review=data;project.story=$('story').value;project.scenes=selectedScenes();saveProject();
  $('characters').replaceChildren();$('scenes').replaceChildren();
  $('character-count').textContent=data.characters.length;$('scene-count').textContent=data.scenes.length;
  $('character-status').textContent=data.characters.every(c=>c.status==='ready')?'All resolved':'Review needed';
  data.characters.forEach((c,index)=>{
    const a=asset('characters',c.character_id), row=node('div','asset-row');row.id=`character-${index}`;
    row.append(c.role==='visible'?image(a?.preview_url):node('div','row-preview missing-preview',c.role==='narration'?'Narration':'Voice only'));const copy=node('div','row-copy');copy.append(node('strong','',c.speaker_text),state(c.status));
    copy.append(node('p','',c.role==='visible'?(a?`${a.name_en} · ${a.version||'unversioned'}`:'Choose a character from your library'):c.role==='narration'?'Narration · no visible character':'Off-screen voice · no visible character'));
    if(c.source==='remembered')copy.append(node('p','','Remembered alias'));
    else if(c.source==='project')copy.append(node('p','','Project-only choice'));
    if(c.status!=='ready')copy.append(node('p','issue-note',c.reason||'Select a ready rig or an off-screen role.'));
    if(a?.articulated_status&&project.renderer==='godot')copy.append(node('p','hint',a.articulated_status.replaceAll('_',' ')));
    const change=node('button','',c.status==='ready'?'Change':'Choose character');change.onclick=()=>openPicker('characters',{key:c.key,label:c.speaker_text,current:c.character_id});row.append(copy,change);$('characters').append(row);
  });
  data.scenes.forEach((s,index)=>{
    const a=asset('backgrounds',s.background_id),row=node('div','asset-row');row.id=`scene-${index}`;row.append(image(a?.preview_url,'row-preview scene-preview'));
    const copy=node('div','row-copy');copy.append(node('strong','',`Scene ${index+1} · ${a?.name_bn||'Choose a background'}`),state(s.status));
    copy.append(node('p','',`${s.location_text||'No location identified'} · segments ${s.start_segment+1}–${s.end_segment}`));
    if(a)copy.append(node('p','',`${a.name_en} · ${a.time_of_day}`));
    else copy.append(node('p','issue-note',"We couldn't match this location. Choose a background for this scene."));
    const change=node('button','',a?'Change background':'Choose background');change.onclick=()=>openPicker('backgrounds',{index,label:s.location_text||'',current:s.background_id});row.append(copy,change);$('scenes').append(row);
  });
  showIssues(data.issues);$('review-status').textContent=data.ready?'Cast and scenes validated. Ready to generate.':'Resolve the highlighted items. Your story stays editable.';
  if(data.estimated_duration?.is_estimate)$('estimate').textContent=`Estimated ${data.estimated_duration.min}–${data.estimated_duration.max}s · final timing uses speech`;
  renderBoundaries();controls();
  $('style-review').textContent=(data.warnings||[]).join(' ');
  window.renderScreenplay?.(data);
  window.renderProduction?.();
}
function renderBoundaries(){
  $('boundaries').hidden=!review?.segments.length;$('segments').replaceChildren();
  review?.segments.forEach((s,index)=>{const row=node('div','segment'), label=node('label','',`${index+1}. ${s.speaker_name}: ${s.text}`);const input=node('input');input.type='checkbox';input.checked=review.scenes.some(sc=>sc.start_segment===index);input.disabled=index===0;input.setAttribute('aria-label',`Start scene at segment ${index+1}`);input.onchange=()=>guarded(async()=>{
      const starts=new Set(review.scenes.map(sc=>sc.start_segment)); if(input.checked)starts.add(index);else starts.delete(index);
      const sorted=[...starts].sort((a,b)=>a-b),old=review.scenes;
      project.scenes=sorted.map((start,i)=>{const prior=old.find(sc=>sc.start_segment===start);return {scene_id:`scene_${String(i+1).padStart(3,'0')}`,start_segment:start,end_segment:sorted[i+1]??review.segments.length,background_id:prior?.background_id||null,location_text:prior?.location_text||review.segments[start].text};});
      project.manualScenes=true;const data=await request('/api/resolve',{...modeOptions(),story:$('story').value,character_mappings:project.character_mappings,scenes:project.scenes});renderReview(data);
    });row.append(input,label);$('segments').append(row);});
}
async function analyzeStory(){reviewing=true;controls();showError('');$('review-status').textContent='Discovering characters, locations and valid assets…';try{renderReview(await request('/api/analyze',payload(false)));}finally{reviewing=false;controls();}}
async function loadLibrary(){const [characters,backgrounds]=await Promise.all([request('/api/characters'),request('/api/backgrounds')]);libraries={characters,backgrounds};}
function openPicker(kind,context=null){pick={kind,context};selected=context?.current||null;$('picker-title').textContent=kind==='characters'?'Choose a character':'Choose a background';$('picker-description').textContent=context?`Resolve “${context.label||'this scene'}” using a validated local asset.`:'Browse the actual local assets. Reference-only and incomplete rigs cannot be rendered.';
  $('picker-error').hidden=true;
  $('asset-search').value='';$('asset-status').value=context?'ready':'';$('asset-group').replaceChildren();
  const all=node('option','','All '+(kind==='characters'?'age groups':'times'));all.value='';$('asset-group').append(all);
  for(const value of [...new Set(libraries[kind].map(a=>kind==='characters'?a.age_group:a.time_of_day))]){const option=node('option','',value);option.value=value;$('asset-group').append(option);}
  $('voice-roles').hidden=kind!=='characters'||!context;$('mapping-options').hidden=!context;$('remember').checked=false;$('mapping-alias').value=context?.label||'';renderPicker();$('picker').showModal();
}
function renderPicker(){
  const query=$('asset-search').value.normalize('NFC').toLocaleLowerCase(),status=$('asset-status').value,group=$('asset-group').value;$('asset-grid').replaceChildren();
  const rows=libraries[pick.kind].filter(a=>(!query||[a.name_bn,a.name_en,...a.aliases].join(' ').normalize('NFC').toLocaleLowerCase().includes(query))&&(!status||a.status===status)&&(!group||(pick.kind==='characters'?a.age_group:a.time_of_day)===group));
  for(const a of rows){const card=node('button','library-card '+(pick.kind==='backgrounds'?'background ':'')+(selected===a.id?'selected':''));card.disabled=!!pick.context&&a.status!=='ready';card.setAttribute('aria-label',`${a.name_en} — ${a.status.replaceAll('_',' ')}`);card.append(image(a.preview_url,''));const copy=node('div','card-text');copy.append(node('strong','',a.name_bn),node('small','',a.name_en),state(a.status),node('small','',`${pick.kind==='characters'?a.age_group:a.time_of_day} · ${a.version||'unversioned'}`));if(a.reason)copy.append(node('p','',a.reason));card.append(copy);card.onclick=()=>{selected=a.id;renderPicker();};$('asset-grid').append(card);}
  if(!rows.length)$('asset-grid').append(node('p','empty','No assets match these filters.'));
  for(const button of document.querySelectorAll('[data-role]'))button.classList.toggle('selected',selected===button.dataset.role);
  $('picker-apply').disabled=!selected;$('picker-apply').textContent=$('remember').checked?'Use & remember alias':'Use for this project';
}
async function applyPicker(){
  if(!pick.context||!selected)return;
  const context=pick.context,alias=$('mapping-alias').value.trim()||context.label;
  if($('remember').checked&&!alias)throw new Error('Enter an alias before remembering this background.');
  let body={asset_type:pick.kind==='characters'?'character':'background',alias:(alias||'current scene').slice(0,250),asset_id:selected,scope:$('remember').checked?'remember':'project'};
  while(true){try{await request('/api/mappings',body);break;}catch(e){if(e.status!==409)throw e;
      if(!window.confirm(e.message+'\n\nRemember this mapping?'))body.scope='project';
      else if(e.detail.reason==='alias_conflict')body.confirm_conflict=true;else body.confirm_generic=true;}}
  const scenes=selectedScenes();if(pick.kind==='characters')project.character_mappings[context.key]=selected;
  else{scenes[context.index].background_id=selected;scenes[context.index].location_text=alias||context.label;project.manualScenes=true;}
  const data=await request('/api/resolve',{...modeOptions(),story:$('story').value,character_mappings:project.character_mappings,scenes});
  $('picker').close();renderReview(data);
}
function warnings(items){$('warnings').replaceChildren();for(const text of items||[])$('warnings').append(node('li','',text));$('warnings').hidden=!items?.length;}
function showReport(job){const report=job.report;if(!report)return;const t=report.timings;
  $('report-text').textContent=[`Video: ${job.duration_seconds.toFixed(2)}s · ${job.width} × ${job.height} · ${job.fps} fps`,`Speech: ${report.tts.device} · ${report.sprite_renderer} · ${t.encoder}`,`Generation (this attempt): ${report.total_generation_seconds}s`,`Scenes: ${t.scene_count||1} · reused: ${t.scenes_reused||0}`, ...Object.entries(t).filter(([k])=>k.endsWith('_seconds')).map(([k,v])=>`${k.replaceAll('_',' ')}: ${v}s`),`Peak RAM: ${report.memory.peak_process_tree_rss_mb} MB`,...report.assets.characters.map(c=>`Character: ${c.character_id} · ${c.version} · ${c.identity_hash.slice(0,16)}`),...(report.assets.backgrounds||[report.assets.background]).map(b=>`Background: ${b.background_id} · ${b.version}`),`Output: ${report.output}`,t.encoding_overlap_note].join('\n');
}
function showSceneProgress(job){$('scene-progress').replaceChildren();for(const [i,s] of (job.render_scenes||[]).entries()){const row=node('div','scene-progress-row');row.append(node('span','',`Scene ${i+1} · ${s.duration_seconds.toFixed(1)}s`),node('span','',`${s.status} · ${s.progress}%${s.cached?' · cached':''}${s.processing_seconds!==undefined?' · '+s.processing_seconds.toFixed(1)+'s processing':''}`));if(s.status==='failed'&&terminal.has(job.status)){const retry=node('button','','Retry this scene');retry.onclick=()=>guarded(async()=>{showError('');const next=await request(`/api/jobs/${job.job_id}/scenes/${s.scene_id}/retry`,{});await follow(next.job_id);});row.append(retry);} $('scene-progress').append(row);}}
async function follow(id){const own=++token;currentJob=id;localStorage.setItem(jobKey,id);running=true;controls();$('retry').hidden=true;try{while(own===token){const job=await request(`/api/jobs/${id}`);$('status').textContent=`${labels[job.status]||job.status} · ${job.progress}%`;$('bar').style.width=`${job.progress}%`;$('bar').parentElement.setAttribute('aria-valuenow',job.progress);showSceneProgress(job);
    if(terminal.has(job.status)){warnings(job.warnings);if(job.status==='completed'&&job.video_url){$('result').hidden=false;$('video').src=job.video_url;$('video').poster=job.poster_url;$('video').style.aspectRatio=`${job.width}/${job.height}`;$('video').style.width=job.width>job.height?'min(100%,960px)':'min(100%,380px)';$('download').href=job.video_url+'?download=true';$('video-info').textContent=`${job.duration_seconds.toFixed(1)}s · ${job.width} × ${job.height} MP4`;showReport(job);}else{showError(job.error||'Generation cancelled.');$('retry').hidden=false;$('retry').textContent=job.scene_pipeline_version?'Resume unfinished scenes':'Retry generation';$('retry').dataset.endpoint=job.scene_pipeline_version?'resume':'retry';}return;}await new Promise(r=>setTimeout(r,900));}}
  finally{if(own===token){running=false;controls();}}}
$('analyze').onclick=()=>guarded(analyzeStory);
$('generate').onclick=()=>guarded(async()=>{initiated=true;showError('');if(!review?.ready)return;
  const approved={...modeOptions(),story:$('story').value,character_mappings:review.character_mappings,scenes:selectedScenes(),review_token:review.review_token,...(project.renderer==='godot'?{production_id:window.currentProductionId?.()}: {})};
  running=true;currentJob=null;controls();$('status').textContent='Checking reviewed story…';
  try{const check=await request('/api/preflight',approved);if(!check.ready){renderReview(check);return;}
    if($('story').value!==approved.story)throw new Error('Story changed during preflight. Analyze again.');
    $('result').hidden=true;$('status').textContent='Submitting reviewed story…';$('bar').style.width='0%';
    const job=await request('/api/generate',approved);await follow(job.job_id);
  }finally{running=false;controls();}});
$('cancel').onclick=()=>guarded(async()=>{if(currentJob){await request(`/api/jobs/${currentJob}/cancel`,{});$('status').textContent='Cancellation requested; waiting for the current operation.';}});
$('retry').onclick=()=>guarded(async()=>{initiated=true;showError('');const job=await request(`/api/jobs/${currentJob}/${$('retry').dataset.endpoint||'resume'}`,{});await follow(job.job_id);});
$('story').value=project.story;count();
$('story').oninput=()=>{project.story=$('story').value;project.scenes=null;project.manualScenes=false;project.script_corrections={};review=null;window.renderProduction?.();saveProject();count();$('review-status').textContent='Script changed. Analyze again before generating.';controls();};
$('new-project').onclick=()=>{localStorage.setItem(projectKey+'-previous',JSON.stringify(project));project={story:'',character_mappings:{},scenes:null,manualScenes:false,duration_mode:'shorts',video_format:'auto',renderer:'godot'};$('story').value='';review=null;count();saveProject();showMode();$('characters').replaceChildren(node('p','empty','Analyze your new story.'));$('scenes').replaceChildren();$('issues').hidden=true;$('boundaries').hidden=true;$('review-status').textContent='New project. Previous draft is backed up locally.';controls();};
$('refresh').onclick=()=>guarded(async()=>{await request('/api/assets/refresh',{});await loadLibrary();if($('story').value.trim())await analyzeStory();});
$('browse-characters').onclick=()=>openPicker('characters');$('browse-backgrounds').onclick=()=>openPicker('backgrounds');$('picker-close').onclick=()=>$('picker').close();
for(const id of ['asset-search','asset-status','asset-group','remember'])$(id).addEventListener(id==='asset-search'?'input':'change',renderPicker);
for(const button of document.querySelectorAll('[data-role]'))button.onclick=()=>{selected=button.dataset.role;renderPicker();};
$('picker-apply').onclick=()=>guarded(applyPicker);
guarded(async()=>{await loadLibrary();const health=await request('/api/health');const h=health.hardware;$('readiness').textContent=`Speech: ${h.cuda_available?'CUDA available':'CPU'} · ${h.encoder} · Rhubarb: ${health.rhubarb_found?'ready':'approximate fallback'} · Model: ${health.model_cached?'cached':'downloads on first use'}`;
  const saved=localStorage.getItem(jobKey),jobs=await request('/api/jobs');if(!initiated&&saved&&jobs.some(j=>j.job_id===saved))await follow(saved);
  if(project.story.trim())await analyzeStory();});
