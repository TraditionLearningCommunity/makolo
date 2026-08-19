import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}


test('participant home and Access QR stay usable on mobile @mobile', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');
  await expect(page.getByRole('heading', { name: /Que dois-je faire maintenant/i })).toBeVisible();
  await expect(page.getByText('Inscription communautaire E2E').first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto('/me/accesses/');
  const access = page.getByRole('link').filter({ hasText: 'Inscription communautaire E2E' }).first();
  await expect(access).toBeVisible();
  await access.click();
  await expect(page.getByRole('img', { name: /QR de votre confirmation/i })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto('/account/profile/');
  await expect(page.getByRole('heading', { name: 'Mon profil' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Enregistrer mon profil/i })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});


test('scanner and Operations remain reachable at phone width @mobile', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await expect(page.getByText('Lire une image QR')).toBeVisible();
  await expect(page.getByLabel('Saisie manuelle du jeton QR')).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.context().clearCookies();
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/operations/');
  await expect(page.getByRole('heading', { name: 'Makolo Operations Center' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
