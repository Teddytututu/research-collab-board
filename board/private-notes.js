/* The browser is owner; assistants reply through the trusted local CLI. */
(() => {
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const button = text => { const n = el('button', '', text); n.type = 'button'; return n; };
  const owner = () => BoardIdentity.me?.id === 'owner';
  const state = () => ({items: [], more: false, body: '', client: null, version: 0, pending: []});
  const peers = {GPT: state(), Claude: state()}, views = {};
  let selected = 'GPT', privateBox, privateInput, mounted = false, privateBusy = false, accessEpoch = 0;
  let room, privateTitle, privateLabel, privateTabs, privateTrigger, publicScroll = 0;
  const privateMediaURL = (peer, name) => Object.hasOwn(peers, peer) && typeof name === 'string' && /^[a-f0-9]{32}\.png$/.test(name) ? '/api/private/image?peer=' + encodeURIComponent(peer) + '&name=' + encodeURIComponent(name) : null;
  const clearPending = data => { data.pending.forEach(p => URL.revokeObjectURL(p.url)); data.pending = []; };
  function resizePrivate() { privateInput.style.height = 'auto'; privateInput.style.height = Math.min(160, Math.max(44, privateInput.scrollHeight)) + 'px'; }
  async function request(url, payload) {
    const response = await fetch(url, payload ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)} : {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请稍后重试，草稿已保留。');
    return data;
  }
  const endpoint = peer => '/api/private?peer=' + encodeURIComponent(peer);
  function setStatus(view, text) { view.status.textContent = text; }

  function privateMessage(row) {
    const name = String(row.author), mine = name === BoardIdentity.me.id;
    const article = el('article', 'private-message room-message by-' + name.toLowerCase() + (mine ? ' mine' : ''));
    article.dataset.privateMessageId = row.id;
    const avatar = button(name.slice(0, 1));
    avatar.className = 'private-avatar room-avatar ' + name.toLowerCase(); avatar.dataset.mentionId = name;
    avatar.setAttribute('aria-keyshortcuts', 'Alt+M');
    avatar.setAttribute('aria-label', '提及 ' + BoardIdentity.name(name));
    avatar.onclick = () => insertMention(name, privateInput);
    avatar.addEventListener('keydown', event => { if (event.altKey && event.key.toLowerCase() === 'm') { event.preventDefault(); insertMention(name, privateInput); } });
    const asset = BoardIdentity.accounts.find(account => account.id === name)?.avatar;
    if (asset?.file) {
      const image = el('img', 'room-avatar-image'); image.alt = ''; image.decoding = 'async';
      image.addEventListener('load', () => avatar.classList.add('room-avatar-ready'), {once: true});
      image.addEventListener('error', () => { image.remove(); avatar.classList.remove('room-avatar-ready'); }, {once: true});
      image.src = BoardIdentity.avatarURL(name, asset.file);
      if (/^\d+(?:\.\d+)?%$/.test(asset.cropWidth || '') && /^-?\d+(?:\.\d+)?%$/.test(asset.cropLeft || '') && /^-?\d+(?:\.\d+)?%$/.test(asset.cropTop || '')) {
        Object.assign(image.style, {inset:'auto', width:asset.cropWidth, height:'auto', left:asset.cropLeft, top:asset.cropTop, transform:'none', objectFit:'fill'});
      } else image.style.objectPosition = asset.position || '';
      avatar.append(image);
    }
    const content = el('div', 'room-message-content'), meta = el('div', 'room-meta');
    const time = el('time', '', String(row.created_at).slice(5, 16).replace('T', ' '));
    time.dateTime = row.created_at;
    meta.append(el('span', 'room-author', BoardIdentity.name(name)), time);
    const bubble = el('div', 'room-bubble'); bubble.append(el('p', 'room-body', row.body));
    const images = (Array.isArray(row.images) ? row.images : []).filter(name => privateMediaURL(row.peer, name));
    if (images.length) {
      const box = el('div', 'room-images');
      images.forEach((name, index) => {
        const open = button(''); open.setAttribute('aria-label', '查看私聊图片 ' + (index + 1));
        const image = el('img'); image.alt = '私聊图片 ' + (index + 1); image.loading = 'lazy'; image.src = privateMediaURL(row.peer, name);
        open.append(image); open.onclick = () => { if (owner() && selected === row.peer) privateGallery({...row, images}, index, open); };
        box.append(open);
      });
      bubble.append(box);
    }
    content.append(meta, bubble); article.append(avatar, content); return article;
  }

  function render(peer) {
    if (selected !== peer || !owner()) return;
    const view = views.private, data = peers[peer];
    const bottom = view.log.scrollHeight - view.log.scrollTop - view.log.clientHeight < 72;
    const oldTop = view.log.scrollTop;
    const focused = view.log.contains(document.activeElement) ? document.activeElement.closest('.private-message')?.dataset.privateMessageId : null;
    const children = data.items.map(privateMessage);
    view.log.replaceChildren(...children);
    if (focused) children.find(child => child.dataset.privateMessageId === focused)?.querySelector('.private-avatar')?.focus({preventScroll: true});
    view.empty.hidden = children.length > 0; view.older.hidden = !data.more;
    view.log.scrollTop = bottom ? view.log.scrollHeight : oldTop;
  }
  async function load(peer, older = false) {
    if (!owner() || !Object.hasOwn(peers, peer)) return;
    const data = peers[peer], view = views.private, version = ++data.version, epoch = accessEpoch;
    const before = older ? data.items[0]?.id : null;
    view.older.disabled = true;
    try {
      const result = await request(endpoint(peer) + (before ? '&before=' + encodeURIComponent(before) : ''));
      if (version !== data.version || !owner() || epoch !== accessEpoch) return;
      const byId = new Map((older ? [...result.items, ...data.items] : [...data.items, ...result.items]).map(row => [row.id, row]));
      data.items = [...byId.values()];
      if (older || data.items.length <= result.items.length) data.more = result.has_more;
      render(peer);
      if (selected === peer) { view.empty.textContent = '还没有消息'; setStatus(view, ''); }
    } catch (error) {
      if (version === data.version && owner() && epoch === accessEpoch && selected === peer) {
        if (!data.items.length) view.empty.textContent = '加载遇到问题，请点击刷新。';
        setStatus(view, error.message);
      }
    } finally { if (version === data.version && owner() && epoch === accessEpoch && selected === peer) view.older.disabled = false; }
  }

  function makeView(id, title) {
    const section = el('section', 'social-section'); section.id = id;
    section.append(el('h2', '', title));
    const card = el('div', 'card social-card'), status = el('p', 'social-status'); status.setAttribute('role', 'status');
    const older = button('查看更早留言'); older.hidden = true;
    const refresh = button('↻'); refresh.className = 'social-refresh'; refresh.title = '刷新'; refresh.setAttribute('aria-label', '刷新');
    const log = el('div', 'private-log');
    log.setAttribute('role', 'region'); log.setAttribute('aria-label', title + '记录'); log.tabIndex = 0;
    const empty = el('p', 'social-empty', '正在加载…');
    card.append(refresh, older, empty, log); section.append(card);
    return {section, card, log, empty, status, older, refresh};
  }
  function composer(view, id, label) {
    const form = el('form', 'social-compose'), textLabel = el('label', '', label);
    const input = el('textarea'); input.id = id; input.rows = 3; input.maxLength = 6000; input.required = true;
    textLabel.htmlFor = id;
    const submit = el('button', '', '发送'); submit.type = 'submit';
    form.append(textLabel, input, submit, view.status); view.card.append(form);
    return {form, input, submit};
  }
  function privateControls() {
    const view = views.private = makeView('private-chat', '我的私聊'); privateBox = view.section;
    privateBox.classList.add('room-private-panel'); privateBox.hidden = true;
    privateTitle = view.section.querySelector('h2'); privateTitle.id = 'private-peer-title';
    view.section.setAttribute('aria-labelledby', privateTitle.id);
    const heading = el('div', 'room-private-heading'), back = button('←'); back.title = '返回讨论室'; back.setAttribute('aria-label', '返回讨论室');
    back.className = 'room-private-back'; back.onclick = () => closePrivate();
    heading.append(back, privateTitle); view.section.prepend(heading);
    const tabs = el('div', 'private-peers'); tabs.setAttribute('role', 'group'); tabs.setAttribute('aria-label', '选择私聊对象');
    privateTabs = tabs;
    const form = composer(view, 'private-text', '给 GPT 的私聊消息'); privateInput = form.input;
    form.form.classList.add('room-compose'); form.submit.classList.add('room-submit');
    const inputWrap = el('div', 'room-input-wrap');
    privateInput.before(inputWrap); inputWrap.append(privateInput);
    privateLabel = form.form.querySelector('label');
    for (const peer of Object.keys(peers)) {
      const tab = button(peer); tab.dataset.peer = peer; tab.setAttribute('aria-pressed', String(peer === selected));
      tab.onclick = () => openPrivate(peer);
      tabs.append(tab);
    }
    view.card.prepend(tabs);
    privateInput.required = false; privateInput.rows = 1;
    const attach = el('div', 'room-attach'); attach.id = 'private-attach'; attach.hidden = true;
    inputWrap.before(attach);
    const picker = el('input'); picker.type = 'file'; picker.multiple = true; picker.accept = 'image/png,image/jpeg,image/webp,image/gif'; picker.hidden = true;
    const pick = button('＋ 图片'); pick.className = 'room-pick'; pick.title = '也可以粘贴或拖入图片';
    inputWrap.before(pick, picker);
    const hint = el('p', 'room-composer-hint', 'Enter 发送 · Shift+Enter 换行'); hint.id = 'private-send-hint'; privateInput.setAttribute('aria-describedby', hint.id); form.form.append(hint);
    function showPending() {
      const peer = selected, data = peers[peer]; attach.replaceChildren(); attach.hidden = !data.pending.length;
      data.pending.forEach((p, index) => {
        const thumb = el('div', 'thumb'), image = el('img'), remove = button('×');
        image.src = p.url; image.alt = '待发送的图片'; remove.setAttribute('aria-label', '移除这份附件'); remove.disabled = privateBusy;
        remove.onclick = () => { if (privateBusy || !owner() || selected !== peer) return; URL.revokeObjectURL(p.url); data.pending.splice(index, 1); data.client = null; showPending(); };
        thumb.append(image, remove); attach.append(thumb);
      });
    }
    view.showPending = showPending;
    function addFiles(files) {
      if (privateBusy || !owner()) return;
      const data = peers[selected];
      for (const file of files) {
        if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type)) { setStatus(view, '图片请使用 PNG、JPG、WebP、GIF。'); continue; }
        if (file.size > 8 * 1024 * 1024) { setStatus(view, '图片请控制在 8 MiB 以内。'); continue; }
        if (data.pending.length >= 6) { setStatus(view, '一次最多发 6 张图片。'); break; }
        data.pending.push({file, url: URL.createObjectURL(file)}); data.client = null;
      }
      showPending();
    }
    pick.onclick = () => picker.click(); picker.onchange = () => { addFiles(picker.files); picker.value = ''; };
    privateInput.addEventListener('paste', event => { const files = Array.from(event.clipboardData?.files || []).filter(f => f.type.startsWith('image/')); if (files.length) { event.preventDefault(); addFiles(files); } });
    form.form.addEventListener('dragover', event => { if (Array.from(event.dataTransfer?.types || []).includes('Files')) { event.preventDefault(); form.form.classList.add('room-drop'); } });
    form.form.addEventListener('dragleave', () => form.form.classList.remove('room-drop'));
    form.form.addEventListener('drop', event => { form.form.classList.remove('room-drop'); const files = Array.from(event.dataTransfer?.files || []); if (files.length) { event.preventDefault(); addFiles(files); } });
    privateInput.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.altKey && !event.isComposing && event.keyCode !== 229 && !event.defaultPrevented) {
        event.preventDefault(); form.form.requestSubmit();
      }
    });
    privateInput.addEventListener('input', () => { peers[selected].body = privateInput.value; peers[selected].client = null; resizePrivate(); });
    view.older.onclick = () => load(selected, true);
    view.refresh.onclick = () => load(selected);
    form.form.onsubmit = async event => {
      event.preventDefault(); if (privateBusy || !owner()) return;
      const peer = selected, data = peers[peer], body = privateInput.value.trim(), epoch = accessEpoch;
      if (!body && !data.pending.length) { setStatus(view, '写点内容或放张图片再发送。'); return; }
      data.client ||= crypto.randomUUID(); privateBusy = true;
      for (const control of [...tabs.children, privateInput, form.submit, pick, picker]) control.disabled = true;
      showPending(); setStatus(view, '正在发送…');
      try {
        const images = await Promise.all(data.pending.map(p => new Promise((ok, bad) => {
          const reader = new FileReader(); reader.onload = () => ok(reader.result); reader.onerror = () => bad(new Error('图片读取遇到问题，草稿已保留。')); reader.readAsDataURL(p.file);
        })));
        if (!owner() || epoch !== accessEpoch || selected !== peer) return;
        await request(endpoint(peer), {body, client_id: data.client, images});
        if (!owner() || epoch !== accessEpoch) return;
        data.body = ''; data.client = null; clearPending(data); privateInput.value = ''; resizePrivate(); showPending(); await load(peer);
        if (!owner() || epoch !== accessEpoch) return;
        setStatus(view, '已发送给 ' + peer);
      } catch (error) { if (owner() && epoch === accessEpoch) setStatus(view, error.message); }
      finally {
        privateBusy = false; for (const control of [...tabs.children, privateInput, form.submit, pick, picker]) control.disabled = false; showPending();
        if (owner() && epoch === accessEpoch && !privateBox.hidden) privateInput.focus({preventScroll: true});
      }
    };
    return view.section;
  }
  function openPrivate(peer, trigger) {
    if (!mounted || !owner() || typeof peer !== 'string' || !Object.hasOwn(peers, peer)) return false;
    if (privateBusy) { setStatus(views.private, '正在发送给 ' + selected + '，请稍候。'); return false; }
    if (privateBox.hidden) publicScroll = document.getElementById('room-threads').scrollTop;
    closeGallery();
    peers[selected].body = privateInput.value; selected = peer;
    privateInput.value = peers[peer].body; views.private.showPending(); resizePrivate();
    if (trigger) privateTrigger = trigger;
    privateTitle.textContent = '与 ' + BoardIdentity.name(peer) + ' 私聊';
    privateLabel.textContent = '给 ' + BoardIdentity.name(peer) + ' 的私聊消息'; privateInput.placeholder = '给 ' + BoardIdentity.name(peer) + ' 发消息…';
    for (const tab of privateTabs.children) tab.setAttribute('aria-pressed', String(tab.dataset.peer === peer));
    room.dataset.privatePeer = peer; privateBox.hidden = false;
    render(peer); setStatus(views.private, '正在加载…'); load(peer);
    window.dispatchEvent(new Event('roomprivateopen'));
    privateInput.focus({preventScroll: true}); return true;
  }
  function closePrivate(focus = true) {
    if (!privateBox || privateBox.hidden) return;
    if (owner()) peers[selected].body = privateInput.value;
    closeGallery();
    privateBox.hidden = true; delete room.dataset.privatePeer;
    document.getElementById('room-threads').scrollTop = publicScroll;
    const fallback = Array.from(room.querySelectorAll('.room-avatar')).find(avatar => avatar.dataset.mentionId === selected);
    if (focus) (privateTrigger?.isConnected ? privateTrigger : fallback || document.getElementById('room-text'))?.focus({preventScroll: true});
    privateTrigger = null;
  }
  function insertMention(id, input) {
    if (!input || input.disabled || !BoardIdentity.accounts.some(row => row.id === id)) return false;
    const start = input.selectionStart ?? input.value.length, end = input.selectionEnd ?? start;
    const prefix = start && !/\s$/.test(input.value.slice(0, start)) ? ' ' : '';
    const text = prefix + '@' + id + ' ';
    if (input.maxLength > 0 && input.value.length - (end - start) + text.length > input.maxLength) return false;
    input.focus({preventScroll: true}); input.setSelectionRange(start, end);
    const inserted = document.execCommand('insertText', false, text);
    if (!inserted) { input.setRangeText(text, start, end, 'end'); input.dispatchEvent(new Event('input', {bubbles: true})); }
    input.setSelectionRange(start + text.length, start + text.length);
    return true;
  }
  function syncOwner() {
    if (owner()) { if (!privateBox.hidden) load(selected); }
    else {
      ++accessEpoch; closePrivate(false);
      for (const value of Object.values(peers)) { ++value.version; value.items = []; value.body = ''; value.client = null; clearPending(value); }
      views.private.showPending();
      views.private.log.replaceChildren(); privateInput.value = '';
      setStatus(views.private, '');
    }
  }
  let gallery, galleryImage, galleryCount, galleryError, galleryOpener, galleryMessageId, galleryRows = [], galleryAt = 0, galleryPeer;
  function closeGallery() { if (gallery?.open) gallery.close(); }
  function privateGallery(row, at, trigger) {
    if (!owner() || selected !== row.peer) return;
    if (!gallery) {
      gallery = el('dialog', 'room-image-dialog private-image-dialog'); gallery.setAttribute('aria-label', '私聊图片全屏查看');
      const header = el('div', 'room-image-header'), close = button('关闭'); close.autofocus = true;
      galleryCount = el('span', 'room-image-count'); galleryCount.setAttribute('aria-live', 'polite');
      galleryImage = el('img', 'room-image-full'); galleryError = el('p', 'room-image-error', '图片加载遇到问题，请稍后重试。'); galleryError.hidden = true;
      galleryImage.onerror = () => { galleryImage.hidden = true; galleryError.hidden = false; };
      const stage = el('div', 'room-image-stage'), prev = button('‹'), next = button('›');
      prev.setAttribute('aria-label', '上一张图片'); next.setAttribute('aria-label', '下一张图片');
      gallery.showImage = () => {
        galleryImage.hidden = false; galleryError.hidden = true;
        galleryImage.src = privateMediaURL(galleryPeer, galleryRows[galleryAt]); galleryImage.alt = '私聊图片 ' + (galleryAt + 1);
        galleryCount.textContent = (galleryAt + 1) + ' / ' + galleryRows.length;
        prev.disabled = galleryAt === 0; next.disabled = galleryAt === galleryRows.length - 1;
      };
      prev.onclick = () => { if (galleryAt > 0) { galleryAt--; gallery.showImage(); } };
      next.onclick = () => { if (galleryAt < galleryRows.length - 1) { galleryAt++; gallery.showImage(); } };
      close.onclick = closeGallery; header.append(galleryCount, close); stage.append(prev, galleryImage, galleryError, next); gallery.append(header, stage); document.body.append(gallery);
      gallery.addEventListener('keydown', event => { if (event.key === 'Escape') event.stopPropagation(); if (event.key === 'ArrowLeft') { event.preventDefault(); prev.click(); } if (event.key === 'ArrowRight') { event.preventDefault(); next.click(); } });
      gallery.addEventListener('close', () => {
        galleryImage.removeAttribute('src'); galleryRows = [];
        const replacement = Array.from(document.querySelectorAll('#private-chat [data-private-message-id]')).find(row => row.dataset.privateMessageId === galleryMessageId)?.querySelectorAll('.room-images button')[galleryAt];
        (galleryOpener?.isConnected ? galleryOpener : replacement)?.focus({preventScroll: true});
      });
      gallery.addEventListener('click', event => { if ([gallery, header, stage].includes(event.target)) closeGallery(); });
    }
    galleryRows = row.images; galleryPeer = row.peer; galleryAt = at; galleryOpener = trigger; galleryMessageId = row.id;
    gallery.showImage(); gallery.showModal();
  }
  window.RoomPrivateChat = {open: openPrivate, close: closePrivate};
  BoardIdentity.ready.then(() => {
    if (mounted) return; mounted = true;
    room = document.getElementById('msgs'); room.querySelector('.room-header').after(privateControls());
    const links = el('div', 'private-entry'); links.setAttribute('aria-label', '私聊');
    for (const peer of Object.keys(peers)) { const open = button('私聊 ' + peer); open.onclick = () => openPrivate(peer, open); links.append(open); }
    room.querySelector('.room-header').after(links);
    syncOwner(); window.addEventListener('identitychange', () => { syncOwner(); links.hidden = !owner(); });
    privateBox.addEventListener('keydown', event => { if (event.key === 'Escape' && !event.isComposing) { event.stopPropagation(); closePrivate(); } });
    setInterval(() => { if (document.visibilityState === 'visible' && owner() && !privateBox.hidden) load(selected); }, 15000);
  }).catch(() => {});
})();
