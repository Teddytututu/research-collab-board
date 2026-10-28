/* Current moods decorate portraits; original account portraits remain fallback assets. */
window.AvatarMoods = (() => {
  'use strict';
  let rows=[],actors={},moods={},picker,portrait,opener,scheduled=false,openPeerAfterClose=null;
  const el=(tag,cls)=>{const node=document.createElement(tag);if(cls)node.className=cls;return node;};
  const roleOf=id=>actors[id] || null;
  const who=()=>window.BoardIdentity?.me?.id;
  function resolve(id,value){
    const role=roleOf(id);if(!role||!value)return null;
    const own=rows.filter(row=>row.role===role);
    const direct=own.find(row=>row.key===value);if(direct)return direct;
    const explicit=/^(?:expression|表情):/.test(value),name=String(value).replace(/^(?:expression|表情):/,'');
    return (!explicit&&own.find(row=>row.aliases?.includes(name)&&row.file.endsWith('.webp'))) ||
      (!explicit&&own.find(row=>row.aliases?.includes(name))) ||
      own.find(row=>(!explicit||row.collection==='original-60')&&(row.name===name||row.label===name)) || null;
  }
  const current=id=>resolve(id,moods[roleOf(id)]?.mood);
  function crop(image,row){
    const [x,y,side]=row.avatar_crop||[0,0,row.width||1254];
    Object.assign(image.style,{position:'absolute',maxWidth:'none',width:((row.width||1254)/side*100)+'%',
      height:((row.height||1254)/side*100)+'%',left:(-x/side*100)+'%',top:(-y/side*100)+'%',objectFit:'fill',transform:'none'});
  }
  function thumbnail(row){
    const frame=el('span','character-reaction-face'),image=el('img');image.alt='';image.loading='lazy';image.src=row.src||row.url;
    if(row.alpha_bbox){
      const [x0,y0,x1,y1]=row.alpha_bbox,w=x1-x0,h=y1-y0,scale=24/Math.max(w,h);
      Object.assign(image.style,{position:'absolute',width:row.width*scale+'px',height:row.height*scale+'px',
        left:((24-w*scale)/2-x0*scale)+'px',top:((24-h*scale)/2-y0*scale)+'px',maxWidth:'none'});
    }else Object.assign(image.style,{width:'24px',height:'24px',objectFit:'contain'});
    frame.append(image);return frame;
  }
  function decorate(){
    scheduled=false;
    for(const button of document.querySelectorAll('.room-avatar[data-mention-id],.brand-person[data-character],[data-avatar-id]')){
      const id=button.dataset.mentionId||button.dataset.character||button.dataset.avatarId,row=current(id);
      const existing=button.querySelector(':scope > .mood-avatar-face');
      if(!row){existing?.remove();button.classList.remove('has-avatar-mood');continue;}
      if(existing?.dataset.expression===row.key)continue;
      existing?.remove();
      const frame=el('span','mood-avatar-face');frame.dataset.expression=row.key;frame.setAttribute('aria-hidden','true');
      const image=el('img','mood-avatar-image');image.alt='';image.decoding='async';crop(image,row);
      image.onerror=()=>{frame.remove();button.classList.remove('has-avatar-mood');};
      image.src=row.url;frame.append(image);button.append(frame);button.classList.add('has-avatar-mood');
      button.dataset.mood=row.key;
      if(button.matches('.room-avatar,.brand-person'))button.setAttribute('aria-label',id===who()?'选择自己的心情表情':'查看'+(BoardIdentity.name(id)||id)+'的完整表情');
    }
    const claude=Object.keys(actors).find(id=>actors[id]==='claude'),row=current(claude);
    if(row)document.documentElement.style.setProperty('--mood','url("'+row.url+'")');
    document.querySelectorAll('[data-room-mood-sticker],.room-mood-sticker').forEach(node=>node.remove());
  }
  function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(decorate);}}
  function update(value){
    const overview=value?.overview||value||{};
    for(const [id,role] of Object.entries(actors)){
      const record=overview[id.toLowerCase()+'_mood'];if(record)moods[role]=record;
    }
    schedule();
  }
  function closePicker(){if(picker?.open)picker.close();}
  async function save(row){
    const response=await fetch('/api/mood',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mood:row.key})});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'请选择自己的表情。');
    moods[roleOf(who())]=data;schedule();closePicker();
  }
  function openPicker(trigger){
    const own=rows.filter(row=>row.role===roleOf(who()));if(!own.length)return;
    if(!picker){
      picker=el('dialog','avatar-mood-picker');picker.setAttribute('aria-label','选择自己的心情表情');
      picker.addEventListener('click',event=>{if(event.target===picker){const r=picker.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closePicker();}});
      picker.addEventListener('close',()=>opener?.isConnected&&opener.focus({preventScroll:true}));document.body.append(picker);
    }
    opener=trigger;picker.replaceChildren();
    const grid=el('div','avatar-mood-grid'),status=el('p','avatar-mood-status');status.setAttribute('role','status');
    for(const row of own){
      const button=el('button','avatar-mood-option');button.type='button';button.dataset.expression=row.key;
      button.title=row.label;button.setAttribute('aria-label',row.label);button.setAttribute('aria-pressed',String(current(who())?.key===row.key));
      const frame=el('span','avatar-mood-preview'),image=el('img');image.alt='';image.loading='eager';image.src=row.url;crop(image,row);frame.append(image);button.append(frame);
      button.onclick=async()=>{grid.querySelectorAll('button').forEach(n=>n.disabled=true);try{await save(row);}catch(error){status.textContent=error.message;}finally{grid.querySelectorAll('button').forEach(n=>n.disabled=false);}};
      grid.append(button);
    }
    picker.append(grid,status);picker.showModal();
    const box=trigger.getBoundingClientRect(),width=picker.offsetWidth,height=picker.offsetHeight;
    picker.style.left=Math.max(8,Math.min(box.left,innerWidth-width-8))+'px';
    picker.style.top=Math.max(8,Math.min(box.bottom+6,innerHeight-height-8))+'px';
    grid.querySelector('button[aria-pressed="true"],button')?.focus({preventScroll:true});
  }
  function showPortrait(id,trigger){
    const account=BoardIdentity.accounts.find(a=>a.id===id),row=current(id);
    const source=row?.url||(account?.avatar&&BoardIdentity.avatarURL(id,account.avatar.full||account.avatar.file));if(!source)return;
    if(!portrait){
      portrait=el('dialog','avatar-mood-portrait');portrait.setAttribute('aria-label','查看完整表情');
      const close=el('button');close.type='button';close.textContent='关闭';close.onclick=()=>portrait.close();
      const peer=el('button','avatar-mood-private');peer.type='button';peer.onclick=()=>{openPeerAfterClose={id:portrait.dataset.peer,trigger:opener};portrait.close();};
      const header=el('div','avatar-mood-portrait-actions');header.append(peer,close);
      portrait.append(header,el('img'));document.body.append(portrait);
      portrait.addEventListener('click',event=>{if(event.target===portrait)portrait.close();});
      portrait.addEventListener('close',()=>{if(openPeerAfterClose){const next=openPeerAfterClose;openPeerAfterClose=null;RoomPrivateChat.open(next.id,next.trigger);}else if(opener?.isConnected)opener.focus({preventScroll:true});});
    }
    portrait.dataset.peer=id;
    const peer=portrait.querySelector('.avatar-mood-private');peer.textContent='私聊 '+BoardIdentity.name(id);
    peer.hidden=!['claude','gpt'].includes(roleOf(id))||!window.RoomPrivateChat||who()==='guest';
    opener=trigger;const image=portrait.querySelector('img');image.src=source;image.alt=(account?.display_name||id)+' · '+(row?.label||'完整头像');portrait.showModal();
  }
  document.addEventListener('click',event=>{
    if(event.defaultPrevented)return;
    const target=event.target.closest?.('.room-avatar[data-mention-id],.brand-person[data-character]');
    if(!target)return;const id=target.dataset.mentionId||target.dataset.character;
    if(!roleOf(id))return;
    event.preventDefault();event.stopImmediatePropagation();id===who()?openPicker(target):showPortrait(id,target);
  },true);
  const ready=(async()=>{
    await BoardIdentity.ready;
    const response=await fetch('/api/expressions',{cache:'no-store'});if(!response.ok)throw new Error('表情正在准备。');
    const data=await response.json();rows=data.items;actors=data.actors;moods=data.moods||{};
    window.RoomExtras?.setCharacterCatalog?.(rows);
    new MutationObserver(schedule).observe(document.body,{subtree:true,childList:true});
    window.addEventListener('overview',event=>update(event.detail));window.addEventListener('identitychange',schedule);
    decorate();return data;
  })();
  ready.catch(()=>{});
  return {ready,resolve,current,decorate,openPicker,showPortrait,thumbnail};
})();
