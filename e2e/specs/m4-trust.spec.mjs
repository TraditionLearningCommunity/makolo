import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';


test('M4 verification, verified-experience feedback and Proof remain contextual', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/trust/spaces/makolo-e2e-events/verification/request/');
  await page.locator('[name="claim_type"]').selectOption('organization_identity');
  await page.getByRole('button', { name: 'Envoyer la demande', exact: true }).click();
  await expect(page.getByText('Demande de vérification enregistrée.', { exact: true })).toBeVisible();
  await logout(page);

  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/trust/staff/');
  const verification = page.locator('article').filter({ hasText: 'Identité de l’Espace' }).first();
  await verification.locator('[name="action"]').selectOption('verify');
  await verification.locator('[name="reason_code"]').fill('e2e-reviewed');
  await verification.getByRole('button', { name: 'Appliquer', exact: true }).click();
  await expect(page.getByText('Vérification mise à jour.', { exact: true })).toBeVisible();
  await logout(page);

  await page.goto('/trust/spaces/makolo-e2e-events/');
  await expect(page.getByText('Identité de l’Espace', { exact: true })).toBeVisible();
  await expect(page.getByText(/Vérifiée/).first()).toBeVisible();

  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/history/');
  await page.getByRole('link').filter({ hasText: 'Trust expérience E2E' }).first().click();
  await expect(page.getByRole('link', { name: 'Donner mon retour', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Voir mon attestation', exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Donner mon retour', exact: true }).click();
  await page.locator('[name="delivery"]').selectOption('yes');
  await page.locator('[name="overall_sentiment"]').selectOption('positive');
  await page.locator('[name="comment"]').fill('Expérience Trust E2E vérifiée.');
  await page.getByRole('button', { name: 'Envoyer mon retour', exact: true }).click();
  await expect(page.getByText('Votre retour d’expérience vérifiée a été enregistré.', { exact: true })).toBeVisible();

  await page.goto('/me/history/');
  await page.getByRole('link').filter({ hasText: 'Trust expérience E2E' }).first().click();
  await page.getByRole('link', { name: 'Voir mon attestation', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Vérification', exact: true })).toBeVisible();
  await expect(page.getByText('Journey accomplie', { exact: true })).toBeVisible();

  await page.goto('/trust/spaces/makolo-e2e-events/');
  await expect(page.getByText(/1 expériences sur 365 jours/)).toBeVisible();
});
