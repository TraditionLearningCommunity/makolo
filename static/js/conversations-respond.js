/* A Point is the interaction surface. The existing Django command decides;
 * after owner confirmation only the affected Point is replaced. */
(() => {
  'use strict';

  document.addEventListener('submit', async (event) => {
    const form = event.target.closest?.('[data-conversation-point-response]');
    if (!form) return;
    event.preventDefault();
    if (form.dataset.sending === 'true') return;
    form.dataset.sending = 'true';
    const buttons = [...form.querySelectorAll('button[type=submit]')];
    const formData = new FormData(form);
    buttons.forEach(button => { button.disabled = true; });
    form.querySelector('[data-point-response-error]')?.remove();
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
      });
      const payload = await response.json();
      if (!response.ok || typeof payload.html !== 'string') {
        throw new Error(payload.error || 'Réponse non confirmée.');
      }
      const doc = new DOMParser().parseFromString(payload.html, 'text/html');
      const nextPoint = doc.querySelector('[data-thread-point]');
      const previous = form.closest('[data-thread-point]');
      if (!nextPoint || !previous) throw new Error('Réponse non confirmée.');
      previous.replaceWith(nextPoint);
    } catch (error) {
      const message = document.createElement('p');
      message.dataset.pointResponseError = '';
      message.setAttribute('role', 'alert');
      message.className = 'mk-inline-form-error';
      message.textContent = error.message || 'Réponse non confirmée.';
      form.append(message);
      buttons.forEach(button => { button.disabled = false; });
    } finally {
      delete form.dataset.sending;
    }
  });

  document.addEventListener('change', (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== 'radio') return;
    const form = input.closest('[data-conversation-point-response]');
    if (!form || form.dataset.sending === 'true') return;
    const direct =
      (form.dataset.singleChoice === 'true' && input.name === 'choice') ||
      (form.dataset.booleanChoice === 'true' && input.name === 'value');
    if (direct && form.checkValidity()) form.requestSubmit();
  });
})();
