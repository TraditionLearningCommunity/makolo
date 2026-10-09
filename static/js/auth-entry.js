(() => {
  document.querySelectorAll('[data-auth-submit-lock]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.submitting === 'true') {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = 'true';
      form.setAttribute('aria-busy', 'true');
      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      button.disabled = true;
      button.setAttribute('aria-disabled', 'true');
      const label = button.querySelector('[data-auth-submit-label]');
      if (label && button.dataset.busyLabel) {
        label.textContent = button.dataset.busyLabel;
      }
    });
  });

  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const field = document.getElementById(button.dataset.passwordToggle);
      if (!field) return;
      const showing = field.type === 'text';
      field.type = showing ? 'password' : 'text';
      button.setAttribute('aria-pressed', showing ? 'false' : 'true');
      button.setAttribute(
        'aria-label',
        showing ? 'Afficher le mot de passe' : 'Masquer le mot de passe',
      );
    });
  });
})();
