import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';


test('authorized manager grants and revokes a canonical Access without payment', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/access/');
  await page.getByRole('link', { name: 'Accorder un accès' }).click();
  await expect(page.getByRole('heading', { name: 'Accorder un accès', exact: true })).toBeVisible();

  await page.getByLabel('Adresse e-mail du bénéficiaire').fill('empty.participant@e2e.makolo.test');
  await page.getByLabel('Activité').selectOption({ label: 'Festival Makolo E2E' });
  const occurrenceSelect = page.getByLabel('Session / date');
  const occurrenceOption = occurrenceSelect.locator('option').filter({ hasText: 'Festival Makolo E2E' }).first();
  await occurrenceSelect.selectOption(await occurrenceOption.getAttribute('value'));
  await page.getByLabel('Motif interne').fill('Invité E2E');
  await page.getByRole('button', { name: /Accorder l’accès/i }).click();
  await expect(page.getByText(/Accès accordé/i)).toBeVisible();
  await expect(page.getByText('empty.participant@e2e.makolo.test')).toBeVisible();

  await logout(page);
  await login(page, 'empty.participant@e2e.makolo.test');

  await page.goto('/notifications/');
  await expect(page.getByRole('heading', { name: 'Billet disponible', exact: true })).toHaveCount(1);

  await page.goto('/me/accesses/');
  const accessLink = page.getByRole('link').filter({ hasText: 'Festival Makolo E2E' }).first();
  await expect(accessLink).toBeVisible();
  await accessLink.click();
  await expect(page.getByText(/Autorisé par/i)).toBeVisible();
  await expect(page.getByText('Valide', { exact: true }).first()).toBeVisible();
  const accessUrl = page.url();

  await page.goto('/discover/?q=Festival+Makolo+E2E');
  const discoveryCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(discoveryCard).toContainText('Vous avez accès');
  await expect(discoveryCard.getByRole('link', { name: /Acheter le billet/i })).toHaveCount(0);
  await expect(discoveryCard.getByRole('link', { name: /Voir mon billet|Voir mon accès/i })).toBeVisible();

  await page.goto('/events/festival-makolo-e2e/');
  await expect(page.getByText('Vous avez accès')).toBeVisible();
  await expect(page.getByRole('link', { name: /Acheter le billet/i })).toHaveCount(0);
  await page.getByRole('link', { name: /Voir mon billet|Voir mon accès/i }).click();
  await expect(page).toHaveURL(accessUrl);

  await logout(page);
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/access/?q=empty.participant%40e2e.makolo.test');
  const accessRow = page.locator('article').filter({ hasText: 'empty.participant@e2e.makolo.test' }).first();
  await expect(accessRow).toContainText('Festival Makolo E2E');
  await accessRow.getByRole('button', { name: 'Révoquer' }).click();
  await expect(page.getByText(/Accès révoqué/i)).toBeVisible();

  await logout(page);
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/discover/?q=Festival+Makolo+E2E');
  const revokedCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(revokedCard).toContainText('Accès révoqué');
  await expect(revokedCard.getByRole('link', { name: /Acheter le billet/i })).toHaveCount(0);
});
