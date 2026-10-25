/* One project user; assistant roles are provided by the local project scripts. */
window.BoardIdentity=(()=>{
 const api={me:{id:'owner'},accounts:[],channel:'main'};
 api.name=id=>api.accounts.find(a=>a.id===id)?.display_name || id;
 api.avatarURL=(id,file)=>file?.startsWith('generated/')?'/'+file:'/art/'+file;
 let pending=null,signature=null,timer=null,firstSuccess;
 const firstAccounts=new Promise(resolve=>{firstSuccess=resolve;});
 const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.assign(Object.create(null),...Object.keys(value).sort().map(k=>({[k]:canonical(value[k])}))):value;
 api.refreshAccounts=()=>{
  if(pending)return pending;
  pending=(async()=>{
   const abort=typeof AbortController==='function'?new AbortController():null;
   const timeout=abort&&typeof setTimeout==='function'?setTimeout(()=>abort.abort(),10000):null;
   try{
    const r=await fetch('/api/accounts',{cache:'no-store',...(abort?{signal:abort.signal}:{})});
    if(!r.ok){const error=new Error('Open the paired project page');error.status=r.status;throw error;}
    const rows=(await r.json()).accounts;
    if(!Array.isArray(rows)||rows.some(a=>!a||typeof a.id!=='string')||new Set(rows.map(a=>a.id)).size!==rows.length)throw new Error('A valid account snapshot is required');
    const next=JSON.stringify(canonical([...rows].sort((a,b)=>a.id.localeCompare(b.id))));
    if(next!==signature){api.accounts=rows;signature=next;window.dispatchEvent(new Event('accountschange'));}
    firstSuccess();return api.accounts;
   }finally{if(timeout!==null)clearTimeout(timeout);}
  })().finally(()=>{pending=null;});
  return pending;
 };
 const refreshVisible=()=>{if(typeof document!=='undefined'&&document.hidden)return;return api.refreshAccounts().catch(()=>{});};
 const start=()=>{if(timer===null&&typeof setInterval==='function')timer=setInterval(refreshVisible,15000);};
 window.addEventListener?.('focus',refreshVisible);
 window.addEventListener?.('pagehide',()=>{if(timer!==null){clearInterval(timer);timer=null;}});
 window.addEventListener?.('pageshow',()=>{start();return refreshVisible();});
 if(typeof document!=='undefined')document.addEventListener?.('visibilitychange',refreshVisible);
 api.ready=(async()=>{
  const r=await fetch('/api/me');if(!r.ok)throw new Error('Pair this device on your computer');api.me=await r.json();start();
  try{await api.refreshAccounts();}catch(error){if(error.status===401||error.status===403)throw error;}
  await firstAccounts;
 })();
 return api;
})();
