import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


async function expectForbidden(page, path) {
  const response = await page.goto(path);
  expect(response.status()).toBe(403);
  await expect(page.getByRole('heading', { name: /Cet espace n’est pas accessible/i })).toBeVisible();
}


test('participant sees personal navigation and server denies event management', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Favoris', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Événements', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Operations Center' })).toHaveCount(0);
  await expectForbidden(page, '/events/new/');
});


test('event manager sees event, access and audience tools but not finance', async ({ page }) => {
  await login(page, 'event.manager@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Événements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contrôle d’accès' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'CRM & audiences' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);
  let response = await page.goto('/events/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /Créer|Nouvel événement/i })).toBeVisible();

  response = await page.goto('/tickets/manage/types/new/');
  expect(response.status()).toBe(200);
  await expect(page.getByLabel('Événement').getByRole('option', { name: 'Festival Makolo E2E' })).toHaveCount(1);
});


test('finance sees finance and analytics surfaces without event creation rights', async ({ page }) => {
  await login(page, 'finance@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Analytics' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'CRM & audiences' })).toHaveCount(0);
  const response = await page.goto('/payments/');
  expect(response.status()).toBe(200);
  await expectForbidden(page, '/events/new/');
});


test('marketing sees CRM, Growth and Promotions while event creation remains forbidden', async ({ page }) => {
  await login(page, 'marketing@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'CRM & audiences' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Growth' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Promotions' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);
  await expectForbidden(page, '/events/new/');
});


test('assigned scanner agent can access its event without organizer privileges', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Contrôle d’accès' }).first()).toBeVisible();
  const response = await page.goto('/scanner/event/festival-makolo-e2e/');
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  await expectForbidden(page, '/events/new/');
});


test('staff sees Operations and a non-staff user is denied directly', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await expect(page.getByRole('link', { name: 'Operations Center' }).first()).toBeVisible();
  let response = await page.goto('/operations/');
  expect(response.status()).toBe(200);

  await page.context().clearCookies();
  await login(page, 'participant@e2e.makolo.test');
  await expectForbidden(page, '/operations/');
});


test('multi-role user gets deterministic organizer dashboard with unioned tools', async ({ page }) => {
  await login(page, 'multi.role@e2e.makolo.test');
  await expect(page.getByText(/Espace organisation/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Événements', exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true }).first()).toBeVisible();
  expect((await page.goto('/events/')).status()).toBe(200);
  expect((await page.goto('/payments/')).status()).toBe(200);
});
