import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


async function expectForbidden(page, path) {
  const response = await page.goto(path);
  expect(response.status()).toBe(403);
  await expect(page.getByText(/Erreur 403/i)).toBeVisible();
}


test('participant sees personal navigation and server denies event management', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Accueil', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mes démarches', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mes accès', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Notifications', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Profil', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Activités', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Operations Center' })).toHaveCount(0);
  await expectForbidden(page, '/events/new/');
});


test('activity manager sees canonical activity and access tools but not Contacts', async ({ page }) => {
  await login(page, 'event.manager@e2e.makolo.test');
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/overview\/$/);
  await expect(page.getByRole('link', { name: 'Activités', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contrôle d’accès', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Audiences', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);

  let response = await page.goto('/events/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /Créer|Nouvel événement/i })).toBeVisible();

  response = await page.goto('/tickets/manage/types/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByLabel('Événement').getByRole('option', { name: 'Festival Makolo E2E' })).toHaveCount(1);
});


test('finance sees payments and analyses without activity creation or Contacts', async ({ page }) => {
  await login(page, 'finance@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Analyses', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Audiences', exact: true })).toHaveCount(0);
  const response = await page.goto('/payments/');
  expect(response.status()).toBe(200);
  await expectForbidden(page, '/events/new/');
});


test('marketing sees Contacts, audiences and promotions while event creation remains forbidden', async ({ page }) => {
  await login(page, 'marketing@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Contacts', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Audiences', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Promotions', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Analyses', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);
  await expectForbidden(page, '/events/new/');
});


test('assigned scanner agent can access only its activity without organizer privileges', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  const response = await page.goto('/scanner/event/festival-makolo-e2e/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  const isolated = await page.goto('/scanner/event/atelier-makolo-visuel/');
  expect(isolated.status()).toBe(404);
  await expectForbidden(page, '/events/new/');
});


test('staff lands in Operations and a non-staff user is denied directly', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await expect(page).toHaveURL('/operations/');
  await expect(page.getByRole('heading', { name: 'Makolo Operations Center', exact: true })).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'participant@e2e.makolo.test');
  await expectForbidden(page, '/operations/');
});


test('multi-role user keeps authority contextual to the selected Space', async ({ page }) => {
  await login(page, 'multi.role@e2e.makolo.test');
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/overview\/$/);
  await expect(page.getByRole('heading', { name: 'Makolo E2E Events', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Activités', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);

  await page.goto('/spaces/makolo-e2e-finance/overview/');
  await expect(page.getByRole('heading', { name: 'Makolo E2E Finance', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
});
