
window.RoomMarkdown = (() => {
  const MAX = 6000;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const text = (n, value) => n.append(document.createTextNode(value));
  function safeURL(value) {
    if (typeof value !== 'string' || !/^https?:\/\//i.test(value) || /[\s\u0000-\u001f\u007f]/.test(value)) return null;
    try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && url.hostname ? url.href : null; }
    catch (_) { return null; }
  }
  function mentions(target, value, opts) {
    const aliases = new Map();
    for (const a of opts.accounts || []) {
      aliases.set(a.id.toLowerCase(), a.id);
      if (a.display_name) aliases.set(a.display_name.toLowerCase(), a.id);
    }
    if (aliases.has('owner')) aliases.set('owner', 'owner');
    if (!aliases.size) { text(target, value); return; }
    const names = [...aliases.keys()].sort((a,b) => b.length-a.length).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const re = new RegExp('(^|[^\\w@./:+%\\-])@('+names+')(?![\\w@]|[.+\\-][a-z0-9])', 'gi');
    let end = 0;
    for (const match of value.matchAll(re)) {
      const start = match.index + match[1].length;
      text(target, value.slice(end, start));
      target.append(el('span', 'room-mention'+(aliases.get(match[2].toLowerCase()) === opts.me ? ' room-mention-self' : ''), '@'+match[2]));
      end = start + match[2].length + 1;
    }
    text(target, value.slice(end));
  }
  function inline(target, value, opts, depth = 0) {
    if (depth > 8) { text(target, value); return; }
    const token = /!\[[^\]\n]*\]\([^\n)]*\)|(`+)([^`\n]+)\1|\[([^\]\n]+)\]\(([^\s)]*)\)|\*\*([^\n]+?)\*\*|__([^\n]+?)__|~~([^\n]+?)~~|\*([^*\n]+)\*|_([^_\n]+)_|https?:\/\/[^\s<>"`]+/g;
    let end = 0;
    for (const m of value.matchAll(token)) {
      mentions(target, value.slice(end, m.index), opts);
      if (m[0].startsWith('![')) text(target, m[0]);
      else if (m[1]) target.append(el('code', null, m[2]));
      else if (m[3] != null) {
        const url = safeURL(m[4]);
        if (url) { const a = el('a'); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; inline(a, m[3], opts, depth+1); target.append(a); }
        else text(target, m[0]);
      } else if (m[5] || m[6] || m[7] || m[8] || m[9]) {
        const n = el(m[5] || m[6] ? 'strong' : m[7] ? 'del' : 'em');
        inline(n, m[5] || m[6] || m[7] || m[8] || m[9], opts, depth+1); target.append(n);
      } else {
        const raw = m[0].replace(/[.,;!?，。；！？]+$/, ''), suffix = m[0].slice(raw.length), url = safeURL(raw);
        if (url) { const a = el('a', null, raw); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; target.append(a); text(target, suffix); }
        else text(target, m[0]);
      }
      end = m.index + m[0].length;
    }
    mentions(target, value.slice(end), opts);
  }
  function highlight(code, source, language) {
    if (!['js','javascript','ts','typescript','python','py','json','bash','sh'].includes(language)) { code.textContent = source; return; }
    const re = /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\n]*|#[^\n]*|\b(?:const|let|var|function|return|if|else|for|while|class|new|async|await|import|from|def|print|True|False|None|true|false|null|try|catch|raise|with|as|in)\b|\b\d+(?:\.\d+)?\b)/g;
    let end = 0;
    for (const m of source.matchAll(re)) {
      text(code, source.slice(end, m.index));
      const cls = /^["']/.test(m[0]) ? 'string' : /^(?:#|\/\/)/.test(m[0]) ? 'comment' : /^\d/.test(m[0]) ? 'number' : 'keyword';
      code.append(el('span', 'room-token-'+cls, m[0])); end = m.index+m[0].length;
    }
    text(code, source.slice(end));
  }
  function codeBlock(source, language) {
    language = /^[a-z0-9_+-]{1,24}$/i.test(language) ? language.toLowerCase() : '';
    const box = el('div', 'room-code'), bar = el('div', 'room-code-bar');
    const copy = el('button', 'room-code-copy', '复制'); copy.type = 'button'; copy.setAttribute('aria-label','复制代码');
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(source); copy.textContent = '已复制'; }
      catch (_) { copy.textContent = '请选择代码复制'; }
    };
    bar.append(el('span', null, language || 'text'), copy);
    const pre = el('pre'), code = el('code'); highlight(code, source, language); pre.append(code); box.append(bar, pre); return box;
  }
  const cells = line => line.trim().replace(/^\||(?<!\\)\|$/g, '').split(/(?<!\\)\|/).slice(0,30).map(v => v.trim().replace(/\\\|/g,'|'));
  const divider = line => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
  function blocks(target, lines, opts, depth=0) {
    for (let i=0; i<lines.length;) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      const fence = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
      if (fence) {
        const body = []; i++;
        while (i<lines.length) {
          const close = lines[i].match(/^ {0,3}(`{3,}|~{3,})\s*$/);
          if (close && close[1][0] === fence[1][0] && close[1].length >= fence[1].length) { i++; break; }
          body.push(lines[i++]);
        }
        target.append(codeBlock(body.join('\n'), fence[2].trim())); continue;
      }
      if (i+1<lines.length && line.includes('|') && divider(lines[i+1])) {
        const wrap = el('div','room-table-wrap'), table = el('table'), head = el('thead'), hr = el('tr'), body = el('tbody');
        const labels = cells(line); labels.forEach(label => { const th=el('th'); th.scope='col'; inline(th,label,opts); hr.append(th); }); head.append(hr); i+=2;
        let rows=0;
        while (i<lines.length && lines[i].includes('|') && lines[i].trim() && rows++<100) {
          const tr = el('tr'), row = cells(lines[i++]);
          labels.forEach((_, index) => { const td=el('td'); inline(td,row[index] || '',opts); tr.append(td); }); body.append(tr);
        }
        table.append(head,body); wrap.tabIndex=0; wrap.setAttribute('aria-label','表格，可横向滚动'); wrap.append(table); target.append(wrap); continue;
      }
      const heading = line.match(/^ {0,3}(#{1,6})\s+(.+)$/);
      if (heading) { const h=el('h'+Math.min(6,heading[1].length+2)); inline(h,heading[2],opts); target.append(h); i++; continue; }
      if (/^\s*>/.test(line) && depth<6) {
        const quote=el('blockquote'), content=[];
        while (i<lines.length && /^\s*>/.test(lines[i])) content.push(lines[i++].replace(/^\s*> ?/,''));
        blocks(quote,content,opts,depth+1); target.append(quote); continue;
      }
      const list = line.match(/^\s*(?:([-+*])|(\d{1,6})[.)])\s+(.+)$/);
      if (list) {
        const ordered=!!list[2], listNode=el(ordered?'ol':'ul'); if(ordered)listNode.start=Number(list[2]);
        while (i<lines.length) {
          const entry=lines[i].match(/^\s*(?:([-+*])|(\d{1,6})[.)])\s+(.+)$/);
          if(!entry || !!entry[2]!==ordered)break;
          const li=el('li'); inline(li,entry[3],opts); listNode.append(li); i++;
        }
        target.append(listNode); continue;
      }
      const p=el('p'); inline(p,line,opts); target.append(p); i++;
    }
  }
  function render(source, opts={}) {
    const root=el('div','room-body room-markdown'), value=String(source || '').slice(0,MAX).replace(/\r\n?/g,'\n');
    blocks(root,value.split('\n'),opts);
    if(String(source || '').length>MAX)root.append(el('p','room-render-limit','显示前 6000 字'));
    return root;
  }
  return {render, safeURL};
})();
