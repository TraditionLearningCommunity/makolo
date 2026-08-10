import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


const EXCLUDED = [
  /^\/admin\//,
  /^\/api\//,
  /^\/logout\/?$/,
  /^\/static\//,
  /^\/media\//,
];

function isSafeInternalHref(href) {
  if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return false;
  const url = new URL(href, 'http://127.0.0.1:8000');
  if (url.origin !== 'http://127.0.0.1:8000') return false;
  return !EXCLUDED.some(pattern => pattern.test(url.pathname));
}

async function collectLinks(page, path) {
  await page.goto(path);
  return page.locator('a[href]').evaluateAll(nodes => nodes.map(node => node.getAttribute('href')));
}


test('owner navigation, dashboard, profile and organization links have no dead GET targets', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  const candidates = new Set();
  for (const path of ['/dashboard/', '/account/profile/', '/organizations/', '/discover/']) {
    for (const href of await collectLinks(page, path)) {
      if (isSafeInternalHref(href)) candidates.add(new URL(href, page.url()).toString());
    }
  }

  expect(candidates.size).toBeGreaterThan(10);
  for (const url of [...candidates].slice(0, 45)) {
    const response = await page.context().request.get(url, { maxRedirects: 5 });
    expect(response.status(), `${response.status()} for ${url}`).not.toBe(404);
    expect(response.status(), `${response.status()} for ${url}`).toBeLessThan(500);
  }
});
