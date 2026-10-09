import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';
import { expectNoSeriousAxeViolations } from '../helpers/accessibility.mjs';

const viewports = [
  { label: 'Compact', width: 390, height: 844 },
  { label: 'Medium', width: 900, height: 750 },
  { label: 'Wide', width: 1366, height: 850 },
  { label: 'Very Wide', width: 1920, height: 1080 },
];

test('Platform is private, permission-first, and not Django Admin', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  const denied = await page.goto('/platform/');
  expect(denied.status()).toBe(403);
  await expect(page.getByText(/Traceback|PermissionDenied/)).toHaveCount(0);
  const deepLink = await page.goto('/platform/system/');
  expect(deepLink.status()).toBe(403);

  await page.context().clearCookies();
  await login(page, 'staff@e2e.makolo.test');
  const response = await page.goto('/platform/');
  expect(response.status()).toBe(200);
  expect(response.headers()['cache-control']).toContain('no-store');
  await expect(page.getByRole('link', { name: /Makolo Platform/ }).first()).toBeVisible();
  await expect(page.getByText('Contexte : Platform')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Navigation Platform' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Investiguer' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Système' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Vue d’ensemble' })).toBeVisible();
  await expect(page.getByText(/Django Admin|Coming soon|TODO/)).toHaveCount(0);
});

for (const viewport of viewports) {
  test(`Platform fits ${viewport.label} and stays keyboard-accessible`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await login(page, 'staff@e2e.makolo.test');
    const response = await page.goto('/platform/');
    expect(response.status()).toBe(200);
    await expect(page.getByRole('heading', { name: 'Vue d’ensemble' })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(2);
    await expectNoSeriousAxeViolations(page);

    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Aller au contenu principal' })).toBeFocused();
    await page.getByRole('link', { name: 'Investiguer' }).click();
    await expect(page.getByRole('heading', { name: 'Investiguer' })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: /Titre ou référence/ })).toBeVisible();
  });
}

test('Platform shows empty search honestly and blocks anonymous deep links', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/platform/investigate/');
  await page.getByRole('searchbox', { name: /Titre ou référence/ }).fill('platform-absent-reference-9999');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByText(/Aucune correspondance/).first()).toBeVisible();
  await expect(page.getByText(/owner-fédérée partielle/)).toBeVisible();

  await page.context().clearCookies();
  const response = await page.goto('/platform/investigate/?q=private-id');
  expect([301, 302]).toContain(response.status());
  expect(response.headers().location).toMatch(/login/);
});
