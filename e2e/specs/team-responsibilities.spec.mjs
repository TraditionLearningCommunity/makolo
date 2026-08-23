import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';


test('owner manages Space and Activity responsibilities without conflating membership', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/team/');

  const financeMember = page.locator('article').filter({ hasText: 'finance@e2e.makolo.test' });
  await expect(financeMember).toBeVisible();
  await financeMember.getByRole('link', { name: 'Gérer les responsabilités' }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: /Responsabilités de/i })).toBeVisible();

  await page.getByLabel("Responsabilité dans l'Espace").selectOption('marketing');
  await page.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(page.getByText(/Responsabilité dans l'Espace mise à jour/i)).toBeVisible();

  await page.getByLabel('Activité').selectOption({ label: 'Festival Makolo E2E' });
  await page.getByLabel('Responsabilité', { exact: true }).selectOption('activity-manager');
  await page.getByRole('button', { name: 'Ajouter', exact: true }).click();
  await expect(page.getByText(/Responsabilité sur l'activité ajoutée/i)).toBeVisible();
  const activityResponsibility = page.locator('div').filter({ hasText: 'Festival Makolo E2E' }).filter({ hasText: "Responsable de l’activité" }).first();
  await expect(activityResponsibility).toBeVisible();

  await logout(page);
  await login(page, 'finance@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/access/grant/');
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Accorder un accès', exact: true })).toBeVisible();
  await expect(page.getByLabel('Activité').locator('option', { hasText: 'Festival Makolo E2E' })).toHaveCount(1);

  await logout(page);
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/team/');
  await page.locator('article').filter({ hasText: 'finance@e2e.makolo.test' }).getByRole('link', { name: 'Gérer les responsabilités' }).click();
  const responsibilityRow = page.locator('div').filter({ hasText: 'Festival Makolo E2E' }).filter({ hasText: "Responsable de l’activité" }).first();
  page.once('dialog', dialog => dialog.accept());
  await responsibilityRow.getByRole('button', { name: 'Retirer cette responsabilité' }).click();
  await expect(page.getByText(/Responsabilité sur l'activité retirée/i)).toBeVisible();

  await page.getByLabel("Responsabilité dans l'Espace").selectOption('finance');
  await page.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(page.getByText(/Responsabilité dans l'Espace mise à jour/i)).toBeVisible();
});
