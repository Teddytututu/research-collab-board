const test=require('node:test'),assert=require('node:assert/strict');
const eta=require('../board/eta-view.js');
const now=new Date('2030-01-02T10:00:00+08:00');
test('three explicit clock forms use the board day',()=>{
 for(const [status,expected] of [['1/6 · 约 12:00','1/6 · 约 12:00'],['1/6 · 约 明天 08:00','1/6 · 明早 08:00'],['1/6 · 约 01-04 16:00','1/6 · 约 01-04']])
  assert.equal(eta.task({status},null,now),expected);
});
test('declared clock replaces placeholder condition and preserves lifecycle states',()=>{
 const status='1/6 · 约 12:00';
 assert.equal(eta.task({status,eta:{mode:'conditional',short_condition:'本轮估时'}},null,now),'1/6 · 约 12:00');
 assert.equal(eta.task({status,eta:{mode:'paused'}},null,now),'1/6 · 暂停');
 assert.equal(eta.task({status:'delivered · awaiting review'},null,now),'已交');
 assert.equal(eta.task({status:'stopped: 1/6',current_stage:{done:1,total:6}},null,now),'1/6 · 已停');
 assert.equal(eta.task({status:'1/6 · 约 09:00'},null,now),'1/6');
 assert.equal(eta.task({status:'1/6 · 约 25:00'},null,now),'1/6');
});
