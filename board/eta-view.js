/* ETA text only; dates use the board's Taipei clock. */
(function(root){
 const dateKey=d=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);
 const time=d=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Taipei',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
 const duration=seconds=>{const m=Math.max(1,Math.ceil(seconds/60));return m<60?m+'分钟':+(m/60).toFixed(1)+'小时';};
 function label(eta,now=new Date()){
  if(!eta)return '';
  if(eta.mode==='phase_complete')return eta.phase_label||'本阶段已完成';
  if(eta.mode==='continuous')return '随实验队列交付';
  if(eta.mode==='complete')return eta.actual_at?(eta.completion_label||'已交')+' '+time(new Date(eta.actual_at)):'本阶段已完成';
  if(eta.mode==='paused')return eta.remaining_seconds!=null?'已暂停，恢复后约'+duration(eta.remaining_seconds):'已暂停，条件恢复后更新';
  if(eta.mode==='conditional')return '等'+(eta.short_condition||eta.condition||'前置条件明确')+(eta.remaining_seconds!=null?'后约'+duration(eta.remaining_seconds):'后更新');
  if(!eta.at)return '预计时间待更新';
  const d=new Date(eta.at);if(!Number.isFinite(+d)||+d<=+now||+d-+now>48*3600000)return '预计待定';
  const tomorrow=new Date(+now+86400000),day=dateKey(d)===dateKey(now)?'今天':dateKey(d)===dateKey(tomorrow)?'明天':dateKey(d).slice(5);
  return (eta.overdue?'已超时 · ':'')+'预计 '+day+' '+time(d);
 }
 function detail(eta){if(!eta)return '';return [label(eta),eta.confidence?'把握：'+eta.confidence:'',eta.basis,eta.revision_reason].filter(Boolean).join(' · ');}
 function history(eta){return (eta?.previous_deliveries||[]).map(r=>(r.scope||'上一轮交付')+' '+dateKey(new Date(r.at)).slice(5)+' '+time(new Date(r.at))).concat(eta?.historical_revision?[eta.historical_revision]:[]).join('；');}

 const units=text=>Array.from(String(text));
 const size=text=>units(text).length;
 const shortStage=text=>String(text||'').replace(/^原图(?:回收|接收)$|^回收原图$/,'收图');
 function linked(task,run){return run&&(!task.id||run.id===task.id||run.task_id===task.id)?run:null;}
 function progress(task,run){
  const own=linked(task,run),stage=task.current_stage||own?.current_stage;
  if(stage&&Number.isSafeInteger(stage.done)&&stage.done>=0&&Number.isSafeInteger(stage.total)&&stage.total>0&&stage.done<=stage.total)
   return {stage:shortStage(stage.label||stage.name),done:stage.done,total:stage.total,count:stage.done+'/'+stage.total};
  const match=String(task.status||'').match(/^\s*(\d+)\s*\/\s*(\d+)(?=\s|$|[·；;，,])/);
  if(match&&Number.isSafeInteger(+match[1])&&Number.isSafeInteger(+match[2])&&+match[2]>0&&+match[1]<=+match[2])
   return {stage:'',done:+match[1],total:+match[2],count:match[1]+'/'+match[2]};
  return {stage:'',count:''};
 }
 function compact(left,right){
  if(left&&right){
   for(const candidate of [left+' · '+right,left+'·'+right.replace(/\s/g,'')])if(size(candidate)<=16)return candidate;
  }
  if(size(left)<=16&&left)return left;
  if(size(right)<=16&&right)return right;
  return '';
 }
 function wait(eta,status){
  const condition=String(eta?.short_condition||eta?.condition||status||'');
  if(/登录|登陆|login/i.test(condition))return '等登录';
  if(/空卡|卡可用|资源|设备/.test(condition))return '等空卡';
  if(/领取|待领/.test(condition))return '等领取';
  if(/估时|工作量|运行速度|前置条件|状态确认/.test(condition))return '';
  const match=condition.match(/^(?:等)?([\p{L}\p{M}]{1,8}回复)/u);
  return match?'等'+match[1]:eta?.short_condition&&size('等'+condition)<=14?'等'+condition:'';
 }
 // Status text “约 HH:MM / 约 明天 HH:MM / 约 MM-DD HH:MM” (also 预计…), Taipei clock; '' once passed.
 function declared(status,now){
  const m=String(status||'').match(/(?:^|·)\s*(?:预计(?:完成)?|约)\s*(明天|\d{1,2}-\d{2})?\s*(\d{1,2}):(\d{2})\s*$/);  // only a trailing “· 约 HH:MM” segment counts
  if(!m)return '';
  const hh=+m[2],mm=+m[3],clock=String(hh).padStart(2,'0')+':'+m[3];
  const today=dateKey(now),tomorrow=dateKey(new Date(+now+86400000));
  const day=!m[1]?today:m[1]==='明天'?tomorrow:today.slice(0,5)+m[1].padStart(5,'0');
  if(!(hh<24&&mm<60&&(day>today||(day===today&&clock>time(now)))))return '';
  return day===today?'约 '+clock:day===tomorrow?(hh<12?'明早 ':'明天 ')+clock:'约 '+day.slice(5);
 }
 function task(task,run,now=new Date()){
  const status=String(task.status||''),own=linked(task,run),p=progress(task,own);
  const eta=task.eta||own?.eta;
  if(/待验收|^(?:accepted|delivered|通过|已完成|完成|已交|交付)|(?:^|[·；，])\s*已交(?:付)?\s*$/i.test(status))return '已交';
  const left=p.stage+p.count;
  if(/(?:^|[·；，])\s*(?:stopped|cancelled|已停|停止|取消|终止)/i.test(status)||eta?.mode==='stopped'){const text=compact(left,'已停');return text.includes('已停')?text:'已停';}
  if(/暂停|搁置/.test(status)||eta?.mode==='paused'){const text=compact(left,'暂停');return text.includes('暂停')?text:'暂停';}
  const said=declared(status,now);
  if(eta?.mode==='conditional'||/^(?:等|等待|待领)/.test(status)){
   if(said&&/^\d+\s*\/\s*\d+/.test(status))return compact(left,said);
   const waiting=wait(eta,status);return waiting||compact(left,'');
  }
  // A completed phase and an earlier delivery carry no forecast for the next phase.
  if(['complete','phase_complete','continuous'].includes(eta?.mode))return compact(left,'');
  const raw=eta?.at,at=raw!=null?new Date(typeof raw==='number'?raw*1000:raw):null;
  const reasonable=at&&Number.isFinite(+at)&&+at>+now&&+at-+now<=48*3600000&&!eta.overdue;
  let timing='';
  if(reasonable){
   const tomorrow=dateKey(new Date(+now+86400000)),day=dateKey(at);
   timing=day===dateKey(now)?'约 '+time(at):day===tomorrow?(+time(at).slice(0,2)<12?'明早 ':'明天 ')+time(at):'';
  }else if(!eta||!eta.at){
   timing=said;
  }
  return compact(left,timing?timing+(left?'':' 交'):'');
 }
 const api={label,detail,duration,history,task,progress};if(typeof module==='object' && module.exports)module.exports=api;else root.EtaView=api;
})(typeof window==='object'?window:globalThis);
