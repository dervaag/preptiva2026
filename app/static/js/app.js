'use strict';
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options = {}) {
  const response = await fetch(path, {credentials:'same-origin', ...options});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.includes('/auth/')) location.assign('/login');
    let error = data.detail || 'Permintaan gagal.';
    if (Array.isArray(error)) error = error.map(e => `${e.loc.at(-1)}: ${e.msg}`).join('\n');
    throw new Error(error);
  }
  return data;
}
function showError(selector, error) { const el = $(selector); el.textContent = error.message || error; el.hidden = false; }
function toast(message) { const el = $('#toast'); el.textContent = message; el.hidden = false; setTimeout(() => {el.hidden = true;}, 5000); }
const postJSON = (path, data = {}) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
const page = document.body.dataset.page;
$('#logout')?.addEventListener('click', async () => {try {await postJSON('/api/auth/logout'); location.assign('/login');} catch (e) {toast(e.message);}});
$('#today') && ($('#today').textContent = new Intl.DateTimeFormat('id-ID', {day:'numeric',month:'long',year:'numeric'}).format(new Date()));
$('#auth-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button[type=submit]'); button.disabled = true;
  $('#auth-error').hidden = true;
  const data = Object.fromEntries(new FormData(event.target));
  if (page === 'register') {data.age = Number(data.age); data.agree = !!data.agree;}
  try {await postJSON(`/api/auth/${page}`, data); location.assign('/dashboard');}
  catch (error) {showError('#auth-error', error); button.disabled = false;}
});
$('#interview-mode')?.addEventListener('change', event => {
  const panel = event.target.value === 'panel';
  $('#single-personas').hidden = panel; $('#panel-personas').hidden = !panel;
  document.querySelectorAll('[name=panel]').forEach(input => {input.disabled = !panel;});
});
$('#session-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button[type=submit]'); button.disabled = true;
  button.textContent = 'Menyiapkan sesi…'; $('#form-error').hidden = true;
  try {
    const form = new FormData(event.target);
    if ($('#interview-mode').value === 'panel' && form.getAll('panel').length < 2) throw new Error('Pilih minimal dua interviewer untuk panel.');
    const data = await api('/api/sessions', {method:'POST', body:form}); location.assign(`/sesi/${data.session_id}/ruang`);
  }
  catch(error) {showError('#form-error', error); button.disabled = false; button.textContent = 'Siapkan wawancara ↗';}
});
const statusNames = {preparing:'Menyiapkan',ready:'Siap dimulai',running:'Berlangsung',scoring:'Menilai',done:'Selesai',failed:'Ditutup / gagal'};
function sessionRows(items) {
  if (!items.length) return '<div class="empty"><span class="empty-icon">↗</span><h2>Perjalanan Anda dimulai di sini</h2><p>Belum ada latihan. Kenali kekuatan Anda melalui percakapan pertama.</p><a class="text-button" href="/simulasi/baru">Mulai simulasi pertama ↗</a></div>';
  return items.map(s => {
    const target = s.status === 'done' || s.status === 'scoring' ? 'hasil' : 'ruang';
    const date = new Intl.DateTimeFormat('id-ID',{day:'numeric',month:'short',year:'numeric'}).format(new Date(s.created_at));
    return `<a class="session-row" href="/sesi/${esc(s.id)}/${target}"><span class="session-icon">${s.interviewer === 'hr' ? '◉' : s.interviewer === 'manager' ? '◇' : '⌘'}</span><div class="session-info"><strong>${esc(s.job_role)}</strong><small>${esc((s.panel || [s.interviewer]).map(p => p.toUpperCase()).join(' + '))} · ${esc(s.level)} · ${date}</small></div>${s.total_score !== null ? `<span class="session-score">${Math.round(s.total_score*20)}<small class="muted"> /100</small></span>` : ''}<span class="status ${esc(s.status)}">${statusNames[s.status]}</span><span aria-hidden="true">↗</span></a>`;
  }).join('');
}
async function loadDashboard() {
  try {const data = await api('/api/dashboard'); $('#stat-total').textContent = data.total_sessions;
    $('#stat-average').innerHTML = data.avg_score === null ? '—' : `${Math.round(data.avg_score*20)} <small>/100</small>`;
    $('#stat-best').innerHTML = data.best_score === null ? '—' : `${Math.round(data.best_score*20)} <small>/100</small>`;
    $('#recent-sessions').innerHTML = sessionRows(data.recent_sessions);
  } catch(e) {$('#recent-sessions').textContent = e.message;}
}
async function loadHistory() {
  try {const {items} = await api('/api/sessions'); const render = () => {$('#history-list').innerHTML = sessionRows(items.filter(s => $('#history-filter').value === 'all' || s.status === $('#history-filter').value));}; render(); $('#history-filter').addEventListener('change', render);}
  catch(e) {$('#history-list').textContent = e.message;}
}
const list = items => `<ul>${(items || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul>`;
async function loadResult() {
  const base = `/api/sessions/${document.body.dataset.sid}`;
  try {
    const state = await api(`${base}/state`);
    if (state.status === 'failed') throw new Error(state.error || 'Sesi gagal. Silakan buat latihan baru.');
    if (state.status === 'scoring') {setTimeout(loadResult, 2000); return;}
    if (state.status !== 'done') {$('#result-content').innerHTML = `<div class="panel empty"><h2>Latihan belum selesai</h2><p>Selesaikan percakapan untuk melihat refleksi Anda.</p><a class="button" href="/sesi/${esc(document.body.dataset.sid)}/ruang">Buka ruang wawancara ↗</a></div>`;return;}
    const r = await api(`${base}/result`);
    $('#result-role').textContent = `${r.job_role} · ${r.level} · Umpan balik berbasis bukti jawaban`;
    $('#result-content').innerHTML = `<div class="result-grid"><section class="panel score-card"><span class="eyebrow">SKOR LATIHAN ANDA</span><div class="score-number">${r.total_score === null ? '—' : Math.round(r.total_score*20)}<small> /100</small></div><strong class="score-label">${esc(r.label)}</strong><p>${r.delta === null ? 'Langkah pertama untuk mengenali potensi Anda.' : `${r.delta >= 0 ? '+' : ''}${Math.round(r.delta*20)} poin dari latihan sebelumnya untuk posisi ini.`}</p></section><section class="panel score-review"><span class="eyebrow">GAMBARAN PERCAKAPAN</span><h2>Yang bisa Anda bawa ke depan</h2><p>${esc(r.review.summary)}</p><div class="star-row">${Object.entries(r.star_summary).map(([key,value]) => `<span>${value ? '✓' : '○'} ${esc(key)}</span>`).join('')}</div></section></div>${(r.panel_results || []).length > 1 ? `<section class="panel-results" aria-label="Hasil per interviewer">${r.panel_results.map(p => `<article class="panel"><span class="eyebrow">${esc(p.interviewer.toUpperCase())}</span><h3>${p.total_score === null ? 'Belum terukur' : Math.round(p.total_score*20) + ' /100'}</h3><small>Skor dari pertanyaan interviewer ini.</small></article>`).join('')}</section>` : ''}<section class="panel"><h2>Peta kompetensi Anda</h2>${r.competencies.map(c => `<div class="competency"><span>${esc(c.name)}</span><div class="bar"><span style="width:${c.score === null ? 0 : Math.max(0,Math.min(100,c.score*20))}%"></span></div><strong>${c.score === null ? '—' : Math.round(c.score*20)}</strong></div>${c.evidence.length ? `<p class="muted" style="font-size:11px">“${esc(c.evidence[0])}”</p>` : ''}`).join('')}<small class="muted">Kompetensi tanpa bukti ditandai belum terukur. Skor total menormalkan bobot kompetensi yang terukur.</small></section><div class="result-lists"><section class="panel"><h2>✧ Kekuatan Anda</h2>${list(r.review.strengths)}</section><section class="panel"><h2>↗ Ruang untuk bertumbuh</h2>${list(r.review.improvements)}</section></div><section class="panel"><h2>Langkah kecil berikutnya</h2>${(r.review.study_recommendations || []).map(s => `<article class="recommendation"><strong>${esc(s.topic)}</strong><p>${esc(s.reason)}</p><p>${esc(s.action)}</p></article>`).join('')}</section><section class="panel" style="margin-top:24px"><h2>Lihat kembali jawaban Anda</h2>${r.items.map(i => `<details class="review-item"><summary>${i.main_order}. ${i.persona ? esc(i.persona.name) + ' · ' : ''}${esc(i.question_text)} ${i.kind === 'follow_up' ? '(follow-up)' : ''}</summary><div class="transcript">${esc(i.transcript)}</div>${list(i.feedback.strengths)}${list(i.feedback.improvements)}<p>${esc(i.feedback.better_answer_tip || '')}</p><small class="muted">${i.wpm} kata/menit · ${i.filler_count} kata pengisi — konteks, bukan penalti otomatis</small></details>`).join('')}<small class="muted">Rubrik ${esc(r.assessment.version)} · ${r.assessment.validated ? 'Tervalidasi' : 'Belum divalidasi untuk seleksi kerja'}</small></section>`;
  } catch(e) {$('#result-content').innerHTML = `<div class="error" role="alert">${esc(e.message)}</div>`;}
}
if (page === 'dashboard') loadDashboard();
if (page === 'history') loadHistory();
if (page === 'result') loadResult();
