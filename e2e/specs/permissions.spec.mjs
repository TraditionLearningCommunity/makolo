import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function expectForbidden(page, path) {
  const response = await page.goto(path);
  expect(response.status()).toBe(403);
  await expect(page.getByRole('heading', { name: /Cet espace n’est pas accessible/i })).toBeVisible();
}


test('participant cannot access organizer-only creation routes', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await expectForbidden(page, '/events/new/');
  await expectForbidden(page, '/organizations/new/');
});


test('participant stays in personal scope and cannot enter a Space Console', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await expect(page).toHaveURL('/me/');
  await expect(page.getByRole('link', { name: 'Mes Espaces' })).toHaveCount(0);
  await expectForbidden(page, '/spaces/makolo-e2e-events/overview/');
});


test('space owner reaches the Space Console through a Mandate', async ({ page }) => {
  await login(page, 'organizer@e2e.makolo.test');
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/overview\/$/);
  await expect(page.getByRole('heading', { name: 'Makolo E2E Events', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Activités', exact: true }).first()).toBeVisible();
});


test('event manager is limited to assigned activities and cannot manage the Space', async ({ page }) => {
  await login(page, 'event.manager@e2e.makolo.test');
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/overview\/$/);
  await expect(page.getByText(/uniquement les activités qui vous sont attribuées/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Équipe', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toHaveCount(0);

  await page.getByRole('link', { name: 'Activités', exact: true }).first().click();
  await expect(page.getByText('Festival Makolo E2E').first()).toBeVisible();
  await expect(page.getByText('Atelier Makolo Visuel')).toHaveCount(0);
});


test('finance role sees commerce without inheriting scanner or CRM authority', async ({ page }) => {
  await login(page, 'finance@e2e.makolo.test');
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/overview\/$/);
  await expect(page.getByRole('link', { name: 'Commandes', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Contrôle d’accès', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Contacts', exact: true })).toHaveCount(0);
});


test('scanner role remains constrained to authorized activity contexts', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' })).toBeVisible();
  const isolated = await page.goto('/scanner/event/atelier-makolo-visuel/');
  expect(isolated.status()).toBe(404);
  await expectForbidden(page, '/events/new/');
});


test('staff lands in Operations and a non-staff user is denied directly', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await expect(page).toHaveURL('/operations/');
  await expect(page.getByRole('heading', { name: 'Opérations Makolo', exact: true })).toBeVisible();

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

  await page.goto('/spaces/makolo-e2e-transport/overview/');
  await expect(page.getByRole('heading', { name: 'Makolo E2E Transport', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Paiements', exact: true })).toBeVisible();
});
