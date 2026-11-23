/* The canonical Questionnaire remains the owner. Inline forms only submit
 * an authorized action and replace the Point with fresh server presentation. */
(() => {
  'use strict';
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest?.('[data-conversation-inline-form]');
    if (!form) return;
    event.preventDefault();
    if (form.dataset.sending === 'true') return;
    form.dataset.sending = 'true';
    const submitter = event.submitter;
    const data = new FormData(form);
    if (submitter?.name) data.set(submitter.name, submitter.value);
    const controls = [...form.querySelectorAll('button[type=submit]')];
    controls.forEach(button => { button.disabled = true; });
    let error = form.querySelector('[data-form-error]');
    if (error) error.remove();
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: data,
        credentials: 'same-origin',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
      });
      const payload = await response.json();
      if (!response.ok || typeof payload.html !== 'string') {
        throw new Error(payload.error || 'Envoi impossible.');
      }
      const doc = new DOMParser().parseFromString(payload.html, 'text/html');
      const nextPoint = doc.querySelector('[data-thread-point]');
      const previous = form.closest('[data-thread-point]');
      if (!nextPoint || !previous) throw new Error('Réponse indisponible.');
      previous.replaceWith(nextPoint);
    } catch (cause) {
      error = document.createElement('p');
      error.dataset.formError = '';
      error.setAttribute('role', 'alert');
      error.className = 'mk-inline-form-error';
      error.textContent = cause.message || 'Envoi impossible.';
      form.append(error);
      controls.forEach(button => { button.disabled = false; });
    } finally {
      delete form.dataset.sending;
    }
  });
})();
