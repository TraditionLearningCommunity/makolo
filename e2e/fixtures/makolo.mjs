import { readFileSync } from 'node:fs';
import { test as base, expect } from '@playwright/test';

const EXPECTED_DOCUMENT_STATUS_CONSOLE = /^Failed to load resource: the server responded with a status of (403 \(Forbidden\)|404 \(Not Found\))$/;
const TILE_PNG = readFileSync(new URL('../../static/brand/apple-touch-icon.png', import.meta.url));

export const test = base.extend({
  page: async ({ page }, use) => {
    const browserErrors = [];

    await page.route('https://tile.openstreetmap.org/**', route => route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: TILE_PNG,
    }));

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
      if (!/\/static\//.test(request.url())) return;
      const errorText = request.failure()?.errorText || '';
      if (/NS_BINDING_ABORTED|net::ERR_ABORTED/.test(errorText)) return;
      browserErrors.push(`failed static request: ${request.url()} ${errorText}`);
    });

    await use(page);

    const cspViolations = await page.evaluate(() => window.__makoloCspViolations || []).catch(() => []);
    expect(browserErrors, browserErrors.join('\n')).toEqual([]);
    expect(cspViolations, JSON.stringify(cspViolations, null, 2)).toEqual([]);
  },
});

export { expect } from '@playwright/test';
