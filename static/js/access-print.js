(() => {
  const button = document.querySelector('[data-print-access]');
  if (!button) return;
  button.addEventListener('click', () => window.print());
})();
