import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';


async function createPaidOrder(page) {
  await page.goto('/discover/');
  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await page.getByRole('link', { name: /Obtenir des billets/i }).click();
  await page.getByLabel('Quantité').fill('1');
  await page.getByRole('button', { name: /Créer la commande/i }).click();
  await expect(page.getByText('Pass standard E2E')).toBeVisible();
}


async function completeSandboxPayment(page) {
  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await page.locator('[name="provider"]').selectOption('sandbox');
  const method = page.locator('[name="method"]');
  if (await method.locator('option').count() > 1) await method.selectOption({ index: 1 });
  await page.getByRole('button', { name: /Initialiser le paiement/i }).click();
  await expect(page.getByText(/Sandbox/i)).toBeVisible();
  await page.getByRole('button', { name: /Simuler un paiement réussi/i }).click();
  await expect(page.getByText(/Paiement sandbox confirmé/i)).toBeVisible();
}


test('participant goes from discovery to favorite, payment, QR, accepted scan then duplicate refusal', async ({ page }, testInfo) => {
  await login(page, 'participant@e2e.makolo.test');
  await expect(page.getByText(/Espace participant/i)).toBeVisible();

  await page.goto('/discover/for-you/');
  await expect(page.getByRole('heading').filter({ hasText: /Pour vous|Sélection/i }).first()).toBeVisible();
  await page.goto('/discover/');
  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await page.getByRole('button', { name: /Enregistrer/i }).click();
  await expect(page.getByRole('button', { name: /Enregistré/i })).toBeVisible();
  await page.goto('/discover/bookmarks/');
  await expect(page.getByText('Festival Makolo E2E').first()).toBeVisible();

  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await page.getByRole('link', { name: /Obtenir des billets/i }).click();
  await page.getByLabel('Quantité').fill('1');
  await page.getByRole('button', { name: /Créer la commande/i }).click();
  await completeSandboxPayment(page);

  await page.getByRole('link', { name: /Commande MKO-/i }).click();
  const ticketLink = page.getByRole('link', { name: /Pass standard E2E/i }).first();
  await expect(ticketLink).toBeVisible();
  await ticketLink.click();
  const ticketUrl = page.url();
  await expect(page.getByText('Valide', { exact: true }).first()).toBeVisible();

  const qrPath = testInfo.outputPath('purchased-ticket-qr.png');
  await page.getByRole('img', { name: 'QR du ticket' }).screenshot({ path: qrPath });

  await logout(page);
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/');
  const eventCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(eventCard).toBeVisible();
  await eventCard.getByRole('link', { name: 'Scanner' }).click();
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  await expect(page.getByText(/Saisie manuelle du jeton QR/i)).toBeVisible();
  await page.locator('#qr-image').setInputFiles(qrPath);
  await expect(page.getByRole('heading', { name: 'Accès autorisé' })).toBeVisible();

  await page.reload();
  await page.locator('#qr-image').setInputFiles(qrPath);
  await expect(page.getByRole('heading', { name: 'Accès refusé' })).toBeVisible();
  await expect(page.getByText(/déjà utilisé/i)).toBeVisible();
  await page.getByRole('link', { name: 'Historique' }).click();
  const scanRows = page.locator('tbody tr');
  await expect(scanRows.filter({ hasText: 'Accès autorisé' })).toHaveCount(1);
  await expect(scanRows.filter({ hasText: 'Billet déjà utilisé' })).toHaveCount(1);
  await expect(scanRows.filter({ hasText: 'Festival Makolo E2E' })).toHaveCount(2);

  await logout(page);
  await login(page, 'participant@e2e.makolo.test');
  await page.goto(ticketUrl);
  await expect(page.getByText('Utilisé', { exact: true }).first()).toBeVisible();
  await page.goto('/discover/my-events/');
  await expect(page.getByText('Festival Makolo E2E').first()).toBeVisible();
});


test('sandbox payment can be cancelled and retried without losing the order', async ({ page }) => {
  await login(page, 'profile.user@e2e.makolo.test');
  await createPaidOrder(page);
  const orderUrl = page.url();

  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await page.locator('[name="provider"]').selectOption('sandbox');
  const method = page.locator('[name="method"]');
  if (await method.locator('option').count() > 1) await method.selectOption({ index: 1 });
  await page.getByRole('button', { name: /Initialiser le paiement/i }).click();
  await page.getByRole('button', { name: /Annuler cette tentative/i }).click();
  await expect(page.getByText(/Paiement annulé/i)).toBeVisible();

  await page.goto(orderUrl);
  await expect(page.getByRole('link', { name: /Payer maintenant/i })).toBeVisible();
  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await page.locator('[name="provider"]').selectOption('sandbox');
  const retryMethod = page.locator('[name="method"]');
  if (await retryMethod.locator('option').count() > 1) await retryMethod.selectOption({ index: 1 });
  await page.getByRole('button', { name: /Initialiser le paiement/i }).click();
  await expect(page.getByRole('button', { name: /Simuler un paiement réussi/i })).toBeVisible();
});
