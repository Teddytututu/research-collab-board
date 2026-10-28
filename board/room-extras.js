
window.RoomExtras = (() => {
  const api = {};
  const el = (tag, cls, value) => { const n=document.createElement(tag); if(cls)n.className=cls; if(value!=null)n.textContent=value; return n; };
  const button = (label, cls) => { const n=el('button',cls,label); n.type='button'; return n; };
  const imageName = /^[a-f0-9]{32}\.(?:png|jpg|webp|gif)$/;
  api.mediaURL = name => typeof name==='string' && imageName.test(name) ? '/chat-img/'+name : null;
  const stickerAssets=new Map();
  api.stickerURL = (id,url) => {
    if(typeof id!=='string' || !/^[a-z][a-z0-9_-]{0,31}$/.test(id))return null;
    if(typeof url==='string' && /^\/room-stickers\/[a-z0-9_-]+\.(?:jpg|png|webp|gif)$/.test(url))stickerAssets.set(id,url);
    return stickerAssets.get(id) || null;
  };
  api.merge = (previous, current, boundary) => {
    if(!previous || previous.deleted || current.deleted || current.id===boundary || previous.author!==current.author || previous.channel!==current.channel)return false;
    const a=Date.parse(previous.created_at), b=Date.parse(current.created_at);
    return Number.isFinite(a) && Number.isFinite(b) && b>=a && b-a<=300000 && String(previous.created_at).slice(0,10)===String(current.created_at).slice(0,10);
  };
  api.visible = log => document.visibilityState==='visible' && log.getClientRects().length>0 && !log.closest('#msgs')?.classList.contains('collapsed');
  api.reader = (actor, channel='main') => {
    const key='room-read-v1:'+actor+':'+channel;
    let last=''; try{last=localStorage.getItem(key)||'';}catch(_){}
    const state={unread:new Set(), boundary:null, known:null, tail:null};
    state.sync = items => {
      state.tail=items.at(-1)?.id;
      const fresh=state.known ? items.filter(item=>!state.known.has(item.id)) : last && items.some(item=>item.id===last) ? items.slice(items.findIndex(item=>item.id===last)+1) : [];
      for(const item of fresh)if(item.author!==actor)state.unread.add(item.id);
      state.known=new Set(items.map(item=>item.id));
      state.unread=new Set([...state.unread].filter(id=>state.known.has(id)));
      if(!state.boundary || !state.known.has(state.boundary))state.boundary=items.find(item=>state.unread.has(item.id))?.id || null;
    };
    state.mark = () => { state.unread.clear(); if(state.tail)try{localStorage.setItem(key,state.tail);}catch(_){}; };
    return state;
  };
  async function post(url, payload) {
    const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json(); if(!response.ok)throw new Error(result.error || '请稍后重试。'); return result;
  }
  api.post=post;
  // T164: shared message actions and reaction attribution, driven by server permissions.
  api.readOnly = () => {
    const me=typeof BoardIdentity==='object'?BoardIdentity.me:null;
    return !me || me.id==='guest' || me.role==='guest' || me.is_guest===true || me.read_only===true || me.readonly===true;
  };
  api.projectDeleted = item => item?.deleted ? {...item,body:'',images:[],files:[],sticker:null,sticker_id:null,source:null,reference:null,reactions:[],can_delete:false} : item;
  api.deleteAction = item => item.deleted ? item.delete_action : item.author ? ((item.author_id||item.author)===BoardIdentity.me.id?'withdraw':'delete') : item.delete_action||'withdraw';
  api.deletionText = item => {
    const actor=item.deleted_by, id=typeof actor==='object'?actor?.id:actor;
    const name=typeof actor==='object'&&actor?.display_name?actor.display_name:(typeof BoardIdentity==='object'?BoardIdentity.name(id):id)||'管理员';
    return name+(item.delete_action==='delete'?' 删除了一条消息':' 撤回了一条消息');
  };
  let floating=null,restoringFocus=false;
  function restoreTrigger(trigger) {
    if(trigger?.isConnected){restoringFocus=true;try{trigger.focus({preventScroll:true});}finally{restoringFocus=false;}return;}
    const id=trigger?.closest?.('[data-discussion-id]')?.dataset.discussionId;
    const row=Array.from(document.querySelectorAll('[data-discussion-id]')).find(n=>n.dataset.discussionId===id);
    (row?.querySelector('.room-actions-button')||row)?.focus({preventScroll:true});
  }
  api.closeMenus = (restore=false) => {
    const current=floating;floating=null;
    if(current){current.panel.remove();current.trigger.setAttribute('aria-expanded','false');if(restore)restoreTrigger(current.trigger);}
    if(typeof openReactionPicker!=='undefined')openReactionPicker?.close(restore);
  };
  function floatPanel(trigger,panel,focus=false) {
    api.closeMenus();document.body.append(panel);floating={trigger,panel};trigger.setAttribute('aria-expanded','true');
    const rect=trigger.getBoundingClientRect(), bounds=panel.getBoundingClientRect();
    const width=document.documentElement.clientWidth, height=document.documentElement.clientHeight;
    panel.style.left=Math.max(8,Math.min(rect.left,width-bounds.width-8))+'px';
    panel.style.top=Math.max(8,Math.min(rect.bottom+4,height-bounds.height-8))+'px';
    if(focus)(panel.querySelector('button')||panel).focus({preventScroll:true});
    return panel;
  }
  document.addEventListener('pointerdown',event=>{
    if(floating&&!floating.panel.contains(event.target)&&!floating.trigger.contains(event.target))api.closeMenus();
  });
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&floating){event.preventDefault();event.stopPropagation();api.closeMenus(true);}
    else if(event.key==='Tab'&&floating)api.closeMenus(true);
  });
  document.addEventListener('scroll',event=>{if(floating&&!floating.panel.contains(event.target))api.closeMenus();},true);
  api.longPress = (target,show,ignore=()=>false) => {
    let timer=null,start=null,suppress=false;
    const clear=()=>{if(timer!==null)clearTimeout(timer);timer=null;};
    target.addEventListener('pointerdown',event=>{
      if(event.pointerType==='mouse'||ignore(event))return;
      clear();start={x:event.clientX,y:event.clientY};
      timer=setTimeout(()=>{timer=null;suppress=true;show(event);setTimeout(()=>{suppress=false;},800);},500);
    });
    target.addEventListener('pointermove',event=>{if(start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>10)clear();});
    for(const type of ['pointerup','pointercancel','pointerleave'])target.addEventListener(type,clear);
    target.addEventListener('click',event=>{if(suppress){event.preventDefault();event.stopImmediatePropagation();suppress=false;}},true);
  };
  function confirmDelete(item,trigger) {
    return new Promise(resolve=>{
      const action=api.deleteAction(item)==='delete'?'删除':'撤回', dialog=el('dialog','room-delete-dialog');
      dialog.setAttribute('aria-label','确认'+action+'消息');
      const title=el('h2',null,'确认'+action+'这条消息？'), text=el('p',null,'消息位置将显示'+action+'标记。');
      const actions=el('div','room-delete-dialog-actions'), cancel=button('保留消息','room-delete-cancel'), confirm=button('确认'+action,'room-delete-confirm');
      let approved=false;
      cancel.onclick=()=>dialog.close();confirm.onclick=()=>{approved=true;dialog.close();};
      dialog.addEventListener('cancel',()=>{approved=false;});
      dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
      dialog.addEventListener('close',()=>{dialog.remove();restoreTrigger(trigger);resolve(approved);},{once:true});
      actions.append(cancel,confirm);dialog.append(title,text,actions);document.body.append(dialog);dialog.showModal();cancel.focus({preventScroll:true});
    });
  }
  api.messageActions = (item,article,handlers) => {
    if(api.readOnly()||item.deleted)return null;
    const more=button('⋯','room-actions-button');more.setAttribute('aria-label','消息操作');more.setAttribute('aria-haspopup','menu');more.setAttribute('aria-expanded','false');
    let busy=false;
    const show=()=>{
      const menu=el('div','room-message-menu');menu.setAttribute('role','menu');menu.setAttribute('aria-label','消息操作');
      const reply=button('回复','room-menu-reply');reply.setAttribute('role','menuitem');reply.onclick=()=>{api.closeMenus();handlers.reply();};menu.append(reply);
      if(item.can_delete===true){
        const remove=button(api.deleteAction(item)==='delete'?'管理员删除':'撤回','room-menu-delete');remove.setAttribute('role','menuitem');
        remove.onclick=async()=>{
          if(busy)return;api.closeMenus();if(!await confirmDelete(item,more))return;
          if(api.readOnly()||item.deleted||item.can_delete!==true)return;
          busy=true;
          try{const result=await post('/api/discussion/delete',{message_id:item.id,...(item.channel?{channel:item.channel}:{})});
            if(result.deleted!==true||result.message_id!==item.id)throw new Error('消息状态更新中，请稍后重试。');
            handlers.deleted(api.projectDeleted({...item,...result,delete_action:api.deleteAction(item)}));
          }catch(error){handlers.failed(error.message);}finally{busy=false;}
        };menu.append(remove);
      }
      menu.addEventListener('keydown',event=>{
        const options=Array.from(menu.querySelectorAll('button')), at=options.indexOf(document.activeElement);
        if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
          event.preventDefault();const index=event.key==='Home'?0:event.key==='End'?options.length-1:(at+(event.key==='ArrowUp'?-1:1)+options.length)%options.length;options[index].focus();
        }else if(event.key==='Tab')api.closeMenus(true);
      });floatPanel(more,menu,true);
    };
    more.onclick=()=>floating?.trigger===more?api.closeMenus(true):show();
    article.addEventListener('contextmenu',event=>{if(event.target.closest('.room-reactions'))return;event.preventDefault();show();});
    api.longPress(article,show,event=>!!event.target.closest('button,a,input,textarea,.room-reactions'));
    return more;
  };
  function actorsFor(reaction) {
    const seen=new Set();return (Array.isArray(reaction.actors)?reaction.actors:[]).filter(actor=>actor&&typeof actor.id==='string'&&!seen.has(actor.id)&&seen.add(actor.id));
  }
  function actorFace(actor) {
    const frame=el('span','room-reaction-avatar');frame.setAttribute('aria-hidden','true');
    frame.dataset.avatarId=actor.id;
    frame.textContent=(actor.display_name||actor.id).slice(0,1);
    const asset=actor.avatar??(typeof BoardIdentity==='object'?BoardIdentity.accounts?.find(a=>a.id===actor.id)?.avatar:null);
    const file=typeof asset==='string'?asset:asset?.file;
    if(file&&typeof BoardIdentity==='object'){
      const url=BoardIdentity.avatarURL(actor.id,file);
      if(typeof url==='string'&&url.startsWith('/')&&!url.startsWith('//')){
        const image=el('img'),fallback=frame.textContent;image.alt='';image.src=url;image.loading='lazy';image.onerror=()=>{image.remove();frame.textContent=fallback;};
        if(asset?.position)image.style.objectPosition=asset.position;
        if(/^\d+(?:\.\d+)?%$/.test(asset?.cropWidth||'')&&/^-?\d+(?:\.\d+)?%$/.test(asset?.cropLeft||'')&&/^-?\d+(?:\.\d+)?%$/.test(asset?.cropTop||''))
          Object.assign(image.style,{position:'absolute',width:asset.cropWidth,height:'auto',left:asset.cropLeft,top:asset.cropTop,maxWidth:'none'});
        frame.textContent='';frame.append(image);
      }
    }return frame;
  }
  function reactionActors(trigger,reaction) {
    const actors=actorsFor(reaction);if(!actors.length)return;
    const show=(focus=false)=>{
      if(floating?.trigger===trigger)return;
      const panel=el('div','room-reaction-actors');panel.tabIndex=-1;panel.setAttribute('role','region');panel.setAttribute('aria-label','回应成员');
      for(const actor of actors){const row=el('div','room-reaction-person');row.append(actorFace(actor),el('span',null,actor.display_name||actor.id));panel.append(row);}
      const unknown=Math.max(0,reaction.count-actors.length);if(unknown)panel.append(el('p','room-reaction-unknown','另有 '+unknown+' 次历史回应'));
      floatPanel(trigger,panel,focus);
    };
    trigger.setAttribute('aria-haspopup','true');trigger.setAttribute('aria-expanded','false');
    api.longPress(trigger,()=>show(true));
    trigger.addEventListener('contextmenu',event=>{event.preventDefault();event.stopPropagation();show(true);});
  }
  // Archived collection channels stay on disk; the live timeline shows discussions.
  api.discussionItems = rows => (rows || []).filter(item => !['files','library'].includes(item.channel)).map(api.projectDeleted);
  api.fileLink = file => {
    const a=el('a','room-file');a.href='/chat-file/'+file.id;a.download=file.name;
    const size=file.size ?? file.bytes ?? 0;
    a.append(el('span',null,'↧'),el('strong',null,file.name),el('small',null,size<1024?size+' B':(size/1024).toFixed(1)+' KB'));
    return a;
  };

  // Unicode is ready immediately; the server supplies consented local PNGs.
  const unicodeFaces=[["👍", {label:"完成"}], ["❤️", {label:"关心"}], ["😂", {label:"微笑"}], ["🎉", {label:"庆祝"}], ["👀", {label:"审阅"}], ["💡", {label:"想法"}]];
  const reactionFaces=new Map(unicodeFaces);
  api.setReactionCatalog=rows=>{
    reactionFaces.clear();for(const [symbol,face] of unicodeFaces)reactionFaces.set(symbol,face);
    for(const row of rows)if(typeof row.key==='string' && /^(?:\/room-reactions\/[0-9]+\.png|\/expression-img\/[a-z0-9_-]+\.(?:webp|svg))$/.test(row.url))
      reactionFaces.set(row.key,{...row,label:row.label,src:row.url,fallback:row.fallback || '🙂',character:row.kind==='character'});
  };
  const reactionFace = symbol => {
    const face=reactionFaces.get(symbol);
    if(face?.character&&window.AvatarMoods?.thumbnail)return AvatarMoods.thumbnail(face);
    if(!face?.src)return el("span",null,symbol.startsWith('bili:')?'🙂':symbol);
    const img=el("img","room-reaction-image"); img.src=face.src; img.alt=""; img.width=24; img.height=24; img.draggable=false; img.loading="lazy";
    img.onerror=()=>img.replaceWith(el('span',null,face.fallback || symbol));
    return img;
  };
  const reactionLabel = symbol => reactionFaces.get(symbol)?.label || "表情";
  let openReactionPicker=null;
  document.addEventListener('click',event=>{
    if(openReactionPicker && !openReactionPicker.picker.contains(event.target) && !openReactionPicker.add.contains(event.target))openReactionPicker.close();
  });
  api.reactions = (item, emoji, changed, failed) => {
    const box=el('div','room-reactions'); let busy=false;
    if(item.deleted)return box;
    async function apply(symbol, active) {
      if(busy||api.readOnly())return; api.closeMenus();closePicker(); busy=true; box.querySelectorAll('button').forEach(n=>n.disabled=true);
      try { const result=await post('/api/reaction',{message_id:item.id,emoji:symbol,active}); changed(result); }
      catch(error) { failed(error.message); box.querySelectorAll('button').forEach(n=>n.disabled=false); }
      finally{busy=false;}
    }
    for(const reaction of item.reactions || []) {
      const b=button('','room-reaction'+(reaction.mine?' mine':'')), actors=actorsFor(reaction);
      b.dataset.emoji=reaction.emoji;
      b.append(reactionFace(reaction.emoji));
      if(actors.length&&actors.length===reaction.count&&reaction.count<=3){const faces=el('span','room-reaction-avatar-stack');for(const actor of actors)faces.append(actorFace(actor));b.append(faces);}
      else b.append(el('span','room-reaction-count',reaction.count));
      b.setAttribute('aria-pressed',String(!!reaction.mine));
      if(api.readOnly())b.setAttribute('aria-disabled','true');
      b.setAttribute('aria-label',reactionLabel(reaction.emoji)+'，'+reaction.count+' 人回应'+(reaction.mine?'，点击取消自己的回应':''));
      reactionActors(b,reaction);
      b.onclick=()=>apply(reaction.emoji,!reaction.mine); box.append(b);
    }
    const add=button('＋ 表情','room-reaction-add'), picker=el('div','room-reaction-picker'); picker.hidden=true;
    const grid=el('div','room-reaction-grid');
    picker.append(grid);
    add.setAttribute('aria-expanded','false'); picker.setAttribute('role','group'); picker.setAttribute('aria-label','选择表情回应');
    const choices=emoji.filter(symbol=>reactionFaces.has(symbol));
    let built=false;
    function closePicker(restoreFocus=false) {
      picker.hidden=true; add.setAttribute('aria-expanded','false');
      if(openReactionPicker?.picker===picker)openReactionPicker=null;
      if(restoreFocus && add.isConnected)add.focus({preventScroll:true});
    }
    function showChoices() {
      grid.replaceChildren();
      let characters=false;
      for(const symbol of choices) {
        if(reactionFaces.get(symbol)?.character&&!characters){const line=el('div','room-reaction-separator');line.setAttribute('role','separator');grid.append(line);characters=true;}
        const b=button('','room-reaction-option'); b.append(reactionFace(symbol)); b.title=reactionLabel(symbol); b.setAttribute('aria-label','回应 '+reactionLabel(symbol));
        b.onclick=()=>apply(symbol,true); grid.append(b);
      }
      grid.scrollTop=0;
    }
    add.onclick=()=>{
      if(!picker.hidden){closePicker();return;}
      openReactionPicker?.close();
      picker.hidden=false; add.setAttribute('aria-expanded','true');
      openReactionPicker={picker,add,close:closePicker};
      if(!picker.hidden){
        if(!built){showChoices();built=true;}
        picker.style.transform='none';
        const bounds=box.closest('#msgs')?.getBoundingClientRect(), rect=picker.getBoundingClientRect();
        const right=Math.min(document.documentElement.clientWidth-12,(bounds?.right || innerWidth)-12);
        const left=Math.max(12,(bounds?.left || 0)+12);
        const log=box.closest('.room-threads')?.getBoundingClientRect();
        const height=document.documentElement.clientHeight||window.innerHeight||768;
        const top=(log?.top ?? bounds?.top ?? 0)+8, bottom=(log?.bottom ?? bounds?.bottom ?? height)-8;
        const x=Math.max(left-rect.left,Math.min(0,right-rect.right)), y=Math.max(top-(rect.top??top),Math.min(0,bottom-(rect.bottom??bottom)));
        picker.style.transform='translate('+x+'px,'+y+'px)';
        picker.scrollIntoView({block:'nearest',inline:'nearest'}); grid.querySelector('button')?.focus({preventScroll:true});
      }
    };
    picker.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closePicker(true);}};
    if(!api.readOnly())box.append(add,picker); return box;
  };
  let dialog, image, imageError, caption, prev, next, opener, messageId, current=[], index=0;
  function restoreImageFocus() {
    let target=opener;
    if(!target?.isConnected)target=Array.from(document.querySelectorAll('[data-discussion-id]')).find(n=>n.dataset.discussionId===messageId)?.querySelectorAll('.room-images button, .parent-images button')[index];
    target?.focus({preventScroll:true});
  }
  function dismissImage() {dialog.close();restoreImageFocus();image.removeAttribute('src');current=[];}
  api.messageDeleted = id => {if(id===messageId&&dialog?.open)dismissImage();};
  function showImage() {
    image.hidden=false;imageError.hidden=true;
    image.src=api.mediaURL(current[index]); image.alt='消息图片 '+(index+1)+' / '+current.length;
    caption.textContent=(index+1)+' / '+current.length; prev.disabled=index===0; next.disabled=index===current.length-1;
  }
  api.gallery = (item, selected, trigger) => {
    if(item.deleted)return;
    const valid=(item.images || []).filter(name=>api.mediaURL(name));
    if(!valid.length)return;
    if(!dialog){
      dialog=el('dialog','room-image-dialog'); dialog.setAttribute('aria-label','消息图片全屏查看');
      const header=el('div','room-image-header'), close=button('关闭','room-image-close'); close.autofocus=true;
      caption=el('span','room-image-count'); caption.setAttribute('aria-live','polite'); header.append(caption,close);
      image=el('img','room-image-full');imageError=el('p','room-image-error','图片加载遇到问题，请稍后重试。');imageError.hidden=true;imageError.setAttribute('role','status');
      image.onerror=()=>{image.hidden=true;imageError.hidden=false;};const row=el('div','room-image-stage');
      prev=button('‹','room-image-prev'); next=button('›','room-image-next');
      prev.setAttribute('aria-label','上一张图片'); next.setAttribute('aria-label','下一张图片');
      prev.onclick=()=>{if(index>0){index--;showImage();}}; next.onclick=()=>{if(index<current.length-1){index++;showImage();}};
      close.onclick=dismissImage; row.append(prev,image,imageError,next); dialog.append(header,row); document.body.append(dialog);
      dialog.addEventListener('click',event=>{
        if(event.target===dialog || event.target===row || event.target===header)dismissImage();
      });
      dialog.addEventListener('keydown',e=>{if(e.key==='Escape')e.stopPropagation();if(e.key==='ArrowLeft'){e.preventDefault();prev.click();}if(e.key==='ArrowRight'){e.preventDefault();next.click();}});
      dialog.addEventListener('cancel',event=>{event.preventDefault();dismissImage();});
      dialog.addEventListener('close',()=>{if(!dialog.open){restoreImageFocus();image.removeAttribute('src');current=[];}});
    }
    current=valid; index=Math.max(0,valid.indexOf((item.images||[])[selected])); opener=trigger; messageId=item.id;showImage(); dialog.showModal();
  };
  return api;
})();
