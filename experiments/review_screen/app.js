(function () {
  'use strict';
  const payload=JSON.parse(document.getElementById('review-data').textContent);
  const {canAccept,exportToml,SessionTimer}=globalThis.ReviewModel;
  const decisions=new Map(), timer=new SessionTimer();
  const pages=[...new Set(payload.packet.fields.map(field => field.page_id))];
  let page=0, edited=false;
  const el=id => document.getElementById(id);
  function node(tag,text) { const item=document.createElement(tag); if(text !== undefined) item.textContent=text; return item; }
  function progress() {
    const count=[...decisions.values()].filter(value=>value.action !== 'pending').length;
    el('progress').textContent=`${count} / ${payload.packet.fields.length} fields selected (export validates entries)`;
  }
  function render() {
    el('page-count').textContent=`Page ${page+1} / ${pages.length}: ${pages[page]}`;
    el('previous').disabled=page===0; el('next').disabled=page===pages.length-1;
    const fields=payload.packet.fields.filter(field=>field.page_id===pages[page]);
    el('source-image').src=payload.images[fields[0].image];
    el('source-image').alt=`Registered synthetic source page ${pages[page]}`;
    el('fields').replaceChildren();
    for (const field of fields) {
      const index=payload.packet.fields.indexOf(field);
      const state=decisions.get(field.id) || {action:'pending',value:'',reason:''};
      const box=node('fieldset'); box.append(node('legend',field.field));
      box.append(node('p',`Candidate status: ${field.candidate_status}; OCR: ${field.engine_status}`));
      const candidate=node('p',field.candidate === null ? 'No candidate' : field.candidate); candidate.className='candidate'; box.append(candidate);
      const action=node('select'); action.id=`action-${index}`;
      for (const name of ['pending','accept','correct','withhold']) { const option=node('option',name[0].toUpperCase()+name.slice(1)); option.value=name; option.disabled=name==='accept' && !canAccept(field); action.append(option); }
      action.value=state.action;
      const value=node('input'); value.type='text'; value.id=`value-${index}`; value.value=state.value;
      const reason=node('input'); reason.type='text'; reason.id=`reason-${index}`; reason.value=state.reason;
      for (const [control,title] of [[action,'Decision'],[value,'Corrected value (maximum 200 characters)'],[reason,'Reason (maximum 500 characters)']]) {
        const label=node('label',title); label.htmlFor=control.id; box.append(label,control);
      }
      function availability() { value.disabled=action.value!=='correct'; reason.disabled=!['correct','withhold'].includes(action.value); }
      function update() { decisions.set(field.id,{action:action.value,value:value.value,reason:reason.value}); edited=true; availability(); progress(); el('error').textContent=''; }
      action.addEventListener('change',update); value.addEventListener('input',update); reason.addEventListener('input',update); availability(); el('fields').append(box);
    }
    progress();
  }
  function download(name,content,type) {
    const url=URL.createObjectURL(new Blob([content],{type})); const link=node('a');
    link.href=url; link.download=name; document.body.append(link); link.click(); link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  el('digest').textContent=payload.packet_sha256;
  el('previous').addEventListener('click',()=>{if(page>0){page--;render();}});
  el('next').addEventListener('click',()=>{if(page<pages.length-1){page++;render();}});
  el('zoom').addEventListener('input',()=>{el('source-image').style.width=`${el('zoom').value}%`;el('zoom-value').textContent=`${el('zoom').value}%`;});
  el('download-decisions').addEventListener('click',()=>{
    try { download('decisions.toml',exportToml(payload,decisions),'application/toml'); el('error').textContent=''; }
    catch(error) { el('error').textContent=error.message; }
  });
  function timerDisplay() { el('timer').textContent=`${timer.elapsed()} ms (${timer.since === null ? 'paused' : 'running'})`; }
  el('start-timer').addEventListener('click',()=>{timer.start(!document.hidden);timerDisplay();});
  el('pause-timer').addEventListener('click',()=>{timer.pause();timerDisplay();});
  document.addEventListener('visibilitychange',()=>{timer.visibility(!document.hidden);timerDisplay();});
  el('download-timer').addEventListener('click',()=>download('browser-session.json',JSON.stringify(timer.record(payload.packet_sha256),null,2)+'\n','application/json'));
  window.addEventListener('beforeunload',event=>{if(edited){event.preventDefault();event.returnValue='';}});
  window.addEventListener('pagehide',()=>timer.pause());
  setInterval(timerDisplay,250); render();
})();
