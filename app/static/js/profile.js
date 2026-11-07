'use strict';
(() => {
  if (document.body.dataset.page !== 'profile') return;
  const node = id => document.getElementById(id);
  const ui = value => window.PreptivaI18n?.t(value) ?? value;
  const personal = node('profile-personal-form'), cv = node('profile-cv-form');
  const pdf = node('profile-cv-pdf');
  const dialog = node('profile-delete-dialog');
  const privacy = window.PreptivaPrivacy;
  const cvDeleteForm = node('profile-delete-form'), accountDialog = node('profile-account-dialog');
  const accountDeleteForm = node('profile-account-delete-form'), passwordForm = node('profile-password-form');
  const emailPassword = node('profile-email-password');
  let hasCv = !node('profile-delete-cv').disabled;
  let privacyController = new AbortController();
  function error(id, cause) {node(id).textContent = cause?.message || String(cause); node(id).hidden = false;}
  function validatePdf() {
    const file = pdf.files[0];
    const message = !file ? ui('Pilih file PDF CV terlebih dahulu.') :
      (!/\.pdf$/i.test(file.name) || (file.type && file.type !== 'application/pdf')) ? ui('Unggah CV dalam format PDF.') :
      file.size > 5*1024*1024 ? ui('PDF maksimal 5 MB.') : '';
    pdf.setCustomValidity(message);
    return !message;
  }
  function updateCv(data) {
    hasCv = data.has_cv;
    pdf.value = '';validatePdf();node('profile-file-selection').hidden = true;
    node('profile-delete-cv').disabled = !hasCv;
    node('profile-cv-state').textContent = hasCv ? 'CV tersimpan' : 'Belum ada CV tersimpan';
    node('profile-cv-state').dataset.saved = String(hasCv);
  }
  function syncEmailPassword() {
    const changed = personal.elements.email.value.trim().toLowerCase() !== personal.elements.email.defaultValue.trim().toLowerCase();
    node('profile-email-password-field').hidden = !changed;
    emailPassword.disabled = !changed; emailPassword.required = changed;
    if (!changed) emailPassword.value = '';
  }
  personal.elements.email.addEventListener('input', syncEmailPassword);
  personal.addEventListener('input', () => {node('profile-personal-status').textContent = ''; node('profile-personal-error').hidden = true;});
  personal.addEventListener('change', () => {node('profile-personal-status').textContent = '';});
  personal.addEventListener('submit', async event => {
    event.preventDefault();
    const button = personal.querySelector('[type=submit]');
    if (button.disabled) return;
    const label = button.textContent;
    button.disabled = true;button.textContent = 'Menyimpan…';personal.setAttribute('aria-busy','true');node('profile-personal-error').hidden = true;
    try {
      const data = await api('/api/profile', {method:'PATCH', body:new FormData(personal)});
      for (const key of ['name','email','gender','age']) {personal.elements[key].value = String(data[key] ?? '');personal.elements[key].defaultValue = String(data[key] ?? '');}
      syncEmailPassword();
      document.querySelectorAll('[data-account-name]').forEach(element => {element.textContent = data.name;});
      document.querySelectorAll('[data-account-email]').forEach(element => {element.textContent = data.email;});
      document.querySelectorAll('[data-account-initial]').forEach(element => {element.textContent = data.name.slice(0,1).toUpperCase();});
      node('profile-personal-status').textContent = 'Perubahan disimpan.';
    } catch (cause) {error('profile-personal-error',cause);}
    finally {emailPassword.value = '';button.disabled = false;button.textContent = label;personal.removeAttribute('aria-busy');}
  });
  pdf.addEventListener('change', () => {
    const file = pdf.files[0];
    validatePdf();
    node('profile-file-name').textContent = file?.name || '';node('profile-file-selection').hidden = !file;
    node('profile-cv-status').textContent = '';node('profile-cv-error').hidden = true;
    if(file && !pdf.checkValidity())pdf.reportValidity();
  });
  pdf.addEventListener('invalid', () => error('profile-cv-error',pdf.validationMessage));
  node('profile-clear-file').addEventListener('click', () => {pdf.value='';validatePdf();node('profile-file-selection').hidden=true;node('profile-cv-error').hidden=true;});
  cv.addEventListener('submit', async event => {
    event.preventDefault();
    const button = cv.querySelector('[type=submit]');
    if(button.disabled)return;
    node('profile-cv-error').hidden=true;
    if(!validatePdf()){pdf.reportValidity();return;}
    const label=button.textContent;
    button.disabled=true;node('profile-delete-cv').disabled=true;button.textContent='Menyimpan…';cv.setAttribute('aria-busy','true');
    try {
      const form=new FormData();
      form.append('cv_pdf',pdf.files[0]);
      updateCv(await api('/api/profile',{method:'PATCH',body:form}));node('profile-cv-status').textContent='CV disimpan.';
    } catch(cause){error('profile-cv-error',cause);}
    finally{button.disabled=false;node('profile-delete-cv').disabled=!hasCv;button.textContent=label;cv.removeAttribute('aria-busy');}
  });
  privacy.bindDialog(dialog, cvDeleteForm);
  privacy.bindDialog(accountDialog, accountDeleteForm);
  node('profile-delete-cv').addEventListener('click', () => {if(hasCv){cvDeleteForm.reset();node('profile-delete-error').hidden=true;dialog.showModal();}});
  node('profile-cancel-delete').addEventListener('click', () => dialog.close());
  cvDeleteForm.addEventListener('submit', async event => {
    event.preventDefault();
    if(cvDeleteForm.dataset.busy === 'true' || !privacy.confirm(cvDeleteForm, 'HAPUS CV'))return;
    const payload = {password: cvDeleteForm.elements.password.value, confirmation: cvDeleteForm.elements.confirmation.value.trim()};
    privacy.busy(cvDeleteForm, true); node('profile-delete-error').hidden=true;
    try{
      const data = await api('/api/profile/cv',{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      updateCv(data);node('profile-cv-status').textContent='CV dihapus.';
      dialog.close();privacy.showReceipt(node('profile-cv-receipt'), data.receipt);
      privacy.loadReceipts(node('profile-receipts'), {signal:privacyController.signal});
    }
    catch(cause){error('profile-delete-error',cause);}
    finally{cvDeleteForm.elements.password.value='';privacy.busy(cvDeleteForm,false);}
  });

  passwordForm.addEventListener('input', () => {
    passwordForm.elements.new_password.setCustomValidity('');passwordForm.elements.password_confirm.setCustomValidity('');
    node('profile-password-error').hidden=true;
  });
  passwordForm.addEventListener('submit', async event => {
    event.preventDefault();
    if(passwordForm.dataset.busy === 'true')return;
    const payload = Object.fromEntries(new FormData(passwordForm));
    const validPassword = payload.new_password.length >= 8 && new TextEncoder().encode(payload.new_password).length <= 72 && /[A-Za-z]/.test(payload.new_password) && /[0-9]/.test(payload.new_password);
    passwordForm.elements.new_password.setCustomValidity(validPassword ? '' : ui('Password minimal 8 karakter, berisi huruf dan angka, maksimal 72 byte.'));
    passwordForm.elements.password_confirm.setCustomValidity(payload.new_password === payload.password_confirm ? '' : ui('Konfirmasi password belum sama.'));
    if(!passwordForm.reportValidity())return;
    privacy.busy(passwordForm,true);node('profile-password-error').hidden=true;
    try {await postJSON('/api/auth/password',payload);passwordForm.reset();location.assign('/login');}
    catch(cause){error('profile-password-error',cause);}
    finally{passwordForm.querySelectorAll('input[type=password]').forEach(input => {input.value='';});privacy.busy(passwordForm,false);}
  });
  node('profile-delete-account').addEventListener('click', () => {
    accountDeleteForm.reset();node('profile-account-delete-error').hidden=true;accountDialog.showModal();
  });
  node('profile-account-cancel').addEventListener('click', () => accountDialog.close());
  accountDeleteForm.addEventListener('submit', async event => {
    event.preventDefault();
    if(accountDeleteForm.dataset.busy === 'true' || !privacy.confirm(accountDeleteForm,'HAPUS AKUN'))return;
    const payload = {password:accountDeleteForm.elements.password.value,confirmation:accountDeleteForm.elements.confirmation.value.trim()};
    privacy.busy(accountDeleteForm,true);node('profile-account-delete-error').hidden=true;
    // A late profile/status 401 must not navigate away before the deletion receipt is saved.
    privacyController.abort();
    try {
      const data=await api('/api/profile',{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      accountDialog.close();
      document.querySelectorAll('#profile-layout input[type=password], #profile-layout textarea').forEach(input => {input.value='';});
      node('profile-layout').hidden=true;node('profile-account-deleted').hidden=false;
      if(node('account-menu'))node('account-menu').hidden=true;
      privacy.showReceipt(node('profile-account-receipt'),data.receipt);
      node('profile-account-deleted-title').focus();
    }catch(cause){error('profile-account-delete-error',cause);privacyController=new AbortController();loadPrivacyPanels();}
    finally{accountDeleteForm.elements.password.value='';privacy.busy(accountDeleteForm,false);}
  });
  async function loadSessionInfo() {
    try {
      const info=await api('/api/auth/session',{signal:privacyController.signal});
      const idle=Math.round(info.idle_timeout_seconds/60), maximum=Math.round(info.absolute_timeout_seconds/3600);
      node('profile-session-info').textContent=`Sesi berakhir setelah ${idle} menit tanpa aktivitas atau maksimal ${maximum} jam.`;
    }catch(cause){if(cause?.name!=='AbortError')node('profile-session-info').textContent='Informasi sesi belum dapat dimuat.';}
  }
  function loadPrivacyPanels() {
    loadSessionInfo();
    privacy.loadPolicy(node('profile-retention-policy'), {signal:privacyController.signal});
    privacy.loadReceipts(node('profile-receipts'), {signal:privacyController.signal});
  }
  window.addEventListener('preptiva:languagechange', validatePdf);
  window.addEventListener('pagehide', () => {privacyController.abort();document.querySelectorAll('input[type=password]').forEach(input => {input.value='';});});
  validatePdf();syncEmailPassword();loadPrivacyPanels();
})();
