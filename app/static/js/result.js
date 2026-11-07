'use strict';
const resultChevron = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
function resultPoints(score) {return typeof score === 'number' && Number.isFinite(score) ? Math.round(Math.max(0, Math.min(5, score)) * 20) : null;}
function resultList(items, empty) {
  return items?.length ? `<ul class="result-feedback-list">${items.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : `<p class="result-muted">${esc(empty)}</p>`;
}
function renderResult(r) {
  const competencies = r.competencies || [], items = r.items || [], review = r.review || {}, assessment = r.assessment || {};
  const names = Object.fromEntries(competencies.map(c => [c.key, c.name]));
  const score = resultPoints(r.total_score), delta = typeof r.delta === 'number' ? Math.round(r.delta * 20) : null;
  const coverage = r.coverage, answered = items.filter(item => !item.skipped).length;
  const personNames = {hr: 'Rina', user: 'Andi', manager: 'Pak Hendra'};
  const personRoles = {hr: 'HR', user: 'User', manager: 'Manager'};
  const statusLabels = {measured: 'Bukti cukup', insufficient: 'Bukti terbatas', not_assessed: 'Belum dinilai', unusable_transcript: 'Transkrip tidak dapat digunakan'};
  const scoreLabel = score === null ? 'Belum terukur' : r.label || 'Hasil latihan';
  return `${assessmentNotice(assessment)}
    <section class="ws-panel result-overview" aria-label="Ringkasan hasil">
      <div class="result-score">
        <h2>Skor keseluruhan</h2>
        <div class="result-score-ring" style="--score-progress:${score ?? 0}%" role="img" aria-label="${score === null ? 'Skor belum terukur' : `Skor ${score} dari 100`}"><div><span class="score-number">${score ?? '—'}</span><small>/100</small></div></div>
        <strong class="score-label">${esc(scoreLabel)}</strong>
        <p>Penilaian untuk latihan wawancara.</p>
      </div>
      <div class="result-summary">
        <h2>Ringkasan wawancara</h2>
        <p class="result-summary-text">${esc(review.summary || 'Ringkasan belum tersedia untuk sesi ini.')}</p>
        <div class="result-metrics">
          <div><span>Perubahan skor</span><strong class="${delta > 0 ? 'result-positive' : delta < 0 ? 'result-negative' : ''}">${delta === null ? '—' : `${delta > 0 ? '+' : ''}${delta}`}<small>${delta === null ? '' : 'poin'}</small></strong><p>${delta === null ? 'Belum ada pembanding' : 'Dari sesi sebanding sebelumnya'}</p></div>
          <div><span class="coverage-summary">Cakupan bukti</span><strong>${coverage ? `${coverage.weighted_percent}%` : '—'}</strong><p>${coverage ? `${coverage.measured} dari ${coverage.total} kompetensi` : 'Tidak tersedia pada sesi ini'}</p></div>
          <div><span>Jawaban</span><strong>${answered}<small>ditinjau</small></strong><p>${items.some(item => item.skipped) ? `${items.filter(item => item.skipped).length} pertanyaan dilewati` : 'Tersimpan dalam sesi ini'}</p></div>
        </div>
      </div>
    </section>
    ${(r.panel_results || []).length > 1 ? `<section class="result-panel-scores" aria-label="Hasil per interviewer">${r.panel_results.map(p => `<article class="ws-panel"><div><h2>${esc(personNames[p.interviewer] || p.interviewer)}</h2><p>${esc(personRoles[p.interviewer] || 'Pewawancara')}</p></div><strong>${resultPoints(p.total_score) ?? '—'}<small>/100</small></strong></article>`).join('')}</section>` : ''}
    <div class="result-analysis">
      <section class="ws-panel result-competencies">
        <div class="ws-panel-heading"><div><h2>Kompetensi</h2><p>Skor berdasarkan bukti jawaban.</p></div><span class="result-scale">/100</span></div>
        <div class="result-competency-list">${competencies.length ? competencies.map(c => {
          const value = resultPoints(c.score);
          return `<article class="competency result-competency"><div class="result-competency-label"><h3>${esc(c.name)}</h3><span>${esc(statusLabels[c.status] || (value === null ? 'Belum terukur' : ''))}</span></div><strong>${value ?? '—'}</strong><div class="result-competency-track" aria-hidden="true"><span style="width:${value ?? 0}%"></span></div>${c.evidence?.length ? `<details class="result-competency-evidence"><summary>Lihat bukti ${resultChevron}</summary>${c.evidence.map(quote => `<blockquote>${esc(quote)}</blockquote>`).join('')}</details>` : ''}</article>`;
        }).join('') : '<p class="result-muted">Belum ada kompetensi yang dinilai.</p>'}</div>
        <p class="result-coverage-note">${coverage ? 'Kompetensi dengan bukti terbatas tidak dimasukkan ke skor total.' : 'Skor sesi ini mengikuti kebijakan penilaian versi sebelumnya.'}</p>
      </section>
      <section class="ws-panel result-feedback">
        <div class="result-feedback-section"><h2>Yang sudah kuat</h2>${resultList(review.strengths, 'Belum ada kekuatan yang dirangkum.')}</div>
        <div class="result-feedback-section"><h2>Fokus perbaikan</h2>${resultList(review.improvements, 'Belum ada perbaikan yang dirangkum.')}</div>
        ${Object.keys(r.star_summary || {}).length ? `<details class="result-star"><summary>Struktur jawaban STAR ${resultChevron}</summary><div>${[['situation', 'Situasi'], ['task', 'Tugas'], ['action', 'Tindakan'], ['result', 'Hasil']].map(([key, name]) => `<p><span>${name}</span><strong>${typeof r.star_summary[key] === 'number' ? `${Math.round(r.star_summary[key])}%` : r.star_summary[key] ? 'Terlihat' : 'Belum terlihat'}</strong></p>`).join('')}</div><small>Bagian yang muncul pada jawaban sesi ini.</small></details>` : ''}
      </section>
    </div>
    ${review.study_recommendations?.length ? `<section class="ws-panel result-next"><div class="ws-panel-heading"><div><h2>Latihan berikutnya</h2><p>Rekomendasi dari sesi ini.</p></div></div><div class="result-next-list">${review.study_recommendations.map((item, index) => `<article><span class="result-step-number">${String(index + 1).padStart(2, '0')}</span><div><h3>${esc(item.topic)}</h3><p>${esc(item.action)}</p>${item.reason ? `<details><summary>Alasan rekomendasi ${resultChevron}</summary><p>${esc(item.reason)}</p></details>` : ''}</div></article>`).join('')}</div></section>` : ''}
    <section class="ws-panel result-answers"><div class="ws-panel-heading"><div><h2>Tinjau jawaban</h2><p>Pertanyaan, transkrip, dan umpan balik.</p></div><span class="result-answer-count">${items.length} jawaban</span></div>
      ${items.map((item, index) => {
        const feedback = item.feedback || {};
        return `<details class="review-item result-answer"><summary><span class="result-step-number">${String(index + 1).padStart(2, '0')}</span><span class="result-answer-heading"><strong>${esc(item.question_text)}</strong><small>${esc([item.persona?.name, item.kind === 'follow_up' ? 'Pertanyaan lanjutan' : `Pertanyaan ${item.main_order}`, item.skipped ? 'Dilewati' : item.input_mode === 'text' ? 'Jawaban teks' : 'Jawaban suara'].filter(Boolean).join(' · '))}</small></span>${resultChevron}</summary><div class="result-answer-body">
          <h3>Jawaban Anda</h3><div class="transcript">${item.skipped ? 'Pertanyaan dilewati. Tidak ada jawaban yang dinilai.' : esc(item.transcript || 'Transkrip tidak tersedia.')}</div>
          ${!item.skipped ? `${feedback.strengths?.length ? `<h3>Yang sudah baik</h3>${resultList(feedback.strengths, '')}` : ''}${feedback.improvements?.length ? `<h3>Saran perbaikan</h3>${resultList(feedback.improvements, '')}` : ''}${feedback.better_answer_tip ? `<div class="result-answer-tip"><h3>Untuk jawaban berikutnya</h3><p>${esc(feedback.better_answer_tip)}</p></div>` : ''}${Object.keys(item.competency_scores || {}).length ? `<details class="result-evidence"><summary>Rincian bukti penilaian ${resultChevron}</summary>${evidenceDetails(item.competency_scores, names)}</details>` : ''}${item.input_mode !== 'text' && Number.isFinite(item.wpm) ? `<p class="result-audio-meta">${item.wpm} kata/menit · ${item.filler_count ?? 0} kata pengisi. Konteks penyampaian, bukan penalti otomatis.</p>` : ''}` : ''}
        </div></details>`;
      }).join('') || '<p class="result-muted">Belum ada jawaban tersimpan.</p>'}
    </section>
    <details class="result-method"><summary>Informasi penilaian ${resultChevron}</summary><p>Rubrik ${esc(assessment.version || 'tidak tercatat')} · ${assessment.validated ? 'Tervalidasi sesuai konteks yang tercatat.' : 'Belum divalidasi untuk seleksi kerja.'} Skor digunakan untuk refleksi latihan.</p></details>`;
}
