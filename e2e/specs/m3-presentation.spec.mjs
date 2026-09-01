import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


test('M3 organizer opens Presentation Studio, previews real data and publishes a template', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/activities/');
  await page.getByRole('link').filter({ hasText: 'Réservation sur place E2E' }).first().click();
  await page.getByRole('link', { name: 'Ouvrir Présentation', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Réservation sur place E2E', exact: true })).toBeVisible();
  await expect(page.getByText('Makolo Essential', { exact: true })).toBeVisible();
  await expect(page.getByText('Formal', { exact: true })).toBeVisible();
  await page.getByText('Formal', { exact: true }).click();
  await page.locator('select[name="theme"]').selectOption('ivory');
  await page.locator('textarea[name="intro"]').fill('Présentation M3 E2E');
  await page.getByRole('button', { name: 'Enregistrer', exact: true }).click();
  await expect(page.getByText('Présentation enregistrée en brouillon.', { exact: true })).toBeVisible();

  const preview = page.getByRole('link', { name: 'Téléphone', exact: true });
  const [previewPage] = await Promise.all([page.context().waitForEvent('page'), preview.click()]);
  await expect(previewPage.getByRole('heading', { name: 'Réservation sur place E2E', exact: true })).toBeVisible();
  await expect(previewPage.getByText('Présentation M3 E2E', { exact: true })).toBeVisible();
  await previewPage.close();

  await page.getByRole('button', { name: 'Utiliser ce modèle', exact: true }).click();
  await expect(page.getByText('Présentation publiée.', { exact: true })).toBeVisible();
});


test('M3 participant can open the MPS Access representation and print preview', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/accesses/');
  const access = page.getByRole('link').filter({ hasText: 'Inscription communautaire E2E' }).first();
  await access.click();
  await page.getByRole('link', { name: 'Voir la Présentation', exact: true }).click();
  await expect(page.locator('.mps-qr')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('mk1.');
});
