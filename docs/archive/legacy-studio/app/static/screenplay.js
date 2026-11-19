// Event corrections are project data, never automatic narration.
const eventTypes=[['scene_description','Scene description'],['action','Character action'],['dialogue','Dialogue'],['narration','Explicit narration'],['camera','Camera instruction'],['sound_effect','Sound effect'],['ignore','Ignore']];
let screenplaySounds=[];
function eventSelect(rows,value,label){const input=node('select');input.setAttribute('aria-label',label);for(const [id,name] of rows){const option=node('option','',name);option.value=id;input.append(option);}input.value=value||'';return input;}
window.renderScreenplay=data=>{
  $('screenplay-events').replaceChildren();$('spoken-preview').replaceChildren();
  for(const event of data.events||[]){
    const row=node('details','script-event '+(event.type==='unresolved_instruction'?'unresolved':''));row.dataset.eventId=event.event_id;row.open=event.type==='unresolved_instruction';
    row.append(node('summary','',`Line ${event.source_line} · ${event.type.toUpperCase()}${event.speaker_label?' — '+event.speaker_label:''}`),node('p','original-line',event.source_text));
    const types=event.type==='unresolved_instruction'?[['unresolved_instruction','Choose classification'],...eventTypes]:eventTypes.some(([id])=>id===event.type)?eventTypes:[[event.type,event.type],...eventTypes];
    const type=eventSelect(types,event.type,'Event type');const text=node('textarea');text.value=event.text;text.rows=2;text.setAttribute('aria-label','Event text');
    const ready=libraries.characters.filter(c=>c.status==='ready').map(c=>[c.id,c.name_bn+' / '+c.name_en]);
    const speaker=eventSelect([['','Choose speaker / actor'],['narrator','Narrator'],['unknown_voice','Off-screen voice'],...ready],event.speaker_id||event.character_ids?.[0],'Speaker or actor');
    const action=eventSelect([['','Choose action'],...actionChoices.map(a=>[a,a.replaceAll('_',' ')])],event.actions?.[0],'Character action');
    const emotion=eventSelect(emotionChoices.map(e=>[e,e]),event.emotion,'Instruction emotion');
    const camera=eventSelect([['','Choose shot'],...shotChoices.map(s=>[s,s])],event.camera_action,'Camera instruction');
    const bg=eventSelect([['','Automatic / choose in background panel'],...libraries.backgrounds.filter(b=>b.status==='ready').map(b=>[b.id,b.name_bn+' / '+b.name_en])],event.background_id,'Event background');
    const sound=eventSelect([['','Choose sound'],...screenplaySounds.map(s=>[s.id,s.id])],event.sound_id,'Sound effect');
    const duration=node('input');duration.type='number';duration.min='.1';duration.max='30';duration.step='.1';duration.placeholder='Automatic action duration';duration.value=event.duration_seconds||'';duration.setAttribute('aria-label','Instruction duration seconds');
    const options=node('div','line-settings');options.append(type,speaker,action,emotion,camera,bg,sound,duration);
    function visibility(){const kind=type.value;speaker.hidden=!['dialogue','action'].includes(kind);action.hidden=kind!=='action';emotion.hidden=!['dialogue','narration','action'].includes(kind);camera.hidden=kind!=='camera';bg.hidden=kind!=='scene_description';sound.hidden=kind!=='sound_effect';duration.hidden=!['action','camera','sound_effect'].includes(kind);}
    type.onchange=visibility;visibility();
    const save=node('button','','Save event correction');save.onclick=()=>guarded(async()=>{
      if(type.value==='unresolved_instruction')throw new Error('Choose how to interpret this line first.');
      if(type.value==='dialogue'&&!speaker.value)throw new Error('Select a dialogue speaker.');
      if(type.value==='action'&&(!ready.some(([id])=>id===speaker.value)||!action.value))throw new Error('Select a ready character and supported animation.');
      const correction={source_text:event.source_text,type:type.value,text:text.value,emotion:emotion.value,
        speaker_label:type.value==='dialogue'?speaker.value:null,character_id:type.value==='action'?speaker.value:null,
        action:type.value==='action'?action.value:null,camera_action:type.value==='camera'?camera.value:null,
        background_id:type.value==='scene_description'?bg.value||null:null,sound_id:type.value==='sound_effect'?sound.value:null,
        duration_seconds:duration.value?Number(duration.value):null};
      project.script_corrections={...(project.script_corrections||{}),[event.event_id]:correction};saveProject();await analyzeStory();
    });row.append(options,text,save);$('screenplay-events').append(row);
  }
  for(const speech of data.spoken_segments||[]){$('spoken-preview').append(node('li','',`${speech.speaker_name} · line ${speech.source_line}: ${speech.text}`));}
  if(!data.spoken_segments?.length)$('spoken-preview').append(node('li','hint','No spoken lines. This screenplay will render silently, with optional ambience/effects.'));
};
guarded(async()=>{screenplaySounds=await request('/api/sounds');if(review)window.renderScreenplay(review);});
