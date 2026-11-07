'use strict';
(() => {
  const page = document.body.dataset.page;
  if (page !== 'dashboard' && page !== 'history') return;
  const node = id => document.getElementById(id);
  const personas = {
    hr: {name: 'Rina', title: 'HR', initial: 'R'},
    user: {name: 'Andi', title: 'User', initial: 'A'},
    manager: {name: 'Pak Hendra', title: 'Manager', initial: 'H'},
  };
  const competencyLabels = {
    communication: 'Komunikasi', problem_solving: 'Pemecahan masalah', technical: 'Teknis', analytical: 'Analisis',
    teamwork: 'Kerja sama', adaptability: 'Adaptasi', leadership: 'Kepemimpinan',
  };
  const levelLabels = {junior: 'Junior', middle: 'Middle', senior: 'Senior', manager: 'Manager'};
  const statusLabels = {preparing: 'Menyiapkan', preparation_failed: 'Persiapan tertunda', ready: 'Siap dimulai', running: 'Berlangsung', scoring: 'Menilai', evaluation_failed: 'Penilaian tertunda', done: 'Selesai', failed: 'Ditutup / gagal'};
  const activeStatuses = new Set(['preparing', 'preparation_failed', 'ready', 'running', 'scoring', 'evaluation_failed']);
  let dateFormatter = new Intl.DateTimeFormat(window.PreptivaI18n?.locale || 'en-GB', {day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'});
  let shortDateFormatter = new Intl.DateTimeFormat(window.PreptivaI18n?.locale || 'en-GB', {day: 'numeric', month: 'short'});
  const pageSize = 8;
  let sessions = [], historyStatus = 'all', historyPage = 1, loaded = false, loading = false, disposed = false;
  let loadGeneration = 0, focusGeneration = 0, loadController = null, focusController = null;
  let trendSessions = [], trendWidth = 0, chartResizeFrame = null, chartObserver = null;

  function timestamp(value) {
    const time = typeof value === 'number' ? value : value ? Date.parse(value) : NaN;
    return Number.isFinite(time) ? time : 0;
  }
  function completedAt(session) {return timestamp(session.finished_at) || timestamp(session.created_at);}
  function byCreated(first, second) {return timestamp(first.created_at) - timestamp(second.created_at);}
  function scored(session) {return session.status === 'done' && typeof session.total_score === 'number' && Number.isFinite(session.total_score);}
  function points(score) {return Math.round(score * 20);}
  function resultPath(session) {return `/sesi/${encodeURIComponent(String(session.id))}/hasil`;}
  function sessionPath(session) {return ['done', 'scoring', 'evaluation_failed'].includes(session.status) ? resultPath(session) : `/sesi/${encodeURIComponent(String(session.id))}/ruang`;}
  function panelRoles(session) {
    const roles = Array.isArray(session.panel) && session.panel.length ? session.panel : [session.interviewer];
    return [...new Set(roles.filter(role => Object.hasOwn(personas, role)))];
  }
  function persona(session) {
    const roles = panelRoles(session);
    if (roles.length > 1) return {name: roles.map(role => personas[role].name).join(' + '), title: `Panel · ${roles.map(role => personas[role].title).join(' + ')}`, initial: 'P'};
    return personas[session.interviewer] || {name: 'Pewawancara', title: 'Interviewer', initial: 'P'};
  }
  function dateText(value) {return timestamp(value) ? dateFormatter.format(new Date(value)) : '-';}
  function timeMarkup(value) {return timestamp(value) ? `<time datetime="${esc(value)}">${esc(dateText(value))}</time>` : '-';}
  function emptyState(title, description, link = true) {
    return `<div class="ws-empty"><span class="ws-empty-icon" aria-hidden="true">↗</span><h3>${esc(title)}</h3><p>${esc(description)}</p>${link ? '<a class="ws-text-link" href="/simulasi/baru">Mulai latihan</a>' : ''}</div>`;
  }
  function sessionRows(items) {
    return items.map(session => {
      const interviewer = persona(session);
      const status = Object.hasOwn(statusLabels, session.status) ? session.status : 'unknown';
      const score = scored(session) ? `${points(session.total_score)}<small>/100</small>` : '-';
      const metadata = [levelLabels[session.level] || session.level, session.company].filter(Boolean).join(' · ');
      return `<a class="ws-session-row" href="${esc(sessionPath(session))}">
        <span class="ws-session-main"><span class="ws-persona ws-persona--${esc(Object.hasOwn(personas, session.interviewer) ? session.interviewer : 'unknown')}" aria-hidden="true">${interviewer.initial}</span><span><strong>${esc(session.job_role || 'Latihan wawancara')}</strong><small>${esc(metadata)}</small></span></span>
        <span class="ws-session-interviewer"><strong>${esc(interviewer.name)}</strong><small>${esc(interviewer.title)}</small></span>
        <span class="ws-session-date">${timeMarkup(session.created_at)}</span>
        <span class="ws-session-status ws-session-status--${status}"><span aria-hidden="true"></span>${esc(statusLabels[status] || 'Status tidak dikenal')}</span>
        <span class="ws-session-score">${score}</span><span class="ws-session-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg></span>
      </a>`;
    }).join('');
  }

  function chartWidth() {
    const chart = node('trend-chart');
    const style = window.getComputedStyle?.(chart);
    const padding = (parseFloat(style?.paddingLeft) || 0) + (parseFloat(style?.paddingRight) || 0);
    return Math.max(260, Math.round(chart.clientWidth - padding || 640));
  }
  function renderTrend(assessed) {
    trendSessions = assessed;
    const recent = assessed.slice(-8);
    const last = recent.at(-1);
    node('trend-summary').textContent = last ? `Skor terakhir ${points(last.total_score)}/100` : 'Skor akan tampil setelah latihan dinilai.';
    node('trend-range').textContent = recent.length > 1 ? `${recent.length} sesi terakhir yang dinilai` : recent.length ? '1 sesi dinilai' : 'Belum ada sesi dinilai';
    if (!recent.length) {
      node('trend-chart').innerHTML = emptyState('Belum ada skor', 'Selesaikan latihan untuk melihat perkembangannya.', false);
      return;
    }
    const width = chartWidth(), left = 42, right = 20, top = 18, bottom = 196;
    trendWidth = width;
    const coordinates = recent.map((session, index) => ({session, score: points(session.total_score),
      x: recent.length === 1 ? width / 2 : left + index * (width - left - right) / (recent.length - 1),
      y: bottom - Math.max(0, Math.min(100, session.total_score * 20)) * (bottom - top) / 100}));
    const description = `Skor latihan dalam urutan penyelesaian: ${coordinates.map(point => point.score).join(', ')} dari 100. Setiap titik membuka hasil latihan.`;
    const grid = [0, 25, 50, 75, 100].map(score => {
      const y = bottom - score * (bottom - top) / 100;
      return `<line class="ws-trend-grid" x1="${left}" y1="${y}" x2="${width - right}" y2="${y}"/><text class="ws-trend-axis" x="${left - 12}" y="${y + 4}" text-anchor="end">${score}</text>`;
    }).join('');
    const line = coordinates.length > 1 ? `<polyline class="ws-trend-line" fill="none" points="${coordinates.map(point => `${point.x},${point.y}`).join(' ')}"/>` : '';
    const links = coordinates.map(point => {
      const finished = completedAt(point.session);
      const label = `${point.session.job_role || 'Latihan wawancara'}, ${dateText(finished)}, ${point.score}/100. Buka hasil latihan.`;
      return `<a href="${esc(resultPath(point.session))}" tabindex="0" aria-label="${esc(label)}"><title>${esc(label)}</title><circle class="ws-trend-hit" cx="${point.x}" cy="${point.y}" r="12" fill="transparent"/><circle class="ws-trend-point" cx="${point.x}" cy="${point.y}" r="5"/></a>`;
    }).join('');
    const labelIndices = new Set([0, Math.floor((recent.length - 1) / 2), recent.length - 1]);
    const labels = coordinates.filter((point, index) => labelIndices.has(index)).map(point => {
      const time = completedAt(point.session);
      return `<text class="ws-trend-label" x="${point.x}" y="224" text-anchor="${point.x === left ? 'start' : point.x === width - right ? 'end' : 'middle'}">${esc(time ? shortDateFormatter.format(new Date(time)) : '-')}</text>`;
    }).join('');
    node('trend-chart').innerHTML = `<svg class="ws-trend-svg" viewBox="0 0 ${width} 240" role="group" aria-label="${esc(description)}"><desc>${esc(description)}</desc>${grid}${line}${links}${labels}</svg>`;
  }
  function resizeTrend() {
    if (disposed || !loaded || !trendSessions.length || chartWidth() === trendWidth) return;
    cancelAnimationFrame(chartResizeFrame);
    chartResizeFrame = requestAnimationFrame(() => {
      chartResizeFrame = null;
      if (!disposed && loaded) renderTrend(trendSessions);
    });
  }

  async function loadFocus(latest) {
    focusController?.abort();
    const generation = ++focusGeneration;
    node('focus-caption').textContent = latest ? 'Dari sesi terakhir yang dinilai' : 'Fokus mengikuti hasil latihan Anda';
    if (!latest) {
      node('focus-content').innerHTML = emptyState('Belum ada fokus latihan', 'Fokus tersedia setelah latihan dinilai.');
      return;
    }
    const controller = new AbortController(); focusController = controller;
    node('focus-content').innerHTML = '<p class="ws-focus-note" role="status">Memuat fokus latihan…</p>';
    const link = `<a class="ws-text-link" href="${esc(resultPath(latest))}">Buka hasil</a>`;
    try {
      const result = await api(`/api/sessions/${encodeURIComponent(String(latest.id))}/result`, {signal: controller.signal});
      if (disposed || generation !== focusGeneration) return;
      if (result.session_id !== latest.id || !Array.isArray(result.competencies)) throw new Error('Fokus belum tersedia.');
      const weakest = result.competencies.filter(competency => typeof competency.score === 'number' && Number.isFinite(competency.score) &&
        typeof competency.weight === 'number' && Number.isFinite(competency.weight) && competency.weight > 0)
        .sort((first, second) => first.score - second.score).slice(0, 3);
      if (!weakest.length) {
        node('focus-content').innerHTML = `${emptyState('Belum ada kompetensi terukur', 'Lihat hasil untuk rincian sesi ini.', false)}${link}`;
        return;
      }
      const rows = weakest.map(competency => {
        const label = competencyLabels[competency.key] || competency.name || String(competency.key || '').replace(/_/g, ' ');
        const score = points(competency.score);
        return `<li class="ws-focus-item"><span class="ws-focus-label">${esc(label)}</span><span class="ws-focus-score">${score}<small>/100</small></span><span class="ws-focus-meter" aria-hidden="true"><span style="width:${Math.max(0, Math.min(100, score))}%"></span></span></li>`;
      }).join('');
      node('focus-content').innerHTML = `<p class="ws-focus-note">Mulai dari skor terendah berikut.</p><ul class="ws-focus-list">${rows}</ul>${link}`;
    } catch {
      if (disposed || generation !== focusGeneration) return;
      node('focus-content').innerHTML = `<p class="ws-focus-note">Fokus belum dapat dimuat.</p><div class="ws-focus-actions">${link}<button id="focus-retry" class="ws-button ws-button--secondary" type="button">Coba lagi</button></div>`;
      node('focus-content').querySelector('#focus-retry')?.addEventListener('click', () => loadFocus(latest));
    } finally {if (focusController === controller) focusController = null;}
  }
  async function renderDashboard() {
    const allAssessed = sessions.filter(scored).sort((first, second) => completedAt(first) - completedAt(second));
    const policy = session => session.aggregation_policy_version || 'legacy-owner-per-question';
    const assessed = allAssessed.filter(session => policy(session) === policy(allAssessed.at(-1) || {}));
    node('stat-completed').textContent = String(sessions.filter(session => session.status === 'done').length);
    node('stat-average').textContent = assessed.length ? String(points(assessed.reduce((total, session) => total + session.total_score, 0) / assessed.length)) : '-';
    node('stat-best').textContent = assessed.length ? String(points(Math.max(...assessed.map(session => session.total_score)))) : '-';
    const delta = assessed.length >= 2 ? Math.round((assessed.at(-1).total_score - assessed[0].total_score) * 20) : null;
    node('stat-change').textContent = delta === null ? '-' : `${delta > 0 ? '+' : ''}${delta}`;
    node('stat-change').dataset.direction = delta === null || delta === 0 ? 'flat' : delta > 0 ? 'up' : 'down';
    node('stat-change-note').textContent = delta === null ? 'Perlu 2 sesi yang dinilai' : 'Skor terakhir vs pertama';
    node('workspace-data').hidden = false;
    node('workspace-loading').hidden = true;
    renderTrend(assessed);
    node('workspace-data').hidden = false;
    node('workspace-loading').hidden = true;
    await loadFocus(assessed.at(-1));
  }

  const interviewerInput = page === 'history' ? document.querySelector('input[name="history_interviewer"]') : null;
  const sortInput = page === 'history' ? document.querySelector('input[name="history_sort"]') : null;
  const tabs = page === 'history' ? [...node('history-tabs').querySelectorAll('[data-history-status]')] : [];
  function matchesStatus(session, filter) {return filter === 'all' || (filter === 'active' ? activeStatuses.has(session.status) : session.status === filter);}
  function renderHistory() {
    if (!loaded) return;
    const search = node('history-search').value.trim().toLocaleLowerCase('id-ID');
    const interviewer = interviewerInput.value;
    const sort = sortInput.value;
    const filtered = sessions.filter(session => matchesStatus(session, historyStatus) && (interviewer === 'all' || panelRoles(session).includes(interviewer)) &&
      (!search || [session.job_role, session.company, persona(session).name, persona(session).title].filter(Boolean).join(' ').toLocaleLowerCase('id-ID').includes(search)));
    filtered.sort((first, second) => {
      if (sort === 'score') {
        const firstScore = scored(first) ? first.total_score : -Infinity;
        const secondScore = scored(second) ? second.total_score : -Infinity;
        if (firstScore !== secondScore) return secondScore - firstScore;
      }
      return sort === 'oldest' ? byCreated(first, second) : byCreated(second, first);
    });
    const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    historyPage = Math.max(1, Math.min(pages, historyPage));
    const visible = filtered.slice((historyPage - 1) * pageSize, historyPage * pageSize);
    node('history-list').innerHTML = visible.length ? sessionRows(visible) : sessions.length ?
      emptyState('Tidak ada latihan yang cocok', 'Ubah pencarian atau atur ulang filter.', false) : emptyState('Belum ada latihan', 'Mulai sesi pertama Anda.');
    node('history-count').textContent = `${filtered.length} dari ${sessions.length} latihan`;
    node('history-page').textContent = `Halaman ${historyPage} dari ${pages}`;
    node('history-prev').disabled = historyPage <= 1;
    node('history-next').disabled = historyPage >= pages;
    node('history-reset').hidden = !search && interviewer === 'all' && historyStatus === 'all' && sort === 'newest';
    for (const tab of tabs) {
      const selected = tab.dataset.historyStatus === historyStatus;
      tab.setAttribute('aria-pressed', String(selected));
      tab.classList.toggle('is-active', selected);
      const count = tab.querySelector('[data-count]');
      if (count) count.textContent = String(sessions.filter(session => matchesStatus(session, tab.dataset.historyStatus)).length);
    }
  }
  function filtersChanged() {historyPage = 1; renderHistory();}
  if (page === 'history') {
    node('history-search').addEventListener('input', filtersChanged);
    interviewerInput.addEventListener('change', filtersChanged);
    sortInput.addEventListener('change', filtersChanged);
    for (const tab of tabs) tab.addEventListener('click', () => {historyStatus = tab.dataset.historyStatus; filtersChanged();});
    node('history-prev').addEventListener('click', () => {historyPage--; renderHistory();});
    node('history-next').addEventListener('click', () => {historyPage++; renderHistory();});
    node('history-reset').addEventListener('click', () => {
      node('history-search').value = ''; historyStatus = 'all'; historyPage = 1;
      for (const [input, value] of [[interviewerInput, 'all'], [sortInput, 'newest']]) {
        input.value = value;
        input.dispatchEvent(new Event('change', {bubbles: true}));
      }
      renderHistory();
    });
  }

  async function load() {
    if (loading || disposed) return;
    loading = true; loaded = false;
    const generation = ++loadGeneration;
    const controller = new AbortController(); loadController = controller;
    node('workspace-error').hidden = true;
    node('workspace-retry').disabled = true;
    node('workspace-loading').hidden = false;
    node('workspace-data').hidden = true;
    try {
      const data = await api('/api/sessions', {signal: controller.signal});
      if (disposed || generation !== loadGeneration) return;
      if (!Array.isArray(data.items)) throw new Error('Data latihan belum dapat dimuat.');
      sessions = data.items; loaded = true;
      if (page === 'dashboard') await renderDashboard();
      else {renderHistory(); node('workspace-data').hidden = false;}
    } catch (cause) {
      if (disposed || generation !== loadGeneration) return;
      node('workspace-error').querySelector('p').textContent = cause?.message || 'Data latihan belum dapat dimuat. Coba lagi.';
      node('workspace-error').hidden = false;
    } finally {
      if (loadController === controller) loadController = null;
      if (!disposed && generation === loadGeneration) {
        loading = false;
        node('workspace-loading').hidden = true;
        node('workspace-retry').disabled = false;
      }
    }
  }
  node('workspace-retry').addEventListener('click', load);
  window.addEventListener('preptiva:languagechange', () => {
    dateFormatter = new Intl.DateTimeFormat(window.PreptivaI18n.locale, {day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
    shortDateFormatter = new Intl.DateTimeFormat(window.PreptivaI18n.locale, {day:'numeric',month:'short'});
    document.querySelectorAll('.ws-session-date time[datetime]').forEach(time => {time.textContent = dateText(time.dateTime);});
    if (page === 'dashboard' && loaded) renderTrend(trendSessions);
  });
  if (page === 'dashboard') {
    if (window.ResizeObserver) {
      chartObserver = new window.ResizeObserver(resizeTrend);
      chartObserver.observe(node('trend-chart'));
    }
    window.addEventListener('resize', resizeTrend);
  }
  window.addEventListener('pagehide', () => {
    disposed = true; loadGeneration++; focusGeneration++;
    loadController?.abort(); focusController?.abort();
    cancelAnimationFrame(chartResizeFrame); chartObserver?.disconnect();
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    disposed = false; loading = false;
    chartObserver?.observe(node('trend-chart'));
    load();
  });
  load();
})();
