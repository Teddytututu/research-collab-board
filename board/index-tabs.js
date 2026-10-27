/* enhance the existing existing renderer category summaries; cards and archive stay owned by existing renderer. */
(() => {
  'use strict';
  const memories = new WeakMap();
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const savedTab = () => { try { return localStorage.getItem('ftab'); } catch (_) { return null; } };
  const saveTab = value => { try { localStorage.setItem('ftab', value); } catch (_) {} };
  function beforeRender(box) {
    const filter = document.getElementById('file-filter');
    if (filter && box.contains(filter)) {
      const memory = memories.get(box);
      if (memory) memory.restoreFocus = document.activeElement === filter;
      box.closest('#files').querySelector('.files-heading').append(filter);
    }
  }
  function enhance(box, order) {
    const host = box.closest('#files');
    if (!host) return;
    host.setAttribute('data-index-tabs', '');
    let bar = host.querySelector('.findex-bar');
    if (!bar) {
      bar = make('div', 'findex-bar');
      box.prepend(bar);
    }
    let tabs = bar.querySelector('.findex-tabs');
    if (!tabs) { tabs = make('div', 'findex-tabs'); bar.prepend(tabs); }
    tabs.replaceChildren();
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', '文件分类');
    const filter = document.getElementById('file-filter');
    if (filter) { bar.append(filter); filter.placeholder = '筛选…'; }
    const memory = memories.get(box) || {preferred: savedTab() || '研究', course: '全部', searchTab: null, searchCourse: '全部'};
    memories.set(box, memory);
    const existing = new Map();
    Array.from(box.children).filter(node => node.classList.contains('factive-group')).forEach(old => {
      const head = old.querySelector(':scope > summary.factive-head');
      if (!head) return;
      const text = head.textContent;
      const category = text.slice(0, text.lastIndexOf(' · '));
      // Shallow-copy only the category wrapper to retire its old fold listener.
      // Move all content nodes, including the original card objects and handlers.
      const group = old.cloneNode(false);
      while (old.firstChild) group.append(old.firstChild);
      old.replaceWith(group);
      const placeholder = make('summary');
      placeholder.hidden = true; placeholder.setAttribute('aria-hidden', 'true');
      group.prepend(placeholder); head.remove(); group.open = true;
      const records = Array.from(group.querySelectorAll('.fcard')).map(card => ({
        card, title: card.querySelector('.fname')?.textContent || '',
        course: card.closest('.fcourse')?.querySelector('.fcourse-label')?.textContent || ''
      }));
      existing.set(category, {category, group, head, records});
    });
    const names = order.filter(name => name !== '其他' || existing.has(name));
    for (const category of existing.keys()) if (!names.includes(category)) names.push(category);
    const empty = box.querySelector('.file-empty');
    const states = names.map((category, index) => {
      const state = existing.get(category) || (() => {
        const group = make('details', 'factive-group');
        const placeholder = make('summary'); placeholder.hidden = true;
        placeholder.setAttribute('aria-hidden', 'true'); group.append(placeholder); group.open = true;
        box.insertBefore(group, empty);
        return {category, group, head: make('summary', 'factive-head'), records: []};
      })();
      const {group, head} = state;
      head.classList.add('findex-tab');
      head.dataset.indexKind = category;
      group.dataset.indexKind = category;
      group.classList.add('findex-pane');
      head.id = 'findex-tab-' + index; group.id = 'findex-pane-' + index;
      head.setAttribute('role', 'tab'); head.setAttribute('aria-controls', group.id);
      group.setAttribute('role', 'tabpanel'); group.setAttribute('aria-labelledby', head.id);
      const label = make('span', 'findex-label', category);
      state.count = make('span', 'findex-count', state.records.length);
      head.replaceChildren(label, state.count); tabs.append(head);
      state.courses = Array.from(group.querySelectorAll(':scope > .fcourse'));
      if (category === '学习') {
        state.chips = make('div', 'findex-courses');
        state.chips.setAttribute('role', 'group'); state.chips.setAttribute('aria-label', '课程筛选');
        const courseNames = ['全部'];
        state.records.forEach(record => {
          const course = record.title.match(/[A-Z]{4}\d{4}/)?.[0];
          if (course && !courseNames.includes(course)) courseNames.push(course);
        });
        state.courseNames = courseNames;
        courseNames.forEach(course => {
          const chip = make('button', 'findex-course', course); chip.type = 'button'; chip.dataset.course = course;
          chip.onclick = () => {
            if (query()) memory.searchCourse = course; else memory.course = course;
            paint();
          };
          state.chips.append(chip);
        });
        group.insertBefore(state.chips, group.children[1] || null);
      }
      head.onclick = event => {
        event.preventDefault();
        if (query()) memory.searchTab = category;
        else { memory.preferred = category; saveTab(category); }
        paint();
      };
      head.onkeydown = event => {
        const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); head.click(); return; }
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        const target = event.key === 'Home' ? 0 : event.key === 'End' ? names.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + names.length) % names.length;
        states[target].head.focus(); states[target].head.click();
      };
      return state;
    });
    if (!names.includes(memory.preferred)) memory.preferred = names[0] || '';
    const query = () => (filter?.value || '').trim().toLocaleLowerCase();
    function paint() {
      const needle = query();
      const matches = new Map(states.map(state => [state.category, state.records.filter(record => record.title.toLocaleLowerCase().includes(needle))]));
      let selected = needle ? memory.searchTab || memory.preferred : memory.preferred;
      if (needle && !memory.searchTab && !matches.get(selected)?.length) selected = states.find(state => matches.get(state.category).length)?.category || selected;
      states.forEach(state => {
        const active = state.category === selected;
        const count = matches.get(state.category).length;
        state.count.textContent = count;
        state.head.classList.toggle('is-selected', active);
        state.head.classList.toggle('is-empty', Boolean(needle) && count === 0);
        state.head.setAttribute('aria-selected', String(active)); state.head.tabIndex = active ? 0 : -1;
        state.group.hidden = !active;
        const wantedCourse = needle ? memory.searchCourse : memory.course;
        const course = state.courseNames?.includes(wantedCourse) ? wantedCourse : '全部';
        state.records.forEach(record => {
          record.card.hidden = !record.title.toLocaleLowerCase().includes(needle) || (state.category === '学习' && course !== '全部' && record.course !== course);
        });
        state.courses.forEach(section => { section.hidden = Array.from(section.querySelectorAll('.fcard')).every(card => card.hidden); });
        if (state.chips) Array.from(state.chips.children).forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.course === course)));
      });
      if (empty) {
        const selectedState = states.find(state => state.category === selected);
        empty.hidden = Boolean(selectedState?.records.some(record => !record.card.hidden));
        empty.textContent = needle ? '没有匹配的报告与文件' : '还没有报告与文件';
      }
    }
    if (filter) filter.oninput = () => { memory.searchTab = null; memory.searchCourse = '全部'; paint(); };
    paint();
    if (filter && memory.restoreFocus) { filter.focus({preventScroll:true}); memory.restoreFocus = false; }
  }
  window.FileIndexTabs = Object.freeze({beforeRender, enhance});
})();
