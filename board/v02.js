/* Project setup and quota advice. */
(()=>{
 const $=s=>document.querySelector(s),node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
 const json=async(url,body)=>{const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw new Error(v.error || '请稍后重试');return v;};
 const tiers=[['plenty','充足'],['normal','一般'],['tight','紧张'],['low','见底']];
 function quota(s){
  const wrap=$('#quota-body');wrap.replaceChildren();
  for(const name of ['Claude','GPT']){const a=s.agents[name],box=node('article',null,'quota-agent'),head=node('div',null,'quota-head');
   const q=a.quota||{status:a.reported_at?'reported-estimate':'unreported'},pending=q.status==='unreported',percent=Math.round(a.remaining*100)+'%';
   const captions={'native':'原生观测 · '+percent,'manual-estimate':'手动估计 · 约'+percent,'configured-estimate':'档位估计 · 约'+percent,'reported-estimate':'上报估计 · 约'+percent,'conservative-bound':'保守上界 · '+percent,'restriction':'原生限制','unreported':'待上报'};
   head.append(node('strong',name),node('span',captions[q.status]||'待上报'));box.append(head);
   const meter=node('meter');meter.min=0;meter.max=1;meter.value=a.remaining;meter.hidden=pending||q.status==='restriction';meter.setAttribute('aria-label',name+(q.status==='native'?'原生观测额度':'额度估计'));box.append(meter);
   const next=a.paused?'提及或验收时唤醒':Number.isFinite(a.next_wake)?new Date(a.next_wake*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'待计算';
   box.append(node('p',pending?'巡检建议待上报':'建议巡检 · '+next),node('p',pending?'初始档位仅用于规划；助手上报后更新。':a.reason,'quota-reason'));
   if(q.observed_at!=null&&Number.isFinite(Number(q.observed_at)))box.append(node('small','观测时间 · '+new Date(Number(q.observed_at)*1000).toLocaleString()));
   const label=node('label','手动估计档位 '),select=node('select');select.setAttribute('aria-label',name+'额度档位');
   const prompt=node('option','选择档位');prompt.value='';prompt.disabled=true;prompt.selected=q.status!=='manual-estimate';select.append(prompt);
   for(const [value,text]of tiers){const option=node('option',text);option.value=value;option.selected=q.status==='manual-estimate'&&(q.tier===value||!q.tier&&Math.abs(a.remaining-({plenty:.7,normal:.4,tight:.15,low:.03}[value]))<.001);select.append(option);}
   select.onchange=async()=>{select.disabled=true;try{quota(await json('/api/quota',{agent:name,tier:select.value,reset_hours:a.reset_hours}));}catch(e){box.append(node('p',e.message));}finally{select.disabled=false;}};
   label.append(select);box.append(label,node('small',(pending?'初始估计分工 ':'建议分工 ')+Math.round(s.shares[name]*100)+'%'));wrap.append(box);
  }
 }
 async function init(){await BoardIdentity.ready;const p=await json('/api/project');
  $('#setup-question').value=p.question;$('#setup-deliverable').value=p.deliverable;$('#setup-name').value=p.user_name;
  $('#project-settings').open=!p.onboarding_complete;
  $('#setup-form').onsubmit=async e=>{e.preventDefault();try{await json('/api/project',{question:$('#setup-question').value,deliverable:$('#setup-deliverable').value,user_name:$('#setup-name').value});$('#setup-status').textContent='已保存';await BoardIdentity.refreshAccounts();location.reload();}catch(e){$('#setup-status').textContent=e.message;}};
  quota(await json('/api/schedule'));
  setInterval(async()=>{try{quota(await json('/api/schedule'));}catch(_){}},45000);
 }
 init().catch(e=>{$('#quota-body').textContent=e.message;});
})();
