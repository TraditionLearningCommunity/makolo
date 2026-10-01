(() => {
  let shareRuntimePromise = null;

  const containsShareCapability = (scope) => Boolean(
    scope?.matches?.('[data-makolo-share]')
    || scope?.querySelector?.('[data-makolo-share]')
  );

  const bindShare = (scope) => {
    window.MakoloShare?.bind?.(scope || document);
  };

  const ensureShareRuntime = (scope) => {
    if (!containsShareCapability(scope)) return;
    if (window.MakoloShare) {
      bindShare(scope);
      return;
    }

    const source = document.body?.dataset.mkShareRuntime;
    if (!source) return;

    if (!shareRuntimePromise) {
      shareRuntimePromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = source;
        script.async = true;
        script.dataset.mkCapability = 'share';
        script.addEventListener('load', resolve, { once: true });
        script.addEventListener('error', reject, { once: true });
        document.head.appendChild(script);
      });
    }

    shareRuntimePromise.then(() => bindShare(scope)).catch(() => {
      shareRuntimePromise = null;
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    ensureShareRuntime(document);
  }, { once: true });

  document.addEventListener('htmx:afterSettle', (event) => {
    ensureShareRuntime(event.detail?.elt || document);
  });
})();
