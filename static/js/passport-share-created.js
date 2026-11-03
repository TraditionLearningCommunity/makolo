document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('link');
  if (!input) return;
  input.addEventListener('click', () => input.select());
  document.querySelectorAll('[data-passport-copy-created]').forEach((button) => {
    button.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(input.value); button.textContent = 'Copié'; }
      catch (_) { input.select(); window.prompt('Copiez ce lien :', input.value); }
    });
  });
});
