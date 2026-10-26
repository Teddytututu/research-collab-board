const test=require('node:test');const assert=require('node:assert/strict');const eta=require('../board/eta-view.js');
const now=new Date('2026-10-23T15:58:00Z');
test('Taipei midnight shows tomorrow',()=>assert.equal(eta.label({mode:'estimate',at:'2026-10-23T16:10:00Z'},now),'预计 明天 00:10'));
test('expired estimates return to pending',()=>assert.equal(eta.label({mode:'estimate',at:'2026-10-23T21:00:00+08:00',overdue:true},now),'预计待定'));
test('pause states remaining time',()=>assert.equal(eta.label({mode:'paused',remaining_seconds:7200},now),'已暂停，恢复后约2小时'));
test('report dependency keeps two hours',()=>assert.equal(eta.label({mode:'conditional',condition:'新视频独立盲数完成',remaining_seconds:7200},now),'等新视频独立盲数完成后约2小时'));
test('completed milestone uses actual clock',()=>assert.equal(eta.label({mode:'complete',actual_at:'2026-10-23T21:06:00+08:00'},now),'已交 21:06'));
test('details include confidence and basis',()=>assert.match(eta.detail({mode:'conditional',condition:'接手',remaining_seconds:3600,confidence:'低',basis:'10个示例'}),/把握：低.*10个示例/));
test('continuous work uses queue completion condition',()=>assert.equal(eta.label({mode:'continuous'}),'随实验队列交付'));

test('sample delivery remains scoped',()=>assert.equal(eta.label({mode:'complete',completion_label:'已交示例',actual_at:'2026-10-23T20:52:00+08:00'},now),'已交示例 20:52'));
test('unclaimed task has one update clause',()=>assert.equal(eta.label({mode:'conditional',condition:'任务领取并核对工作量',short_condition:'领取'},now),'等领取后更新'));

test('video phase completion preserves whole-task scope',()=>assert.equal(eta.label({mode:'phase_complete',phase_label:'视频48/48已完成'}),'视频48/48已完成'));
test('previous deliveries render in a separate dated history string',()=>assert.match(eta.history({previous_deliveries:[{at:'2026-10-23T21:20:00+08:00',scope:'v0.2'}]}),/v0.2 10-23 21:20/));
test('short clocks use the actual same-day forecast',()=>assert.equal(eta.task({status:'6/48',eta:{mode:'estimate',at:'2026-10-23T23:59:00+08:00'}},null,now),'6/48 · 约 23:59'));
test('a future morning uses 明早 within fourteen code points',()=>assert.equal(eta.task({status:'12/60 · 预计10-24 06:10',eta:{mode:'estimate',at:'2026-10-24T06:10:00+08:00'}},null,now),'12/60·明早06:10'));
test('a future afternoon retains the correct day',()=>assert.equal(eta.task({status:'12/60',eta:{mode:'estimate',at:'2026-10-24T16:10:00+08:00'}},null,now),'12/60·明天16:10'));
test('a numeric patrol timestamp keeps its seconds unit',()=>assert.equal(eta.task({status:'6/48',eta:{mode:'estimate',at:Date.parse('2026-10-24T06:10:00+08:00')/1000}},null,now),'6/48·明早06:10'));
test('invalid, past and distant forecasts retain only progress',()=>{
 for(const at of ['invalid','2026-10-23T01:00:00+08:00','2026-11-28T01:42:00+08:00'])
  assert.equal(eta.task({status:'977/1176 · 预计完成01:42',eta:{mode:'estimate',at}},null,now),'977/1176');
 assert.equal(eta.task({status:'进行中',eta:{mode:'estimate',at:'invalid'}},null,now),'—');
});
test('a dated ETA overrides a contradictory legacy clock',()=>assert.equal(eta.task({status:'6/48 · 预计完成01:42',eta:{mode:'estimate',at:'2026-10-24T06:10:00+08:00'}},null,now),'6/48·明早06:10'));
test('a current-day legacy clock is allowed and a past clock is suppressed',()=>{
 assert.equal(eta.task({status:'6/48 · 预计完成23:59'},null,now),'6/48 · 约 23:59');
 assert.equal(eta.task({status:'6/48 · 预计完成20:37'},null,now),'6/48');
 assert.equal(eta.task({status:'6/48 · 预计10-24 06:10'},null,now),'6/48');
});
test('previous delivery and phase completion keep their scope separate',()=>{
 for(const mode of ['complete','phase_complete','continuous'])
  assert.equal(eta.task({status:'178/320',eta:{mode,phase_label:'视频48/48已完成',actual_at:'2026-10-23T11:05:00+08:00'}},null,now),'178/320');
});
test('daily dates are separate from completed task counts',()=>assert.equal(eta.task({status:'日更10/24通过'},null,now),'—'));
test('delivered tasks use 已交 regardless of their completed counts',()=>{
 for(const status of ['待验收 · 330/330；已交','已交','已完成 330/330','delivered · awaiting review','accepted: reviewed'])assert.equal(eta.task({status},null,now),'已交');
});
test('only a task-linked run supplies progress',()=>{
 assert.equal(eta.task({id:'T002',status:'进行中'},{id:'run-2',task_id:'T002',done:6,total:10},now),'6/10');
 assert.equal(eta.task({id:'T002',status:'进行中'},{id:'run-3',task_id:'T003',done:6,total:10},now),'—');
 assert.equal(eta.task({id:'T002',status:'进行中 · 等T003 8/10'},null,now),'—');
});
test('a current receiving stage supersedes the completed collection',()=>{
 const task={id:'T007',status:'采集1000/1000 · 原图回收877/1000 · 预计10-24 00:17',eta:{mode:'estimate',at:'2026-10-24T00:17:00+08:00'}};
 const run={id:'T007',done:1000,total:1000,note:task.status};
 assert.equal(eta.task(task,run,now),'收图877/1000');
 assert.equal(eta.progress(task,run).done,877);
 assert.equal(eta.progress(task,run).total,1000);
 const copy=JSON.stringify([task,run]);eta.task(task,run,now);assert.equal(JSON.stringify([task,run]),copy);
 assert.equal(eta.task({...task,status:'采集1000/1000'},run,now),'收图877/1000');
 assert.equal(eta.task({id:'T007',status:'采集1000/1000 · 原图回收877/1000 · 预计10-26 00:15',eta:{mode:'estimate',at:'2026-10-26T00:15:00+08:00'}},{id:'T007',done:1000,total:1000},new Date('2026-10-25T23:00:00+08:00')),'收图877/1000');
});
test('structured current stages retain their own counters',()=>assert.equal(eta.task({status:'采集1000/1000',current_stage:{label:'收图',done:877,total:1000}},null,now),'收图877/1000'));
test('an astral stage marker counts as one Unicode code point',()=>{
 const value=eta.task({status:'进行中',current_stage:{label:'🧪',done:12,total:60},eta:{mode:'estimate',at:'2026-10-24T06:10:00+08:00'}},null,now);
 assert.equal(value,'🧪12/60·明早06:10');assert.equal(Array.from(value).length,14);
});
test('pause and stop have compact, distinct labels',()=>{
 assert.equal(eta.task({status:'196/320',eta:{mode:'paused',remaining_seconds:3600}},null,now),'196/320 · 暂停');
 assert.equal(eta.task({status:'已停 · 196/320'},null,now),'196/320 · 已停');
 assert.equal(eta.task({status:'暂停 · 1234567/12345678'},null,now),'暂停');
});
test('waiting labels retain action rather than explanations',()=>{
 assert.equal(eta.task({status:'进行中',eta:{mode:'conditional',condition:'用户Claude登录后验图',remaining_seconds:7200}},null,now),'等登录');
 assert.equal(eta.task({status:'1171/1176',eta:{mode:'conditional',condition:'7号卡可用',remaining_seconds:2160}},null,now),'等空卡');
 assert.equal(eta.task({status:'等你登录'},null,now),'等登录');
 assert.equal(eta.task({status:'进行中',eta:{mode:'conditional',short_condition:'审阅者回复'}},null,now),'等审阅者回复');
 assert.equal(eta.task({status:'12/60',eta:{mode:'conditional',short_condition:'本轮估时'}},null,now),'12/60');
});
test('documents without counters show a compact delivery time',()=>assert.equal(eta.task({status:'界面同步',eta:{mode:'estimate',at:'2026-10-24T06:10:00+08:00'}},null,now),'明早 06:10 交'));
test('every short string fits fourteen Unicode code points',()=>{
 for(const status of ['采集1000/1000 · 原图回收877/1000','🧪训练 12/60','日更10/24通过','123456789/1234567890','已停 · 196/320','暂停 · 196/320'])
  for(const mode of ['estimate','paused','conditional','continuous','phase_complete','complete']){
   const result=eta.task({status,eta:{mode,at:'2026-10-24T06:10:00+08:00',short_condition:'超长🧪🧪🧪🧪🧪前置条件'}},null,now);
   assert.ok(Array.from(result).length<=14,result);
   assert.doesNotMatch(result,/[\uD800-\uDBFF]$/);
  }
});

test('task DOM shows goal, deliverable and one current line while preserving expansion',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.style={};this.attributes={};this.dataset={};this.handlers={};this.className='';this.open=false;this.classList={add:name=>{this.className+=' '+name;}};}
  append(...nodes){this.children.push(...nodes);} replaceChildren(){this.children=[];}
  setAttribute(key,value){this.attributes[key]=value;}
  addEventListener(name,handler){this.handlers[name]=handler;}
  querySelector(tag){for(const child of this.children){if(child.tagName===tag)return child;const match=child.querySelector?.(tag);if(match)return match;}return null;}
 }
 const box=new Element('div'),nodes=[],texts=[];
 const el=(tag,cls,text)=>{const value=new Element(tag);value.className=cls||'';value.textContent=text??'';nodes.push(value);return value;};
 const context={EtaView:eta,CODE:/T\d+/g,$:()=>box,el,document:{createElement:tag=>new Element(tag),createTextNode:text=>{texts.push(text);return {textContent:text};}}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../board/lifecycle-view.js'),'utf8'),context);
 const html=fs.readFileSync(require('node:path').join(__dirname,'../board/index.html'),'utf8');
 vm.runInNewContext(html.slice(html.indexOf('const openState ='),html.indexOf('function linkOrText('))+html.slice(html.indexOf('function taskState('),html.indexOf('function renderFiles('))+'\nthis.renderTasks=renderTasks;',context);
 const forecast={mode:'paused',remaining_seconds:7200,basis:'Full recovery explanation',previous_deliveries:[{scope:'Earlier release',at:'2026-10-23T20:00:00+08:00'}]};
 const overview={task_etas:{T002:forecast},task_groups:[{group:'Research',tasks:[{id:'T002',name:'Sample task',description:'A concrete goal',deliverable:'A concrete deliverable'}]}],runs:[{task_id:'T002',note:'Reference preparation is running'}]};
 context.renderTasks(overview,[{id:'T002',title:'Sample task',status:'196/320'}]);
 const short=nodes.find(n=>n.className==='tt-text');assert.equal(short.textContent,'196/320 · 暂停');
 assert.deepEqual(texts,['A concrete goal','A concrete deliverable','Reference preparation is running']);
 assert.deepEqual(nodes.filter(n=>n.className==='task-detail-label').map(n=>n.textContent),['目标：','交付：','现在：']);
 const bar=nodes.find(n=>n.className==='tt-bar');assert.equal(bar.attributes['aria-hidden'],'true');assert.equal(bar.children[0].style.width,'61.3%');
 const row=nodes.find(n=>n.dataset.key==='task-title-T002');assert.equal(row.tagName,'details');assert.ok(row.querySelector('summary'));row.open=true;row.handlers.toggle();
 context.renderTasks(overview,[{id:'T002',title:'Sample task',status:'196/320'}]);
 assert.equal(nodes.filter(n=>n.dataset.key==='task-title-T002').at(-1).open,true);
});
test('three-line details omit duplicate progress and keep generic metadata',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
 const html=fs.readFileSync(path.join(__dirname,'../board/index.html'),'utf8');
 const code=html.slice(html.indexOf('function taskDetailRows('),html.indexOf('function taskEntries('));
 const context={EtaView:{task:()=> '12/60'},CODE:/T\d+/g};vm.runInNewContext(code,context);
 const meta={description:'Goal',deliverable:'Deliverable'};
 const rows=context.taskDetailRows({id:'T002',status:'12/60 · 约06:14'},meta,{runs:[{task_id:'T002',note:'12/60 · 约06:14'}]});
 assert.deepEqual(Array.from(rows,row=>row.label),['目标','交付']);
 const current=context.taskDetailRows({id:'T002',status:'进行中'},meta,{runs:[{task_id:'T002',note:'Original output is ready'}]});
 assert.deepEqual(Array.from(current,row=>row.label),['目标','交付','现在']);
 assert.equal(current[2].text,'Original output is ready');
});
