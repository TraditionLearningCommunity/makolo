import { test, expect } from '@playwright/test';
import { E2E_PASSWORD, login, logout } from '../helpers/auth.mjs';

const PARTICIPANT = 'participant@e2e.makolo.test';
const RESERVATION = 'reservation.participant@e2e.makolo.test';
const MANAGER = 'event.manager@e2e.makolo.test';
const SCANNER = 'scanner@e2e.makolo.test';

async function searchTransport(page, date = '2031-06-15') {
  await page.goto('/transport/');
  await page.locator('select[name="origin"]').selectOption({ label: /Lubumbashi/ });
  await page.locator('select[name="destination"]').selectOption({ label: /Kolwezi/ });
  await page.locator('input[name="date"]').fill(date);
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByRole('heading', { name: /Lubumbashi.*Kolwezi/ })).toBeVisible();
}

test('Transport upfront: search, auth continuation, payment, ticket QR and boarding', async ({ page }, testInfo) => {
  await searchTransport(page);
  await expect(page.getByText('15.00 USD')).toBeVisible();
  await page.locator('a').filter({ hasText: '08:00' }).first().click();
  const promo = page.locator('div').filter({ hasText: 'Promo web E2E' }).filter({ hasText: '15.00 USD' }).last();
  await promo.getByRole('link', { name: 'Acheter le billet' }).click();

  await expect(page).toHaveURL(/\/login\/?next=.*\/transport\/departures\//);
  await page.getByLabel('Adresse e-mail').fill(PARTICIPANT);
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page.getByText('Votre voyage')).toBeVisible();
  await expect(page.getByText('Promo web E2E')).toBeVisible();

  await page.getByRole('button', { name: 'Continuer vers le paiement' }).click();
  await expect(page.getByRole('heading', { name: /PAY-/ })).toBeVisible();
  await page.getByRole('button', { name: 'Simuler un paiement réussi' }).click();
  await expect(page.getByText('Réussi')).toBeVisible();
  await page.getByRole('link', { name: 'Voir mon billet / mes accès' }).click();
  await expect(page.getByText('Lubumbashi → Kolwezi E2E')).toBeVisible();
  await page.getByRole('link', { name: /Voir mon billet|Lubumbashi → Kolwezi E2E/ }).first().click();
  await expect(page.getByText('Billet')).toBeVisible();
  const qr = page.getByRole('img', { name: /QR de votre billet/i });
  await expect(qr).toBeVisible();
  const qrPath = testInfo.outputPath('transport-ticket.png');
  await qr.screenshot({ path: qrPath });

  await logout(page);
  await login(page, SCANNER);
  await page.goto('/spaces/mulykap-transport-e2e/control/');
  await page.getByRole('link', { name: /Lubumbashi → Kolwezi E2E/ }).click();
  await page.locator('#qr-image').setInputFiles(qrPath);
  await expect(page.locator('#result-title')).toHaveText('Accès autorisé');
  await page.waitForTimeout(4100);
  await page.locator('#qr-image').setInputFiles([]);
  await page.locator('#qr-image').setInputFiles(qrPath);
  await expect(page.locator('#result-title')).toHaveText('Accès refusé');
  await expect(page.locator('#result-message')).toContainText(/déjà utilisé/i);
});

test('Transport on-site confirms without online payment surface', async ({ page }) => {
  await login(page, RESERVATION);
  await searchTransport(page);
  await page.locator('a').filter({ hasText: '14:00' }).first().click();
  await expect(page.getByText('À payer sur place')).toBeVisible();
  await page.getByRole('link', { name: 'Réserver' }).click();
  await page.getByRole('button', { name: 'Confirmer la réservation' }).click();
  await expect(page.getByText('Billet')).toBeVisible();
  await expect(page).not.toHaveURL(/\/payments\//);
});

test('Transport manager can create and publish a departure from Space Console', async ({ page }) => {
  await login(page, MANAGER);
  await page.goto('/spaces/mulykap-transport-e2e/transport/');
  await expect(page.getByRole('heading', { name: 'Routes, Départs et Véhicules' })).toBeVisible();
  await expect(page.getByText('Autocar E2E 52')).toBeVisible();

  const vehicleForm = page.locator('form[action$="/transport/vehicles/new/"]');
  await vehicleForm.locator('input[name="label"]').fill('Minibus Manager E2E');
  await vehicleForm.locator('input[name="passenger_capacity"]').fill('12');
  await vehicleForm.getByRole('button', { name: 'Ajouter' }).click();
  await expect(page.getByText('Minibus Manager E2E')).toBeVisible();

  const departureForm = page.locator('form[action$="/transport/departures/new/"]');
  await departureForm.locator('select[name="route"]').selectOption({ label: /Lubumbashi → Kolwezi E2E/ });
  await departureForm.locator('input[name="title"]').fill('Trajet Manager E2E');
  await departureForm.locator('input[name="start_at"]').fill('2031-06-20T09:00');
  await departureForm.locator('input[name="end_at"]').fill('2031-06-20T13:00');
  await departureForm.locator('select[name="vehicle"]').selectOption({ label: /Minibus Manager E2E/ });
  await departureForm.locator('input[name="capacity"]').fill('12');
  await departureForm.locator('input[name="fare_name"]').fill('Standard Manager E2E');
  await departureForm.locator('input[name="unit_price"]').fill('18');
  await departureForm.locator('select[name="payment_mode"]').selectOption('on_site');
  await departureForm.getByRole('button', { name: 'Créer et publier' }).click();
  await expect(page.getByText('20/06/2031 09:00')).toBeVisible();

  await searchTransport(page, '2031-06-20');
  await expect(page.getByText('09:00')).toBeVisible();
  await expect(page.getByText('18.00 USD')).toBeVisible();
});

test('Transport traveler flow remains usable on mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await searchTransport(page);
  await expect(page.getByText('Mulykap Transport E2E')).toBeVisible();
  await page.locator('a').filter({ hasText: '08:00' }).first().click();
  await expect(page.getByRole('heading', { name: /Lubumbashi.*Kolwezi/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Acheter le billet' }).first()).toBeVisible();
});
