import { test, expect } from '../fixtures/makolo.mjs';
import { E2E_PASSWORD, login, logout } from '../helpers/auth.mjs';


async function createPaidOrder(page) {
  await page.goto('/discover/');
  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await page.getByRole('link', { name: /Acheter le billet|Obtenir des billets/i }).click();
  await page.getByLabel('Quantité').fill('1');
  await page.getByRole('button', { name: /Créer la commande/i }).click();
  await expect(page.getByText('Pass standard E2E')).toBeVisible();
}


async function submitSandboxPayment(page) {
  const provider = page.locator('[name="provider"]');
  await expect(provider).toHaveValue('sandbox');
  const method = page.locator('[name="method"]');
  if (await method.locator('option').count() > 1) await method.selectOption({ index: 1 });
  await page.getByRole('button', { name: /^Payer\b/i }).click();
}


async function completeSandboxPayment(page) {
  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await submitSandboxPayment(page);
  await expect(page.getByText(/Sandbox/i)).toBeVisible();
  await page.getByRole('button', { name: /Simuler un paiement réussi/i }).click();
  await expect(page.getByText(/Paiement sandbox confirmé/i)).toBeVisible();
}


test('participant experience works for a canonical non-Event registration', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await expect(page.getByRole('heading', { name: /Que dois-je faire maintenant/i })).toBeVisible();
  await expect(page.getByText('Inscription communautaire E2E').first()).toBeVisible();

  await page.goto('/me/journeys/');
  const journey = page.getByRole('link').filter({ hasText: 'Inscription communautaire E2E' }).first();
  await expect(journey).toContainText('Inscription');
  await journey.click();
  await expect(page.getByText('Maison des initiatives E2E')).toBeVisible();
  await expect(page.getByText(/Inscription confirmée/)).toBeVisible();

  await page.goto('/me/accesses/');
  const access = page.getByRole('link').filter({ hasText: 'Inscription communautaire E2E' }).first();
  await expect(access).toContainText('Confirmation');
  await access.click();
  await expect(page.getByRole('img', { name: /QR de votre confirmation/i })).toBeVisible();
});


test('visitor resumes paid Event after auth, then Discovery exposes canonical Access and scan history', async ({ page }, testInfo) => {
  await page.goto('/events/festival-makolo-e2e/');
  await page.getByRole('link', { name: /Acheter le billet|Obtenir des billets/i }).click();
  await expect(page).toHaveURL(/\/login\/\?next=.*festival-makolo-e2e/i);
  await page.getByLabel('Adresse e-mail').fill('participant@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL(/\/tickets\/buy\/festival-makolo-e2e\/$/);

  await page.getByLabel('Quantité').fill('1');
  await page.getByRole('button', { name: /Créer la commande/i }).click();
  await completeSandboxPayment(page);

  await page.goto('/discover/?q=Festival+Makolo+E2E');
  const discoveryCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(discoveryCard).toContainText('Vous avez accès');
  await expect(discoveryCard.getByRole('link', { name: /Acheter le billet/i })).toHaveCount(0);
  const discoveryAccess = discoveryCard.getByRole('link', { name: /Voir mon billet|Voir mon accès/i });
  await expect(discoveryAccess).toBeVisible();
  await discoveryAccess.click();
  await expect(page).toHaveURL(/\/me\/accesses\//);
  await expect(page.getByText('Valide', { exact: true }).first()).toBeVisible();
  const accessUrl = page.url();

  await page.goto('/notifications/');
  await expect(page.getByRole('heading', { name: 'Paiement confirmé', exact: true })).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'Billet disponible', exact: true })).toHaveCount(1);

  await page.goto('/me/journeys/');
  const paidJourneys = page.getByRole('link').filter({ hasText: 'Festival Makolo E2E' });
  await expect(paidJourneys).toHaveCount(1);
  await paidJourneys.first().click();
  await expect(page.getByText('Terminée', { exact: true }).first()).toBeVisible();

  await page.goto(accessUrl);
  const qrPath = testInfo.outputPath('purchased-access-qr.png');
  await page.getByRole('img', { name: /QR de votre billet/i }).screenshot({ path: qrPath });

  await logout(page);
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/');
  const eventCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(eventCard).toBeVisible();
  await eventCard.getByRole('link', { name: 'Scanner' }).click();
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  await expect(page.getByLabel('Code du billet')).toBeVisible();
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
  await login(page, 'finance@e2e.makolo.test');
  await page.goto('/analytics/events/festival-makolo-e2e/');
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  await expect(page.getByText('1 scan(s) accepté(s)', { exact: true })).toBeVisible();
  const financeSection = page.locator('section').filter({
    has: page.getByRole('heading', { name: 'Revenus nets observés' }),
  });
  await expect(financeSection).toBeVisible();
  await expect(financeSection.getByText(/12[.,]00 USD/, { exact: true })).toBeVisible();

  await logout(page);
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/discover/?q=Festival+Makolo+E2E');
  const usedCard = page.locator('article').filter({ hasText: 'Festival Makolo E2E' });
  await expect(usedCard).toContainText('Accès utilisé');
  await expect(usedCard.getByRole('link', { name: /Acheter le billet/i })).toHaveCount(0);
  await usedCard.getByRole('link', { name: /Voir mon billet|Voir mon accès/i }).click();
  await expect(page).toHaveURL(accessUrl);
  await expect(page.getByText('Utilisé', { exact: true }).first()).toBeVisible();
});


test('sandbox payment can be cancelled and retried without losing the order', async ({ page }) => {
  await login(page, 'profile.user@e2e.makolo.test');
  await createPaidOrder(page);
  const orderUrl = page.url();

  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await submitSandboxPayment(page);
  await page.getByRole('button', { name: /Annuler cette tentative/i }).click();
  await expect(page.getByText(/Paiement annulé/i)).toBeVisible();

  await page.goto(orderUrl);
  await expect(page.getByRole('link', { name: /Payer maintenant/i })).toBeVisible();
  await page.getByRole('link', { name: /Payer maintenant/i }).click();
  await submitSandboxPayment(page);
  await expect(page.getByRole('button', { name: /Simuler un paiement réussi/i })).toBeVisible();
});


test('a free Event consumes its last canonical place and becomes sold out', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/events/capacite-makolo-e2e/');
  await page.getByRole('link', { name: /S’inscrire|Obtenir des billets/i }).click();
  const orderFormUrl = page.url();
  await expect(page.getByText(/1 restant\(s\)/i)).toBeVisible();
  await page.getByLabel('Quantité').fill('1');
  await page.getByRole('button', { name: /Créer la commande/i }).click();
  await expect(page.getByText('Place unique E2E').first()).toBeVisible();

  await page.goto(orderFormUrl);
  await expect(page.getByText(/0 restant\(s\)/i)).toBeVisible();
  await expect(page.getByText(/Complet pour le moment|Indisponible/i)).toBeVisible();
});
