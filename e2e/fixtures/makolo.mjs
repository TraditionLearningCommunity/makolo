import { test as base, expect } from '@playwright/test';

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
      if (message.type() === 'error') browserErrors.push(`console.error: ${message.text()}`);
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
