(() => {
  const form = document.querySelector('[data-transport-search-form]');
  if (!form) return;
  const origin = form.querySelector('[name="origin"]');
  const destination = form.querySelector('[name="destination"]');
  const submit = form.querySelector('[type="submit"]');
  const error = form.querySelector('[data-route-error]');
  if (!origin || !destination || !submit || !error) return;

  const update = () => {
    const same = Boolean(origin.value && destination.value && origin.value === destination.value);
    submit.disabled = same;
    submit.setAttribute('aria-disabled', same ? 'true' : 'false');
    error.hidden = !same;
    error.textContent = same ? 'Le départ et la destination doivent être différents.' : '';
  };

  origin.addEventListener('change', update);
  destination.addEventListener('change', update);
  update();
})();
