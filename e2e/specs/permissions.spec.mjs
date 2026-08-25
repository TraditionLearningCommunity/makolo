import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


async function expectForbidden(page, path) {
  const response = await page.goto(path);
  expect(response.status()).toBe(403);
  await expect(page.getByText(/Erreur 403/i)).toBeVisible();
}


async function expectPersonalEventCreation(page) {
  const response = await page.goto('/events/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /Créer|Nouvel événement/i })).toBeVisible();
}


async function selectSpace(page, name, slug) {
  await page.goto('/spaces/');
  await expect(page).toHaveURL(/\/spaces\/$/);
  await page.getByRole('link', { name: new RegExp(name) }).click();
  await expect(page).toHaveURL(new RegExp(`/spaces/${slug}/overview/$`));
}


test('participant sees personal navigation and can enter personal Event creation', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Accueil', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mes démarches', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mes accès', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Notifications', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Menu utilisateur' }).click();
  await expect(page.getByRole('menuitem', { name: 'Mon profil et réglages' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Activités', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Operations Center' })).toHaveCount(0);
  await expectPersonalEventCreation(page);
});


test('activity manager sees canonical activity and access tools', async ({ page }) => {
  await login(page, 'event.manager@e2e.makolo.test');
  await selectSpace(page, 'Makolo E2E Events', 'makolo-e2e-events');
  await expect(page.getByRole('link', { name: 'Activités', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contrôle d’accès', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Audiences', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);

  await expectPersonalEventCreation(page);

  const response = await page.goto('/tickets/manage/types/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByLabel('Événement').getByRole('option', { name: 'Festival Makolo E2E' })).toHaveCount(1);
});


test('finance sees payments and analyses without Space activity management', async ({ page }) => {
  await login(page, 'finance@e2e.makolo.test');
  await selectSpace(page, 'Makolo E2E Events', 'makolo-e2e-events');
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Analyses', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Audiences', exact: true })).toHaveCount(0);
  const response = await page.goto('/payments/');
  expect(response.status()).toBe(200);
  await expectPersonalEventCreation(page);
});


test('marketing sees Contacts, audiences and promotions while keeping personal Event creation', async ({ page }) => {
  await login(page, 'marketing@e2e.makolo.test');
  await selectSpace(page, 'Makolo E2E Events', 'makolo-e2e-events');
  await expect(page.getByRole('link', { name: 'Contacts', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Audiences', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Promotions', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Analyses', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);
  await expectPersonalEventCreation(page);
});


test('assigned scanner agent can access only its assigned activity without Space organizer privileges', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  const response = await page.goto('/scanner/event/festival-makolo-e2e/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  const isolated = await page.goto('/scanner/event/atelier-makolo-visuel/');
  expect(isolated.status()).toBe(404);
  await expectPersonalEventCreation(page);
});


test('staff keeps the personal landing and can enter Operations while a non-staff user is denied', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await expect(page).toHaveURL('/me/');
  let response = await page.goto('/operations/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Makolo Operations Center', exact: true })).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'participant@e2e.makolo.test');
  await expectForbidden(page, '/operations/');
});


test('multi-role user keeps authority contextual to the selected Space', async ({ page }) => {
  await login(page, 'multi.role@e2e.makolo.test');
  await selectSpace(page, 'Makolo E2E Events', 'makolo-e2e-events');
  await expect(page.getByRole('heading', { name: 'Makolo E2E Events', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Activités', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);

  await page.goto('/spaces/makolo-e2e-finance/overview/');
  await expect(page.getByRole('heading', { name: 'Makolo E2E Finance', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
});
