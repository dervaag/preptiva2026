'use strict';
(() => {
  const form = document.querySelector('#auth-form');
  if (!form) return;
  form.querySelectorAll('[data-password-toggle]').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(visible));
      button.setAttribute('aria-label', `${visible ? 'Sembunyikan' : 'Tampilkan'} ${button.dataset.passwordLabel}`);
    });
  });
  if (document.body.dataset.page !== 'register') return;
  const password = form.elements.password;
  const confirmation = form.elements.password_confirm;
  function validatePasswords() {
    password.setCustomValidity(password.value && (!/[A-Za-z]/.test(password.value) || !/\d/.test(password.value)) ? 'Gunakan huruf dan angka pada password.' : '');
    confirmation.setCustomValidity(confirmation.value && confirmation.value !== password.value ? 'Konfirmasi password belum sama.' : '');
  }
  [password, confirmation].forEach(input => {
    input.addEventListener('input', validatePasswords);
    input.addEventListener('change', validatePasswords);
  });
  validatePasswords();
})();
