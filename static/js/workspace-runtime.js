(() => {
  'use strict';

  const DEFAULT_TTL = 15000;
  const cache = new Map();
  const inFlight = new Map();
  const targetControllers = new WeakMap();
  const subscriptions = new Map();
  const prefetchTimers = new WeakMap();
  let observedScope = currentScope();

  function currentScope() {
    return document.getElementById('main-content')?.dataset.mkRuntimeScope || 'public';
  }

  function canonicalUrl(input) {
    return new URL(input, document.baseURI).toString();
  }

  function scopedKey(url) {
    return `${currentScope()}|${canonicalUrl(url)}`;
  }

  function publish(name, detail, target = document) {
    target.dispatchEvent(new CustomEvent(name, { bubbles: true, detail }));
  }

  function cachedValue(key, ttl) {
    const entry = cache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.storedAt > ttl) {
      cache.delete(key);
      return null;
    }
    return entry.payload;
  }

  async function fetchProjection(url, signal) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Makolo-Projection': 'workspace',
      },
      signal,
    });
    if (!response.ok) {
      const error = new Error(`Projection request failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  function load(url, options = {}) {
    const absoluteUrl = canonicalUrl(url);
    const key = scopedKey(absoluteUrl);
    const ttl = Number.isFinite(options.ttl) ? options.ttl : DEFAULT_TTL;
    if (!options.force) {
      const cached = cachedValue(key, ttl);
      if (cached) return Promise.resolve(cached);
      if (!options.signal && inFlight.has(key)) return inFlight.get(key);
    }

    const request = fetchProjection(absoluteUrl, options.signal)
      .then((payload) => {
        cache.set(key, { payload, storedAt: Date.now() });
        publish('makolo:projection-loaded', {
          key,
          scope: currentScope(),
          url: absoluteUrl,
          payload,
        });
        return payload;
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          publish('makolo:projection-error', { key, url: absoluteUrl, error });
        }
        throw error;
      })
      .finally(() => {
        if (!options.signal) inFlight.delete(key);
      });

    if (!options.signal) inFlight.set(key, request);
    return request;
  }

  function subscribe(target, url) {
    const key = scopedKey(url);
    if (!subscriptions.has(key)) subscriptions.set(key, new Set());
    subscriptions.get(key).add(target);
    target.dataset.mkProjectionTarget = 'true';
    target.dataset.mkProjectionUrl = canonicalUrl(url);
    return key;
  }

  function hydrate(target, url, options = {}) {
    if (!(target instanceof Element)) {
      return Promise.reject(new TypeError('A projection target Element is required.'));
    }
    targetControllers.get(target)?.abort();
    const controller = new AbortController();
    targetControllers.set(target, controller);
    const key = subscribe(target, url);
    target.setAttribute('aria-busy', 'true');

    return load(url, { ...options, signal: controller.signal })
      .then((payload) => {
        if (!controller.signal.aborted) {
          publish('makolo:projection-ready', { key, url: canonicalUrl(url), payload }, target);
        }
        return payload;
      })
      .finally(() => {
        if (targetControllers.get(target) === controller) {
          targetControllers.delete(target);
          target.removeAttribute('aria-busy');
        }
      });
  }

  function invalidate(urls = []) {
    const requested = Array.isArray(urls) ? urls : [urls];
    const scopePrefix = `${currentScope()}|`;
    const absoluteUrls = requested.filter(Boolean).map(canonicalUrl);
    const keys = absoluteUrls.length
      ? absoluteUrls.map((url) => `${scopePrefix}${url}`)
      : [...cache.keys()].filter((key) => key.startsWith(scopePrefix));

    for (const key of keys) cache.delete(key);
    publish('makolo:projections-invalidated', { scope: currentScope(), urls: absoluteUrls });

    for (const key of keys) {
      const targets = subscriptions.get(key);
      if (!targets) continue;
      for (const target of [...targets]) {
        if (!target.isConnected) {
          targets.delete(target);
          continue;
        }
        hydrate(target, target.dataset.mkProjectionUrl, { force: true }).catch(() => {});
      }
    }
  }

  function prefetchFrom(trigger) {
    const url = trigger.dataset.mkProjectionUrl;
    if (!url || trigger.dataset.mkPrefetch === 'false') return;
    clearTimeout(prefetchTimers.get(trigger));
    const timer = window.setTimeout(() => {
      load(url).catch(() => {});
      prefetchTimers.delete(trigger);
    }, 120);
    prefetchTimers.set(trigger, timer);
  }

  function cancelPrefetch(trigger) {
    clearTimeout(prefetchTimers.get(trigger));
    prefetchTimers.delete(trigger);
  }

  document.addEventListener('pointerover', (event) => {
    const trigger = event.target.closest('[data-mk-projection-url][data-mk-prefetch]');
    if (trigger) prefetchFrom(trigger);
  });
  document.addEventListener('pointerout', (event) => {
    const trigger = event.target.closest('[data-mk-projection-url][data-mk-prefetch]');
    if (trigger) cancelPrefetch(trigger);
  });
  document.addEventListener('focusin', (event) => {
    const trigger = event.target.closest('[data-mk-projection-url][data-mk-prefetch]');
    if (trigger) prefetchFrom(trigger);
  });
  document.addEventListener('focusout', (event) => {
    const trigger = event.target.closest('[data-mk-projection-url][data-mk-prefetch]');
    if (trigger) cancelPrefetch(trigger);
  });

  document.addEventListener('htmx:beforeCleanupElement', (event) => {
    const root = event.detail.elt;
    const targets = root.matches?.('[data-mk-projection-target]')
      ? [root]
      : [...root.querySelectorAll?.('[data-mk-projection-target]') || []];
    for (const target of targets) targetControllers.get(target)?.abort();
  });

  document.addEventListener('htmx:afterSwap', () => {
    const nextScope = currentScope();
    if (nextScope !== observedScope) {
      cache.clear();
      inFlight.clear();
      subscriptions.clear();
      observedScope = nextScope;
    }
  });

  document.addEventListener('htmx:historyRestore', () => {
    window.lucide?.createIcons?.();
    publish('makolo:workspace-restored', { scope: currentScope(), url: window.location.href });
  });

  document.addEventListener('htmx:afterRequest', (event) => {
    const detail = event.detail || {};
    const verb = detail.requestConfig?.verb?.toUpperCase();
    if (!verb || verb === 'GET' || !detail.successful) return;
    const owner = detail.elt?.closest?.('[data-mk-invalidate]');
    if (!owner) return;
    const urls = owner.dataset.mkInvalidate.split(',').map((value) => value.trim()).filter(Boolean);
    invalidate(urls);
  });

  window.MakoloWorkspaceRuntime = Object.freeze({
    hydrate,
    invalidate,
    load,
    prefetch: load,
    scope: currentScope,
  });
})();
