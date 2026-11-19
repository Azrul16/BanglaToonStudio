// Default workflow: one click; manual production tools remain available on demand.
document.body.classList.add('automatic-mode');
const studioContent=$('studio-content'), optionalActions=node('div','actions optional-actions');
optionalActions.append($('analyze'),$('generate'),$('browse-characters'));studioContent.append(optionalActions);
const engineDetails=document.querySelector('.editor > details');if(engineDetails)studioContent.append(engineDetails);
if(engineDetails)engineDetails.append($('readiness'));
for(const element of [document.querySelector('.review-column'),$('screenplay-panel'),$('voice-studio-panel'),$('voice-panel'),$('sound-studio-panel')])if(element)studioContent.append(element);
const editorHint=document.querySelector('.editor > .hint');if(editorHint)editorHint.textContent='Everything is planned automatically. Offline mode uses one shared voice; saved character voices are reused.';
$('story').previousElementSibling?.classList.add('story-tip');
if(project.music===undefined){project.music=true;$('music').checked=true;saveProject();}
let automaticId=null,automaticPolling=0;
window.updateAutoControls=()=>{$('auto-generate').disabled=running||!$('story').value.trim();if(automaticId&&running)$('cancel').hidden=false;};
const originalControls=controls;controls=function(){originalControls();window.updateAutoControls();};
const inputHandler=$('story').oninput;$('story').oninput=()=>{inputHandler();window.updateAutoControls();};
$('issues').addEventListener('click',()=>$('studio-tools').open=true,true);

async function followAutomatic(id){
  const own=++automaticPolling;automaticId=id;running=true;initiated=true;currentJob=null;controls();$('cancel').hidden=false;
  try{
    while(own===automaticPolling){
      const data=await request('/api/automatic/'+id);
      if(data.job_id){await follow(data.job_id);await request('/api/automatic/'+id);return;}
      $('status').textContent=data.message||data.status;
      const percent=data.total_segments?Math.round(30*(data.completed_segments||0)/data.total_segments):0;
      $('bar').style.width=percent+'%';$('bar').parentElement.setAttribute('aria-valuenow',percent);
      if(['failed','cancelled'].includes(data.status))throw new Error(data.error||data.status);
      await new Promise(resolve=>setTimeout(resolve,850));
    }
  }finally{if(own===automaticPolling){automaticId=null;running=false;controls();}}
}
$('auto-generate').onclick=()=>guarded(async()=>{
  initiated=true;showError('');running=true;currentJob=null;controls();$('result').hidden=true;
  $('status').textContent='Reading the story and planning the cartoon…';
  const body={...modeOptions(),renderer:'godot',story:$('story').value,character_mappings:project.character_mappings,
    scenes:project.manualScenes?project.scenes:null,request_id:crypto.randomUUID().replaceAll('-','')};
  try{
    let result;
    try{result=await request('/api/automatic/generate',body);}
    catch(error){
      if(error.status===409&&error.detail?.plan){
        const plan=error.detail.plan;const lines=plan.lines.map((s,i)=>(plan.usage[i].cached?'[cached] ':'')+s.speaker_name+': '+s.synthesis_text).join('\n');
        const price=plan.estimated_usd===null?'Account pricing applies.':`Estimated $${plan.estimated_usd}.`;
        if(!confirm(`Generate paid speech for this cartoon?\n${plan.characters} submitted characters. ${price}\n\n${lines}\n\nOnly this batch is approved. No automatic paid retries.`))return;
        result=await request('/api/automatic/generate',{...body,paid_approved:true,approval_token:plan.approval_token});
      }else if(error.status===422&&error.detail?.issues){
        renderReview(error.detail);$('studio-tools').open=true;$('status').textContent='One or more details need your choice. Resolve the highlighted items, then Generate Cartoon.';return;
      }else throw error;
    }
    localStorage.setItem('toon-automatic-v4',result.automatic_id);await followAutomatic(result.automatic_id);
  }finally{running=false;controls();}
});
const originalCancel=$('cancel').onclick;$('cancel').onclick=()=>automaticId&&!currentJob?guarded(async()=>{await request('/api/automatic/'+automaticId+'/cancel',{});$('status').textContent='Stopping after the current operation…';}):originalCancel();
const originalNew=$('new-project').onclick;$('new-project').onclick=()=>{originalNew();$('screenplay-events').replaceChildren();$('spoken-preview').replaceChildren();window.renderProduction?.();$('studio-tools').open=false;controls();};
guarded(async()=>{const id=localStorage.getItem('toon-automatic-v4');if(id){initiated=true;const data=await request('/api/automatic/'+id);if(!['completed','failed','cancelled'].includes(data.status))await followAutomatic(id);else if(data.job_id)await follow(data.job_id);else if(data.error)showError(data.error);}controls();});
controls();
