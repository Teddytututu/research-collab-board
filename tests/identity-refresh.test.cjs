const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('board/identity.js','utf8');
function harness(initialFail=false){
 const listeners={},documentListeners={},intervals=new Map(),timeouts=new Map(),events=[];let serial=0,calls=0;
 const h={data:[{id:'GPT',display_name:'GPT',avatar:'avatar-gpt.svg'},{id:'Claude',display_name:'Claude',avatar:'avatar-claude.svg'}]};
 h.handler=async()=>{if(initialFail){initialFail=false;throw Error('temporary network error');}return {ok:true,json:async()=>({accounts:JSON.parse(JSON.stringify(h.data))})};};
 const window={dispatchEvent:e=>events.push(e),addEventListener:(t,fn)=>listeners[t]=fn};
 const document={hidden:false,addEventListener:(t,fn)=>documentListeners[t]=fn};
 const context={window,document,AbortController,Event:class{constructor(type){this.type=type;}},CustomEvent:class{},
  setInterval:(fn,ms)=>{const id=++serial;intervals.set(id,{fn,ms});return id;},clearInterval:id=>intervals.delete(id),
  setTimeout:(fn,ms)=>{const id=++serial;timeouts.set(id,{fn,ms});return id;},clearTimeout:id=>timeouts.delete(id),
  fetch:async(url,options)=>{if(url==='/api/me')return {ok:true,json:async()=>({id:'owner'})};calls++;h.options=options;return h.handler(options);}};
 vm.runInNewContext(source,context);return Object.assign(h,{id:window.BoardIdentity,events,document,intervals,timeouts,
  calls:()=>calls,fire:t=>listeners[t]?.(),visibility:()=>documentListeners.visibilitychange?.(),tick:()=>[...intervals.values()][0]?.fn()});
}
test('same document adopts deployed PNG and emits exactly one change',async()=>{const h=harness();await h.id.ready;const before=h.events.length;h.data[0].avatar='generated/GPT/avatar.png';await h.tick();assert.equal(h.id.accounts[0].avatar,'generated/GPT/avatar.png');assert.equal(h.events.length,before+1);await h.tick();assert.equal(h.events.length,before+1);assert.equal(h.options.cache,'no-store');});
test('equivalent row/key ordering emits zero repeated changes',async()=>{const h=harness();await h.id.ready;const before=h.events.length;h.data=h.data.reverse().map(a=>({avatar:a.avatar,display_name:a.display_name,id:a.id}));await h.id.refreshAccounts();assert.equal(h.events.length,before);});
test('overlapping refreshes share a single network request',async()=>{const h=harness();await h.id.ready;let finish;h.handler=()=>new Promise(resolve=>finish=resolve);const before=h.calls(),a=h.id.refreshAccounts(),b=h.id.refreshAccounts();assert.equal(a,b);assert.equal(h.calls(),before+1);finish({ok:true,json:async()=>({accounts:h.data})});await a;});
test('temporary failure preserves last good accounts and allows later retry',async()=>{const h=harness();await h.id.ready;const before=h.events.length;h.handler=async()=>{throw Error('offline');};await assert.rejects(h.id.refreshAccounts());assert.equal(h.id.accounts[0].avatar,'avatar-gpt.svg');assert.equal(h.events.length,before);h.handler=async()=>({ok:true,json:async()=>({accounts:[{id:'GPT',avatar:'generated/GPT/avatar.png'}]})});await h.tick();assert.equal(h.id.accounts[0].avatar,'generated/GPT/avatar.png');});
test('invalid and failed responses preserve the cached identity',async()=>{const h=harness();await h.id.ready;for(const response of [{ok:false,status:503},{ok:true,json:async()=>({accounts:null})}]){h.handler=async()=>response;await assert.rejects(h.id.refreshAccounts());assert.equal(h.id.accounts.length,2);}});
test('hidden pages stay quiet and focus resumes refresh',async()=>{const h=harness();await h.id.ready;h.document.hidden=true;const before=h.calls();await h.tick();assert.equal(h.calls(),before);h.document.hidden=false;await h.visibility();assert.equal(h.calls(),before+1);});
test('pagehide stops polling and pageshow restores one timer',async()=>{const h=harness();await h.id.ready;assert.equal(h.intervals.size,1);h.fire('pagehide');assert.equal(h.intervals.size,0);await h.fire('pageshow');assert.equal(h.intervals.size,1);await h.fire('pageshow');assert.equal(h.intervals.size,1);});
test('initial transient accounts failure recovers readiness on a later poll',async()=>{const h=harness(true);await new Promise(resolve=>setImmediate(resolve));await h.tick();await h.id.ready;assert.equal(h.id.accounts.length,2);});
test('stalled requests time out and release the shared request slot',async()=>{const h=harness();await h.id.ready;h.handler=options=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timeout'))));const pending=h.id.refreshAccounts();assert.equal(h.timeouts.size,1);[...h.timeouts.values()][0].fn();await assert.rejects(pending);assert.equal(h.timeouts.size,0);h.handler=async()=>({ok:true,json:async()=>({accounts:h.data})});await h.id.refreshAccounts();});
