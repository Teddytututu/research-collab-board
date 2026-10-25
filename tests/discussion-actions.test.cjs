const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assets=fs.existsSync(path.join(__dirname,'../board/room-extras.js'))?path.join(__dirname,'../board'):path.join(__dirname,'..');
function harness({guest=false}={}){
 let document,now=0,serial=0;const timers=new Map(),calls=[];
 function matches(node,selector){
  return selector.split(',').some(part=>{part=part.trim();if(part.startsWith('[')){const m=part.match(/^\[([^=\]]+)(?:=["']?([^"'\]]+)["']?)?\]$/);return m&&(m[1]==='data-discussion-id'?!!node.dataset.discussionId:m[2]===undefined?node.attributes[m[1]]!==undefined:node.attributes[m[1]]===m[2]);}
   if(part.startsWith('.'))return part.slice(1).split('.').every(c=>node.classList.contains(c));if(part.startsWith('#'))return node.id===part.slice(1);return node.tagName===part.toUpperCase();});
 }
 class Element{
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.parentNode=null;this.attributes={};this.dataset={};this.style={};this.listeners={};this.className='';this._text='';this.hidden=false;this.open=false;this.scrollHeight=400;this.clientHeight=400;this.scrollTop=0;this.offsetTop=0;this.offsetHeight=40;this.offsetWidth=200;
   this.classList={contains:c=>this.className.split(/\s+/).includes(c),add:(...cs)=>{this.className=[...new Set([...this.className.split(/\s+/).filter(Boolean),...cs])].join(' ');},remove:(...cs)=>{this.className=this.className.split(/\s+/).filter(c=>!cs.includes(c)).join(' ');},toggle:(c,on)=>{on=on??!this.classList.contains(c);on?this.classList.add(c):this.classList.remove(c);return on;}};
  }
  get textContent(){return this._text+this.children.map(c=>c.textContent||'').join('');}set textContent(value){this._text=String(value);this.children=[];}
  get isConnected(){return this===document.body||!!this.parentNode?.isConnected;}
  append(...children){for(const child of children){child.remove?.();this.children.push(child);child.parentNode=this;}}
  prepend(...children){for(const child of children.reverse()){child.remove?.();this.children.unshift(child);child.parentNode=this;}}
  replaceChildren(...children){for(const c of this.children)c.parentNode=null;this.children=[];this._text='';this.append(...children);}
  remove(){if(this.parentNode){this.parentNode.children=this.parentNode.children.filter(c=>c!==this);this.parentNode=null;}}
  replaceWith(next){const p=this.parentNode;if(!p)return;const at=p.children.indexOf(this);this.parentNode=null;next.parentNode=p;p.children[at]=next;}
  setAttribute(key,value){this.attributes[key]=String(value);if(key==='id')this.id=String(value);}
  getAttribute(key){return this.attributes[key]??null;}removeAttribute(key){delete this.attributes[key];if(key==='src')this.src='';}
  contains(node){return node===this||this.children.some(c=>c.contains?.(node));}
  closest(selector){for(let n=this;n;n=n.parentNode)if(matches(n,selector))return n;return null;}
  querySelectorAll(selector){const result=[];for(const c of this.children){if(matches(c,selector))result.push(c);result.push(...(c.querySelectorAll?.(selector)||[]));}return result;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  addEventListener(type,fn,options){(this.listeners[type]||=[]).push({fn,once:options?.once});}
  emit(type,properties={}){const event={type,target:this,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;},stopImmediatePropagation(){this.immediate=true;},...properties};
   for(const entry of [...this.listeners[type]||[]]){entry.fn(event);if(entry.once)this.listeners[type]=this.listeners[type].filter(e=>e!==entry);if(event.immediate)break;}
   if(!event.immediate)this['on'+type]?.(event);return event;
  }
  click(){return this.emit('click');}focus(){document.activeElement=this;}showModal(){this.open=true;}close(){this.open=false;this.emit('close');}
  getBoundingClientRect(){return {left:20,right:220,top:20,bottom:52,width:200,height:100};}getClientRects(){return [{}];}scrollIntoView(){}
 }
 document={listeners:{},activeElement:null,visibilityState:'visible',documentElement:{clientWidth:800,clientHeight:600},createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text}),addEventListener(type,fn){(this.listeners[type]||=[]).push(fn);},emit(type,p={}){const e={target:this,preventDefault(){this.defaultPrevented=true;},stopPropagation(){},...p};for(const f of this.listeners[type]||[])f(e);return e;},querySelector:s=>document.body.querySelector(s),querySelectorAll:s=>document.body.querySelectorAll(s)};
 document.body=new Element('body');document.activeElement=document.body;
 const accounts=[{id:'owner',display_name:'Tester',avatar:{file:'avatar-user.svg'}},{id:'Claude',display_name:'Claude',avatar:{file:'avatar-claude.svg'}}];
 const identity={me:{id:guest?'guest':'owner',conversations:true},accounts,channel:'main',name:id=>accounts.find(a=>a.id===id)?.display_name||id,avatarURL:(id,file)=>'/art/'+file};
 const context={window:{},document,BoardIdentity:identity,RoomMarkdown:{render:text=>{const n=new Element('div');n.className='room-markdown';n.textContent=text;return n;}},innerWidth:800,
  fetch:async(url,options)=>{calls.push({url,payload:JSON.parse(options?.body||'{}')});return {ok:true,json:async()=>url==='/api/discussion/delete'?{message_id:'m1',deleted:true,deleted_by:'owner',deleted_at:'2030-01-01T00:00:00Z'}:{reactions:[]}};},
  setTimeout:(fn,delay)=>{const id=++serial;timers.set(id,{fn,at:now+delay});return id;},clearTimeout:id=>timers.delete(id),localStorage:{getItem:()=>null,setItem(){}},console};
 vm.runInNewContext(fs.readFileSync(path.join(assets,'room-extras.js'),'utf8'),context);context.RoomExtras=context.window.RoomExtras;
 const h={document,identity,calls,api:context.RoomExtras,Element,context,advance(ms){now+=ms;let due;while((due=[...timers].find(([,v])=>v.at<=now))){timers.delete(due[0]);due[1].fn();}},escape(){const e=document.emit('keydown',{key:'Escape'});if(!e.defaultPrevented){const d=document.querySelector('dialog');if(d?.open){const cancel=d.emit('cancel');if(!cancel.defaultPrevented)d.close();}}}};
 h.flush=()=>new Promise(resolve=>setImmediate(resolve));
 h.article=()=>{const n=new Element('article');n.dataset.discussionId='m1';document.body.append(n);return n;};
 h.loadDiscussion=()=>{
  for(const id of ['room-threads','room-status','room-latest','room-reply-context','room-reply-label','room-submit','room-text']){const n=new Element('div');n.id=id;document.body.append(n);}
  let source=fs.readFileSync(path.join(assets,'discussion.js'),'utf8');source=source.replace('return {init,update,cleanText,jumpTo};','return {init,update,cleanText,jumpTo,_message:message,_set:(rows)=>{items=rows;draft={};}};');
  vm.runInNewContext(source,context);return context.window.DiscussionRoom;
 };
 return h;
}
const actor=n=>({id:'person'+n,display_name:'Person '+n,avatar:{file:'avatar-user.svg'}});
test('deleted projection clears every content channel while preserving the source',()=>{
 const h=harness(),row={id:'m1',deleted:true,body:'private',images:['a.png'],files:[{name:'private.pdf'}],sticker:{id:'frog'},reference:{body:'private'},reactions:[{}],can_delete:true};const before=JSON.stringify(row),out=h.api.projectDeleted(row);
 assert.equal(out.body,'');assert.equal(out.images.length+out.files.length+out.reactions.length,0);assert.equal(out.sticker,null);assert.equal(out.reference,null);assert.equal(out.can_delete,false);assert.equal(JSON.stringify(row),before);
 assert.equal(h.api.deletionText({...row,deleted_by:'owner',delete_action:'withdraw'}),'Tester 撤回了一条消息');
 assert.equal(h.api.deletionText({...row,deleted_by:'Claude',delete_action:'delete'}),'Claude 删除了一条消息');
});
test('a deleted message renders only a marker and replies redact its quote',()=>{
 const h=harness(),room=h.loadDiscussion(),deleted={id:'m1',author:'Claude',deleted:true,deleted_by:'owner',delete_action:'delete',body:'SECRET',images:['a'.repeat(32)+'.png'],files:[{id:'x',name:'SECRET.pdf'}]};
 const tombstone=room._message(deleted,new Map());assert.match(tombstone.textContent,/删除了一条消息/);assert.doesNotMatch(tombstone.textContent,/SECRET/);assert.equal(tombstone.querySelectorAll('.room-images,.room-file,.room-reactions,.room-actions-button').length,0);
 const reply=room._message({id:'m2',author:'Claude',body:'Reply',parent_id:'m1'},new Map([['m1',deleted]]));assert.match(reply.querySelector('.room-quote').textContent,/原消息已撤回/);assert.doesNotMatch(reply.querySelector('.room-quote').textContent,/SECRET/);
});
test('server can_delete exclusively controls deletion entry and guests stay read-only',()=>{
 for(const guest of [false,true]){const h=harness({guest}),a=h.article();const menu=h.api.messageActions({id:'m1',can_delete:true},a,{reply(){}});if(guest){assert.equal(menu,null);continue;}a.append(menu);menu.click();assert.ok(h.document.querySelector('.room-menu-delete'));h.api.closeMenus();const denied=h.api.messageActions({id:'m2',can_delete:false},a,{reply(){}});a.append(denied);denied.click();assert.equal(h.document.querySelector('.room-menu-delete'),null);}
});
test('administrator and author actions have distinct labels before a tombstone exists',()=>{
 const h=harness();assert.equal(h.api.deleteAction({author:'Claude',delete_action:'withdraw'}),'delete');assert.equal(h.api.deleteAction({author:'owner',delete_action:'withdraw'}),'withdraw');
 const a=h.article(),menu=h.api.messageActions({id:'m1',author:'Claude',can_delete:true,delete_action:'withdraw'},a,{reply(){}});a.append(menu);menu.click();assert.equal(h.document.querySelector('.room-menu-delete').textContent,'管理员删除');
});
test('a projected deleted reference remains explicit when its parent is outside the loaded page',()=>{
 const h=harness(),room=h.loadDiscussion(),row=room._message({id:'m2',author:'Claude',body:'Follow up',parent_deleted:true,reference_text:'原消息已撤回'},new Map());assert.match(row.querySelector('.room-quote').textContent,/原消息已撤回/);assert.equal(row.querySelector('.room-quote').disabled,true);
});
test('delete requires confirmation, sends only the contracted payload and sanitizes its result',async()=>{
 const h=harness(),a=h.article();let changed;const menu=h.api.messageActions({id:'m1',channel:'main',can_delete:true,delete_action:'delete',body:'SECRET'},a,{reply(){},failed:assert.fail,deleted:value=>changed=value});a.append(menu);menu.click();h.document.querySelector('.room-menu-delete').click();assert.equal(h.calls.length,0);assert.equal(h.document.activeElement.className,'room-delete-cancel');h.document.querySelector('.room-delete-confirm').click();await h.flush();assert.equal(h.calls.length,1);assert.equal(h.calls[0].url,'/api/discussion/delete');assert.deepEqual(h.calls[0].payload,{message_id:'m1',channel:'main'});assert.equal(changed.deleted,true);assert.equal(changed.body,'');
});
test('cancel and native Escape preserve the message and return focus',async()=>{
 const h=harness(),a=h.article(),menu=h.api.messageActions({id:'m1',can_delete:true},a,{reply(){},failed:assert.fail,deleted:assert.fail});a.append(menu);
 for(const method of ['cancel','escape']){menu.click();h.document.querySelector('.room-menu-delete').click();method==='cancel'?h.document.querySelector('.room-delete-cancel').click():h.escape();await h.flush();assert.equal(h.calls.length,0);assert.equal(h.document.querySelector('dialog'),null);assert.equal(h.document.activeElement,menu);}
});
test('backend denial preserves the original message and reports the failure',async()=>{
 const h=harness(),a=h.article();let failed='';h.context.fetch=async()=>({ok:false,json:async()=>({error:'权限已更新'})});const menu=h.api.messageActions({id:'m1',body:'Keep me',can_delete:true},a,{reply(){},failed:value=>failed=value,deleted:assert.fail});a.append(menu);menu.click();h.document.querySelector('.room-menu-delete').click();h.document.querySelector('.room-delete-confirm').click();await h.flush();assert.equal(failed,'权限已更新');assert.ok(menu.isConnected);
});
test('menu supports arrows, Escape and an outside click',()=>{
 const h=harness(),a=h.article(),menu=h.api.messageActions({id:'m1',can_delete:true},a,{reply(){}});a.append(menu);menu.click();const panel=h.document.querySelector('.room-message-menu');assert.equal(h.document.activeElement.className,'room-menu-reply');panel.emit('keydown',{key:'ArrowDown'});assert.equal(h.document.activeElement.className,'room-menu-delete');h.escape();assert.equal(h.document.querySelector('.room-message-menu'),null);assert.equal(h.document.activeElement,menu);menu.click();h.document.emit('pointerdown',{target:h.document.body});assert.equal(h.document.querySelector('.room-message-menu'),null);
});
test('touch hold opens actions and movement cancels the gesture',()=>{
 const h=harness(),a=h.article(),bubble=new h.Element('div');a.append(bubble);a.append(h.api.messageActions({id:'m1',can_delete:true},a,{reply(){}}));a.emit('pointerdown',{target:bubble,pointerType:'touch',clientX:0,clientY:0});a.emit('pointermove',{clientX:30,clientY:0});h.advance(500);assert.equal(h.document.querySelector('.room-message-menu'),null);a.emit('pointerdown',{target:bubble,pointerType:'touch',clientX:0,clientY:0});h.advance(500);assert.ok(h.document.querySelector('.room-message-menu'));
});
test('reaction follows Telegram: up to three known actors show avatars only, more show a count, roster only on right click',()=>{
 const h=harness(),box=h.api.reactions({id:'m1',reactions:[{emoji:'👍',count:3,mine:true,actors:[1,2,3].map(actor)},{emoji:'😂',count:5,actors:[1,2,3,4,5].map(actor)}]},['👍','😂'],()=>{},assert.fail);h.document.body.append(box);const [b,c]=box.querySelectorAll('.room-reaction');assert.equal(b.querySelectorAll('.room-reaction-avatar').length,3);assert.equal(b.querySelector('.room-reaction-count'),null);assert.equal(b.getAttribute('aria-pressed'),'true');assert.ok(b.classList.contains('mine'));assert.equal(c.querySelectorAll('.room-reaction-avatar').length,0);assert.equal(c.querySelector('.room-reaction-count').textContent,'5');c.emit('mouseenter');c.emit('focus');assert.equal(h.document.querySelector('.room-reaction-actors'),null);c.emit('contextmenu');const panel=h.document.querySelector('.room-reaction-actors');assert.equal(panel.querySelectorAll('.room-reaction-person').length,5);assert.match(panel.textContent,/Person 5/);h.escape();assert.equal(h.document.querySelector('.room-reaction-actors'),null);
});
test('mine click cancels once; guest attribution remains viewable without posting',async()=>{
 for(const guest of [false,true]){const h=harness({guest}),box=h.api.reactions({id:'m1',reactions:[{emoji:'👍',count:1,mine:true,actors:[actor(1)]}]},['👍'],()=>{},assert.fail);h.document.body.append(box);box.querySelector('.room-reaction').click();await h.flush();assert.equal(h.calls.length,guest?0:1);if(!guest)assert.equal(h.calls[0].payload.active,false);else{assert.equal(box.querySelector('.room-reaction-add'),null);box.querySelector('.room-reaction').emit('contextmenu');assert.ok(h.document.querySelector('.room-reaction-actors'));}}
});
test('long press reveals reaction actors and suppresses its subsequent toggle',async()=>{
 const h=harness(),box=h.api.reactions({id:'m1',reactions:[{emoji:'👍',count:1,actors:[actor(1)]}]},['👍'],()=>{},assert.fail);h.document.body.append(box);const b=box.querySelector('.room-reaction');b.emit('pointerdown',{pointerType:'touch',clientX:5,clientY:5});h.advance(500);b.click();await h.flush();assert.ok(h.document.querySelector('.room-reaction-actors'));assert.equal(h.calls.length,0);
});
test('historical anonymous counts stay visible without invented actors',()=>{
 const h=harness(),box=h.api.reactions({id:'m1',reactions:[{emoji:'👍',count:8,mine:false}]},['👍'],()=>{},assert.fail);assert.equal(box.querySelector('.room-reaction-count').textContent,'8');assert.equal(box.querySelectorAll('.room-reaction-avatar').length,0);box.querySelector('.room-reaction').emit('mouseenter');assert.equal(h.document.querySelector('.room-reaction-actors'),null);
});
test('deleted messages expose no reaction control and stop grouping',()=>{
 const h=harness();assert.equal(h.api.reactions({deleted:true},[],()=>{},assert.fail).children.length,0);assert.equal(h.api.merge({author:'A',deleted:true},{author:'A'},null),false);
});
test('both themes and narrow layout retain attribution and tombstone rules',()=>{
 const css=fs.readFileSync(path.join(assets,'discussion.css'),'utf8')+fs.readFileSync(path.join(assets,'room-features.css'),'utf8');for(const marker of ['room-deleted-marker','room-message-menu','room-delete-dialog','room-reaction-avatar','room-reaction-actors','room-reaction.mine','html.theme-pink','@media(max-width:600px)'])assert.ok(css.includes(marker),marker);
});
