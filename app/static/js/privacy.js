'use strict';
(() => {
  const ui = value => window.PreptivaI18n?.t(value) ?? value;
  function element(tag, text, className) {
    const value = document.createElement(tag);
    if (text !== undefined) value.textContent = ui(text);
    if (className) value.className = className;
    return value;
  }
  function download(receipt) {
    const content = new Blob([JSON.stringify(receipt, null, 2) + '\n'], {type: 'application/json'});
    const url = URL.createObjectURL(content);
    const link = document.createElement('a');
    link.href = url;
    link.download = `preptiva-deletion-${String(receipt.id || 'receipt').replace(/[^a-zA-Z0-9_-]/g, '')}.json`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function showReceipt(target, receipt) {
    target.replaceChildren(); target.hidden = false; target.tabIndex = -1;
    const complete = receipt.status === 'complete';
    target.dataset.state = complete ? 'complete' : 'pending_files';
    target.append(element('h3', complete ? 'Penghapusan selesai.' : 'Penghapusan berkas masih diproses.'));
    target.append(element('p', complete ? 'Tanda terima ini mencatat data yang telah dihapus dari aplikasi.' :
      'Data dalam database sudah dihapus. Pembersihan berkas akan dicoba kembali secara otomatis.'));
    const details = element('dl', undefined, 'privacy-receipt-details');
    const identifier = element('dd', String(receipt.id || '—'));
    identifier.dataset.uiContent = '';
    details.append(element('dt', 'ID tanda terima'), identifier);
    const labels = {sessions: 'Sesi', answers: 'Jawaban', questions: 'Pertanyaan', files: 'Berkas'};
    for (const [key, label] of Object.entries(labels)) {
      const count = receipt.counts?.[key];
      if (Number.isInteger(count) && count >= 0) details.append(element('dt', label), element('dd', String(count)));
    }
    target.append(details);
    target.append(element('p', 'Salinan pada provider AI dan backup dikelola terpisah; tanda terima ini tidak menyatakan penghapusan dari layanan tersebut.', 'privacy-note'));
    const button = element('button', 'Unduh tanda terima', 'ws-button ws-button--secondary');
    button.type = 'button'; button.addEventListener('click', () => download(receipt));
    target.append(button); target.focus({preventScroll:true});
  }
  async function loadPolicy(target, options = {}) {
    try {
      const policy = await api('/api/privacy/policy', options);
      const details = element('dl', undefined, 'privacy-policy-details');
      for (const [label, value] of [['Audio yang disimpan', policy.audio_days], ['Riwayat, transkrip, dan hasil', policy.history_days], ['Tanda terima penghapusan', policy.receipt_days]]) {
        if (Number.isInteger(value) && value > 0) details.append(element('dt', label), element('dd', `${value} hari`));
      }
      details.append(element('dt', 'CV tersimpan'), element('dd', 'Sampai Anda menghapus CV atau akun.'));
      target.replaceChildren(details);
      target.append(element('p', policy.retention_enabled ? 'Pembersihan otomatis berjalan secara berkala.' : 'Pembersihan otomatis belum diaktifkan oleh pengelola.', 'privacy-note'));
      target.append(element('p', 'Menghapus CV tersimpan tidak menghapus salinan dalam sesi lama. Hapus riwayat terkait untuk menghapus salinan tersebut.', 'privacy-note'));
      target.append(element('p', 'Salinan pada provider AI dan backup dikelola terpisah; tanda terima ini tidak menyatakan penghapusan dari layanan tersebut.', 'privacy-note'));
    } catch (cause) {
      if (cause?.name === 'AbortError') return;
      target.replaceChildren(element('p', 'Kebijakan retensi belum dapat dimuat. Coba muat ulang halaman.', 'privacy-error'));
    }
  }
  async function loadReceipts(target, options = {}) {
    try {
      const data = await api('/api/privacy/receipts', options);
      target.replaceChildren();
      if (!Array.isArray(data.items) || !data.items.length) {
        target.append(element('p', 'Belum ada tanda terima penghapusan.', 'privacy-note'));
        return;
      }
      const scopes = {saved_cv: 'CV tersimpan', session: 'Sesi', history: 'Riwayat latihan', account: 'Akun', retention: 'Retensi otomatis'};
      for (const receipt of data.items) {
        const row = element('div', undefined, 'privacy-receipt-row');
        const summary = element('div');
        summary.append(element('strong', scopes[receipt.scope] || 'Penghapusan data'));
        const metadata = element('small');
        const identifier = element('span', String(receipt.id)); identifier.dataset.uiContent = '';
        metadata.append(identifier, document.createTextNode(' · '), element('span', receipt.status === 'complete' ? 'Selesai' : 'Berkas menunggu pembersihan'));
        summary.append(metadata);
        const button = element('button', 'Unduh', 'ws-text-link');
        button.type = 'button'; button.addEventListener('click', () => download(receipt));
        row.append(summary, button); target.append(row);
      }
    } catch (cause) {
      if (cause?.name === 'AbortError') return;
      target.replaceChildren(element('p', 'Tanda terima belum dapat dimuat. Coba muat ulang halaman.', 'privacy-error'));
    }
  }
  function confirm(form, expected) {
    const field = form.elements.confirmation;
    field.setCustomValidity(field.value.trim() === expected ? '' : ui('Teks konfirmasi belum sesuai.'));
    return form.reportValidity();
  }
  function bindDialog(dialog, form) {
    form.elements.confirmation?.addEventListener('input', () => form.elements.confirmation.setCustomValidity(''));
    dialog.addEventListener('cancel', event => {if (form.dataset.busy === 'true') event.preventDefault();});
    dialog.addEventListener('close', () => {
      form.querySelectorAll('input[type=password]').forEach(input => {input.value = '';});
      form.elements.confirmation.value = ''; form.elements.confirmation.setCustomValidity('');
    });
  }
  function busy(form, value) {
    form.dataset.busy = String(value);
    form.setAttribute('aria-busy', String(value));
    form.querySelectorAll('button,input').forEach(input => {input.disabled = value;});
  }
  window.PreptivaPrivacy = {download, showReceipt, loadPolicy, loadReceipts, confirm, bindDialog, busy};
})();
