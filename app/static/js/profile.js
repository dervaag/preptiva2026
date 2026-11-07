'use strict';
(() => {
  if (document.body.dataset.page !== 'profile') return;
  const node = id => document.getElementById(id);
  const ui = value => window.PreptivaI18n?.t(value) ?? value;
  const personal = node('profile-personal-form'), cv = node('profile-cv-form');
  const pdf = node('profile-cv-pdf');
  const dialog = node('profile-delete-dialog');
  let hasCv = !node('profile-delete-cv').disabled;
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
      for (const key of ['name','email','gender','age']) {personal.elements[key].value = String(data[key]);personal.elements[key].defaultValue = String(data[key]);}
      document.querySelectorAll('[data-account-name]').forEach(element => {element.textContent = data.name;});
      document.querySelectorAll('[data-account-email]').forEach(element => {element.textContent = data.email;});
      document.querySelectorAll('[data-account-initial]').forEach(element => {element.textContent = data.name.slice(0,1).toUpperCase();});
      node('profile-personal-status').textContent = 'Perubahan disimpan.';
    } catch (cause) {error('profile-personal-error',cause);}
    finally {button.disabled = false;button.textContent = label;personal.removeAttribute('aria-busy');}
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
  node('profile-delete-cv').addEventListener('click', () => {if(hasCv){node('profile-delete-error').hidden=true;dialog.showModal();}});
  node('profile-cancel-delete').addEventListener('click', () => dialog.close());
  node('profile-confirm-delete').addEventListener('click', async event => {
    const button=event.currentTarget;if(button.disabled)return;button.disabled=true;
    try{updateCv(await api('/api/profile/cv',{method:'DELETE'}));node('profile-cv-status').textContent='CV dihapus.';dialog.close();}
    catch(cause){error('profile-delete-error',cause);}
    finally{button.disabled=false;}
  });
  window.addEventListener('preptiva:languagechange', validatePdf);
  validatePdf();
})();
