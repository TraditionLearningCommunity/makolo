import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';
import { expectNoSeriousAxeViolations } from '../helpers/accessibility.mjs';

test('Platform is distinct, responsive, and exposes only authenticated operator routes', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');

  for (const width of [390, 820, 1280, 1680]) {
    await page.setViewportSize({ width, height: 900 });
    const response = await page.goto('/platform/');
    expect(response.status()).toBe(200);
    await expect(page.getByRole('link', { name: /Makolo Platform/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Vue d’ensemble/ })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Navigation Platform' })).toBeVisible();
    await expect(page.getByText('Opérateur authentifié')).toBeVisible();
    await expectNoSeriousAxeViolations(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
  }

  const operations = await page.goto('/platform/operations/');
  expect(operations.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Opérations' })).toBeVisible();
  const investigation = await page.goto('/platform/investigate/');
  expect(investigation.status()).toBe(200);
  await expect(page.getByRole('searchbox', { name: /Titre ou référence/ })).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'participant@e2e.makolo.test');
  for (const path of ['/platform/', '/platform/system/', '/platform/recognition/', '/platform/trust/']) {
    const response = await page.goto(path);
    expect(response.status()).toBe(403);
  }
});
