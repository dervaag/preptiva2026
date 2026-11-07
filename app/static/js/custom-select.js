'use strict';
(() => {
  const roots = [...document.querySelectorAll('[data-select]')];
  if (!roots.length) return;
  let opened = null, positionFrame = null;

  function selectedIndex(state) {
    return Math.max(0, state.options.findIndex(option => option.dataset.value === state.input.value));
  }

  function render(state) {
    const selected = selectedIndex(state);
    state.input.value = state.options[selected].dataset.value;
    state.value.textContent = state.options[selected].querySelector('.setup-select-option-label').textContent;
    state.options.forEach((option, index) => option.setAttribute('aria-selected', String(index === selected)));
  }

  function close(restoreFocus = false) {
    if (!opened) return;
    const state = opened;
    opened = null;
    state.menu.hidden = true;
    state.trigger.setAttribute('aria-expanded', 'false');
    state.trigger.removeAttribute('aria-activedescendant');
    state.options.forEach(option => option.removeAttribute('data-active'));
    state.query = '';
    if (restoreFocus) state.trigger.focus({preventScroll: true});
  }

  function anchorVisible(state, rect) {
    if (!state.trigger.getClientRects().length || !rect.width || rect.top < -1 || rect.bottom > innerHeight + 1) return false;
    for (let parent = state.root.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      const clip = parent.getBoundingClientRect();
      if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (rect.top < clip.top - 1 || rect.bottom > clip.bottom + 1)) return false;
    }
    return true;
  }

  function position(state) {
    const rect = state.trigger.getBoundingClientRect();
    if (!anchorVisible(state, rect)) {close(); return false;}
    const margin = 8, gap = 6;
    const width = Math.min(rect.width, innerWidth - margin * 2);
    state.menu.style.width = `${width}px`;
    state.menu.style.maxHeight = 'none';
    const naturalHeight = Math.min(state.menu.scrollHeight + 2, 260);
    const below = innerHeight - rect.bottom - margin - gap;
    const above = rect.top - margin - gap;
    const upward = below < naturalHeight && above > below;
    state.menu.style.maxHeight = `${Math.max(0, Math.min(naturalHeight, upward ? above : below))}px`;
    const height = state.menu.getBoundingClientRect().height;
    state.menu.style.left = `${Math.max(margin, Math.min(rect.left, innerWidth - width - margin))}px`;
    state.menu.style.top = `${upward ? rect.top - gap - height : rect.bottom + gap}px`;
    return true;
  }

  function activate(state, index, scroll = true) {
    state.active = Math.max(0, Math.min(index, state.options.length - 1));
    state.options.forEach((option, i) => option.toggleAttribute('data-active', i === state.active));
    state.trigger.setAttribute('aria-activedescendant', state.options[state.active].id);
    if (scroll) state.options[state.active].scrollIntoView({block: 'nearest'});
  }

  function open(state, index = selectedIndex(state)) {
    close();
    opened = state;
    state.menu.hidden = false;
    state.trigger.setAttribute('aria-expanded', 'true');
    if (position(state)) activate(state, index);
  }

  function choose(state, index, restoreFocus = true) {
    const previous = state.input.value;
    state.input.value = state.options[index].dataset.value;
    render(state);
    close(restoreFocus);
    if (state.input.value !== previous) {
      state.input.dispatchEvent(new Event('input', {bubbles: true}));
      state.input.dispatchEvent(new Event('change', {bubbles: true}));
    }
  }

  function normalized(text) {
    return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function search(state, key) {
    const now = performance.now();
    const query = now - state.queryAt > 700 ? key : state.query + key;
    if (opened !== state) open(state);
    state.query = query;
    state.queryAt = now;
    const repeated = [...query].every(char => char === query[0]);
    const needle = normalized(repeated ? query[0] : query);
    const start = state.active + (repeated ? 1 : 0);
    for (let offset = 0; offset < state.options.length; offset++) {
      const index = (start + offset) % state.options.length;
      if (normalized(state.options[index].querySelector('.setup-select-option-label').textContent.trim()).startsWith(needle)) {
        activate(state, index);
        break;
      }
    }
  }

  function keydown(event, state) {
    if (state.trigger.disabled || event.isComposing || event.ctrlKey || event.metaKey) return;
    const isOpen = opened === state;
    if (event.key === 'Tab') {
      if (isOpen) choose(state, state.active, false);
      return;
    }
    if (event.key === 'Escape') {
      if (isOpen) {event.preventDefault(); event.stopPropagation(); close(true);}
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (isOpen) choose(state, state.active); else open(state);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (isOpen && event.altKey && event.key === 'ArrowUp') choose(state, state.active);
      else if (isOpen) activate(state, state.active + (event.key === 'ArrowDown' ? 1 : -1));
      else open(state);
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      const index = event.key === 'Home' ? 0 : state.options.length - 1;
      if (isOpen) activate(state, index); else open(state, index);
    } else if (event.key.length === 1 && !event.altKey) {
      event.preventDefault();
      search(state, event.key);
    }
  }

  roots.forEach(root => {
    const state = {root, input: root.querySelector('input'), trigger: root.querySelector('[role=combobox]'),
      menu: root.querySelector('[role=listbox]'), value: root.querySelector('.setup-select-value'),
      options: [...root.querySelectorAll('[role=option]')], active: 0, query: '', queryAt: -Infinity};
    const initialValue = state.input.value;
    document.body.append(state.menu);
    render(state);
    state.trigger.addEventListener('click', () => {if (opened === state) close(); else open(state);});
    state.trigger.addEventListener('keydown', event => keydown(event, state));
    state.menu.addEventListener('pointerdown', event => {
      if (event.target.closest('[role=option]')) event.preventDefault();
    });
    state.menu.addEventListener('pointermove', event => {
      const option = event.target.closest('[role=option]');
      if (opened === state && option) activate(state, state.options.indexOf(option), false);
    });
    state.menu.addEventListener('click', event => {
      const option = event.target.closest('[role=option]');
      if (opened === state && option) choose(state, state.options.indexOf(option));
    });
    state.input.addEventListener('change', () => {if (opened === state) close(); render(state);});
    state.input.form?.addEventListener('reset', event => queueMicrotask(() => {
      if (event.defaultPrevented) return;
      if (opened === state) close();
      state.input.value = initialValue;
      render(state);
    }));
  });

  function schedulePosition(event) {
    if (!opened || event?.target === opened.menu) return;
    cancelAnimationFrame(positionFrame);
    positionFrame = requestAnimationFrame(() => {if (opened) position(opened);});
  }
  document.addEventListener('pointerdown', event => {
    if (opened && !opened.root.contains(event.target) && !opened.menu.contains(event.target)) close();
  });
  document.addEventListener('focusin', event => {
    if (opened && event.target !== opened.trigger && !opened.menu.contains(event.target)) close();
  });
  document.addEventListener('scroll', schedulePosition, true);
  document.addEventListener('toggle', schedulePosition, true);
  window.addEventListener('resize', schedulePosition);
  window.addEventListener('blur', () => close());
  window.addEventListener('pagehide', () => close());
})();
