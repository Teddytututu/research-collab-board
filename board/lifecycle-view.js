(function(root,factory){
  const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.LifecycleView=api;
})(typeof window==='object'?window:globalThis,()=>{
  function taskState(task){
    const s=String(task.status||'').trim();
    if(/^(stopped|cancelled|已停|取消)/i.test(s))return {label:'已停',css:'task-stopped',done:true,rank:5};
    if(/^(accepted|通过|完成|已完成|收回|不再需要)/i.test(s))return {label:'已完成',css:'s-done',done:true,rank:5};
    if(/^(daily|每日)/i.test(s))return {label:'每日',css:'task-daily',rank:4};
    if(/^(delivered|已交|待验收)/i.test(s))return {label:'已交',css:'task-review',rank:1};
    if(/^(rejected|blocked|退回|卡住|受阻|失败)/i.test(s))return {label:'卡住',css:'task-blocked',rank:3};
    if(/^\d+\s*\/\s*\d+(?:\s|$)/.test(s))return {label:'在跑',css:'task-run',rank:0};
    if(/^(暂停|搁置|等待|等)/.test(s))return {label:'排队',css:'task-queue',waiting:true,rank:2};
    return {label:'排队',css:'task-queue',rank:2};
  }
  function patrolState(record={},now=new Date()){
    const next=Date.parse(record.next_at),last=Date.parse(record.at);
    const overdue=Number.isFinite(next)&&now.getTime()>next+15*60*1000;
    return {overdue,label:overdue?'巡检超时':Number.isFinite(last)?'已巡检':'待巡检'};
  }
  function renderPatrols(container,overview,now=new Date()){
    const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
    const panel=node('div','patrol-strip');panel.setAttribute('aria-label','助手巡检');
    const clock=value=>{const date=new Date(value);return Number.isFinite(date.getTime())?date.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'待登记';};
    for(const who of ['Claude','GPT']){
      const record=overview.patrols?.[who]||{},state=patrolState(record,now);
      const row=node('div','patrol-row'+(state.overdue?' overdue':''));
      const issues=Array.isArray(overview.flow_issues)?overview.flow_issues.filter(i=>i.owner===who&&i.code!=='patrol_overdue').length:record.open_issues||0;
      row.append(node('strong','patrol-who',who),node('span','patrol-time','上次 '+clock(record.at)+' · 下次 '+clock(record.next_at)),
        node('span','patrol-state',state.label),node('span','patrol-issues','流程问题 '+issues),node('span','patrol-note',record.note||'登记巡检后显示摘要'));
      panel.append(row);
    }
    container.append(panel);return panel;
  }
  return {taskState,patrolState,renderPatrols};
});
