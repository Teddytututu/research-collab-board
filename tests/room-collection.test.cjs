const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function helpers(){
  const calls=[];
  const document={addEventListener(){},createElement:tag=>({tag,children:[],append(...nodes){this.children.push(...nodes);}})};
  const context={window:{},document,fetch:(url)=>{calls.push(url);throw Error('Unexpected network call');}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../board/room-extras.js'),'utf8'),context);
  return {api:context.window.RoomExtras,calls};
}
test('archive channels stay hidden while research, study and attachments retain original records',()=>{
  const {api,calls}=helpers();
  const rows=[{id:'research',channel:'main'},{id:'course',channel:'study',files:[{id:'attachment',name:'notes.txt',bytes:2048}]},{id:'old-save',channel:'files'},{id:'old-library',channel:'library'}];
  const before=JSON.stringify(rows),visible=api.discussionItems(rows);
  assert.deepEqual(Array.from(visible,row=>row.id),['research','course']);
  assert.equal(visible[1],rows[1]);assert.equal(JSON.stringify(rows),before);
  assert.equal(api.favorite,undefined);assert.equal(calls.length,0);
});
test('normal attachment links work independently from retired collection UI',()=>{
  const {api,calls}=helpers(),link=api.fileLink({id:'notes-1',name:'notes.txt',bytes:2048});
  assert.equal(link.tag,'a');assert.equal(link.href,'/chat-file/notes-1');assert.equal(link.download,'notes.txt');
  assert.deepEqual(Array.from(link.children,n=>n.textContent),['↧','notes.txt','2.0 KB']);
  assert.equal(calls.length,0);
});
