import { test as base, expect } from '@playwright/test';

const EXPECTED_DOCUMENT_STATUS_CONSOLE = /^Failed to load resource: the server responded with a status of (403 \(Forbidden\)|404 \(Not Found\))$/;

export const test = base.extend({
  page: async ({ page }, use) => {
    const browserErrors = [];

    await page.addInitScript(() => {
      window.__makoloCspViolations = [];
      document.addEventListener('securitypolicyviolation', event => {
        window.__makoloCspViolations.push({
          blockedURI: event.blockedURI,
          directive: event.effectiveDirective,
          disposition: event.disposition,
        });
      });
    });

    page.on('pageerror', error => browserErrors.push(`pageerror: ${error.message}`));
    page.on('console', message => {
      if (message.type() !== 'error') return;
      const text = message.text();
      // Chromium logs top-level 403/404 document responses as console errors even
      // though no JavaScript failed. Static 404s are still blocked below, and the
      // link crawler asserts internal GET targets separately.
      if (EXPECTED_DOCUMENT_STATUS_CONSOLE.test(text)) return;
      browserErrors.push(`console.error: ${text}`);
    });
    page.on('response', response => {
      const url = response.url();
      if (response.status() >= 500) browserErrors.push(`HTTP ${response.status()}: ${url}`);
      if (response.status() === 404 && /\/static\//.test(url)) {
        browserErrors.push(`missing static asset: ${url}`);
      }
    });
    page.on('requestfailed', request => {
      if (/\/static\//.test(request.url())) {
        browserErrors.push(`failed static request: ${request.url()} ${request.failure()?.errorText || ''}`);
      }
    });

    await use(page);

    const cspViolations = await page.evaluate(() => window.__makoloCspViolations || []).catch(() => []);
    expect(browserErrors, browserErrors.join('\n')).toEqual([]);
    expect(cspViolations, JSON.stringify(cspViolations, null, 2)).toEqual([]);
  },
});

export { expect } from '@playwright/test';
