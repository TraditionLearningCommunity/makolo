/* CSP-safe progressive enhancement for search/filter GET forms. */
(() => {
  'use strict';
  document.querySelectorAll('select[data-submit-on-change]').forEach((field) => {
    field.addEventListener('change', () => {
      if (field.form) field.form.requestSubmit();
    });
  });
})();
