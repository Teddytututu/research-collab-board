const test=require('node:test'),assert=require('node:assert/strict');
const view=require('../board/lifecycle-view.js');
test('task tags follow state rather than defaulting to running',()=>{
 for(const [status,label] of [['2/5','在跑'],['queued: inputs ready','排队'],['条件满足就开工','排队'],['stopped: merged','已停'],['delivered · awaiting review','已交'],['blocked: waiting for lead','卡住'],['daily: tomorrow','每日'],['排队：等输入','排队'],['已交 · 待验收','已交'],['每日：今天已交','每日'],['调查输入','排队']])
  assert.equal(view.taskState({status}).label,label,status);
 assert.equal(view.taskState({status:'accepted: done'}).done,true);
 assert.equal(view.taskState({status:'已停：取消'}).done,true);
});
test('patrol uses next deadline plus fifteen minutes and handles missing times',()=>{
 const row={at:'2030-01-01T10:00:00Z',next_at:'2030-01-01T10:30:00Z',note:'Compared cases',open_issues:2};
 assert.equal(view.patrolState(row,new Date('2030-01-01T10:45:00Z')).overdue,false);
 assert.equal(view.patrolState(row,new Date('2030-01-01T10:45:01Z')).overdue,true);
 assert.equal(view.patrolState({},new Date()).label,'待巡检');
 assert.equal(view.patrolState({next_at:'invalid'},new Date()).overdue,false);
});
test('patrol DOM has both roles, explicit overdue text and safe notes',()=>{
 const vm=require('node:vm'),fs=require('node:fs');
 class Element{constructor(tag){this.tag=tag;this.children=[];this.attributes={};}append(...nodes){this.children.push(...nodes);}setAttribute(k,v){this.attributes[k]=v;}}
 const context={document:{createElement:tag=>new Element(tag)}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../board/lifecycle-view.js'),'utf8'),context);
 const container=new Element('div');context.LifecycleView.renderPatrols(container,{patrols:{GPT:{at:'2030-01-01T10:00:00Z',next_at:'2030-01-01T10:30:00Z',note:'<img onerror=alert(1)>'}},flow_issues:[{owner:'GPT',code:'running_stale'}]},new Date('2030-01-01T10:46:00Z'));
 const [lead,executor]=container.children[0].children;
 assert.equal(lead.children[0].textContent,'Claude');assert.equal(executor.children[0].textContent,'GPT');
 assert.match(executor.className,/overdue/);assert.equal(executor.children[2].textContent,'巡检超时');assert.equal(executor.children[3].textContent,'流程问题 1');
 assert.equal(executor.children[4].textContent,'<img onerror=alert(1)>');
});
