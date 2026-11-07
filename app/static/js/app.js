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
    const retryAfter = Number(response.headers.get('Retry-After'));
    if (response.status === 429 && Number.isFinite(retryAfter) && retryAfter > 0 && retryAfter <= 86400) {
      error += window.PreptivaI18n?.language === 'en'
        ? ` Try again in ${Math.ceil(retryAfter)} seconds.` : ` Coba lagi dalam ${Math.ceil(retryAfter)} detik.`;
    }
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
  event.preventDefault(); const button = event.target.querySelector('button[type=submit]');
  if (button.disabled) return;
  const originalLabel = button.textContent;
  button.disabled = true; button.textContent = 'Memproses…';
  event.target.setAttribute('aria-busy', 'true');
  $('#auth-error').hidden = true;
  const data = Object.fromEntries(new FormData(event.target));
  if (page === 'register') {data.age = Number(data.age); data.agree = !!data.agree;}
  try {await postJSON(`/api/auth/${page}`, data); location.assign('/dashboard');}
  catch (error) {
    showError('#auth-error', error instanceof TypeError ? 'Koneksi terputus. Coba lagi.' : error);
    button.disabled = false; button.textContent = originalLabel;
    event.target.removeAttribute('aria-busy');
  }
});
function jobRubricEligible(role, mode, persona) {
  return String(role || '').trim().replace(/\s+/g, ' ').toLowerCase() === 'engineering manager'
    && mode === 'single' && persona === 'manager';
}
function updateJobRubricOption() {
  const container = $('#job-rubric-option');
  if (!container) return;
  const enabled = jobRubricEligible($('[name=job_role]')?.value, $('[name=interview_mode]')?.value,
    $('[name=interviewer]:checked')?.value);
  const checkbox = $('[name=use_job_rubric]');
  container.hidden = !enabled; checkbox.disabled = !enabled;
  if (!enabled) checkbox.checked = false;
}
$('[name=job_role]')?.addEventListener('input', updateJobRubricOption);
$('[name=job_role]')?.addEventListener('change', updateJobRubricOption);
document.querySelectorAll('[name=interviewer]').forEach(input => input.addEventListener('change', updateJobRubricOption));
updateJobRubricOption();
$('#session-form')?.addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button[type=submit]'); button.disabled = true;
  const originalContent = button.innerHTML;
  event.target.setAttribute('aria-busy', 'true');
  button.textContent = 'Menyiapkan sesi…'; $('#form-error').hidden = true;
  try {
    updateJobRubricOption();
    const form = new FormData(event.target);
    if (form.get('interview_mode') === 'panel' && form.getAll('panel').length < 2) throw new Error('Pilih minimal dua pewawancara untuk panel.');
    const data = await api('/api/sessions', {method:'POST', body:form}); location.assign(`/sesi/${data.session_id}/ruang`);
  }
  catch(error) {showError('#form-error', error); button.disabled = false; button.innerHTML = originalContent; event.target.removeAttribute('aria-busy'); $('#form-error').scrollIntoView({block:'nearest'});}
});
const list = items => `<ul>${(items || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul>`;

function sourceLink(source) {
  const title = esc(source.source_title || 'Sumber indikator');
  try {
    const url = new URL(source.url);
    if (url.protocol !== 'https:' || url.username || url.password) return title;
    return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`;
  } catch {return title;}
}
function indicatorDetails(score) {
  if (!Array.isArray(score.indicators_met)) return '';
  const evidence = Array.isArray(score.indicator_evidence) ? score.indicator_evidence : [];
  const next = Array.isArray(score.next_level_indicators) ? score.next_level_indicators : [];
  const sources = Array.isArray(score.sources) ? score.sources : [];
  const origins = {internal:'Disusun internal',adapted:'Diadaptasi',taken:'Diambil dari sumber'};
  return `<section class="indicator-chain" aria-label="Penjelasan indikator penilaian"><h4>Indikator yang didukung bukti</h4>${evidence.length ? evidence.map(item => `<article class="indicator-evidence"><strong>Tingkat ${esc(item.level)} · ${esc(item.behavior)}</strong><blockquote>“${esc(item.quote)}”${item.turn_id ? `<small>Giliran ${esc(item.turn_id)}</small>` : ''}</blockquote><small class="muted">${esc(item.indicator_id)}</small></article>`).join('') : '<p>Belum ada indikator dengan bukti yang terverifikasi.</p>'}${score.next_level_gap ? `<h4>${score.status === 'measured' ? 'Alasan belum mencapai tingkat berikutnya' : 'Bukti yang masih perlu dilengkapi'}</h4><p>${esc(score.next_level_gap)}</p>` : ''}${next.length ? `<ul class="next-indicators">${next.map(item => `<li>Tingkat ${esc(item.level)} · ${esc(item.behavior)}</li>`).join('')}</ul>` : ''}${sources.length ? `<details class="indicator-sources"><summary>Asal indikator dan rujukan</summary><p>Rujukan menjelaskan landasan metodologi atau pekerjaan. Indikator berlabel internal merupakan rancangan Preptiva, bukan skala skor yang ditetapkan sumber.</p>${sources.map(source => `<article><strong>${esc(source.indicator_id)} · ${esc(origins[source.origin] || source.origin)}</strong><p>${sourceLink(source)}${source.source_edition ? ` · ${esc(source.source_edition)}` : ''}</p>${source.source_locator ? `<small>${esc(source.source_locator)}</small>` : ''}${source.source_excerpt ? `<blockquote>“${esc(source.source_excerpt)}”</blockquote>` : ''}${source.application ? `<p>${esc(source.application)}</p>` : ''}</article>`).join('')}</details>` : ''}</section>`;
}
function assessmentNotice(assessment) {
  if (!assessment?.profile_id) return '';
  const pending = assessment.status === 'draft_pending_expert_review' || assessment.job_reviewed_by_human === false;
  return `<section class="notice rubric-notice" aria-label="Status rubrik khusus"><strong>${esc(assessment.title || 'Rubrik khusus pekerjaan')}${pending ? ' · Draf' : ''}</strong><p>${pending ? 'Indikator dan bobot belum ditinjau ahli pekerjaan. ' : ''}${assessment.validated ? 'Hasil berlaku hanya untuk konteks validasi yang tercatat.' : 'Rubrik ini belum divalidasi. Skor dan indikator digunakan untuk refleksi latihan.'}</p>${assessment.scope?.job_roles?.length ? `<small>Konteks: ${esc(assessment.scope.job_roles.join(', '))} · ${esc(assessment.scope.interviewer || '')}</small>` : ''}</section>`;
}
function evidenceDetails(scores, names = {}) {
  return Object.entries(scores || {}).map(([key, s]) => {
    if (!s.status) return '';
    const status = {measured:'Bukti cukup',insufficient:'Bukti belum cukup',not_assessed:'Belum dinilai',unusable_transcript:'Transkrip tidak dapat digunakan'}[s.status];
    return `<div class="evidence-detail"><strong>${esc(names[key] || key.replaceAll('_',' '))} · ${esc(status)}${Array.isArray(s.indicators_met) && s.status === 'measured' ? ` · ${esc(s.score)}/5` : ''}</strong>${s.score_status === 'provisional' ? '<p>Skor sementara tidak masuk skor total.</p>' : ''}${(s.source_refs || []).map(ref => `<blockquote>“${esc(ref.quote)}” <small>Giliran ${esc(ref.turn_id)}</small></blockquote>`).join('')}${s.rationale ? `<p>${esc(s.rationale)}</p>` : ''}${indicatorDetails(s)}</div>`;
  }).join('');
}

async function loadResult() {
  const base = `/api/sessions/${document.body.dataset.sid}`;
  try {
    const state = await api(`${base}/state`);
    $('#result-role').innerHTML = [state.job_role ? `<span data-ui-content>${esc(state.job_role)}</span>` : '', esc({junior:'Junior',middle:'Middle',senior:'Senior',manager:'Manager'}[state.level] || state.level || '')].filter(Boolean).join(' · ') || 'Ringkasan latihan Anda.';
    if (state.status === 'failed') throw new Error(state.error || 'Sesi gagal. Silakan buat latihan baru.');
    if (state.status === 'evaluation_failed') {$('#result-content').innerHTML = `<section class="panel"><h2>Penilaian belum selesai</h2><p>Jawaban Anda tersimpan. Coba penilaian kembali.</p><button class="button" id="retry-evaluation">Nilai ulang</button></section>`; $('#retry-evaluation').onclick = async () => {try {await postJSON(`${base}/finish`); await loadResult();} catch(e) {toast(e.message);}}; return;}
    if (state.status === 'scoring') {setTimeout(loadResult, 2000); return;}
    if (state.status !== 'done') {$('#result-content').innerHTML = `<div class="panel empty"><h2>Latihan belum selesai</h2><p>Selesaikan percakapan untuk melihat refleksi Anda.</p><a class="button" href="/sesi/${esc(document.body.dataset.sid)}/ruang">Buka ruang wawancara ↗</a></div>`;return;}
    const r = await api(`${base}/result`);
    $('#result-role').innerHTML = [`<span data-ui-content>${esc(r.job_role)}</span>`, esc({junior:'Junior',middle:'Middle',senior:'Senior',manager:'Manager'}[r.level] || r.level), r.panel_results?.length > 1 ? `<span>Panel ${r.panel_results.length} pewawancara</span>` : ''].filter(Boolean).join(' · ');
    $('#result-content').innerHTML = renderResult(r);
  } catch(e) {$('#result-content').innerHTML = `<div class="error" role="alert">${esc(e.message)}</div>`;}
}
if (page === 'result') loadResult();
