import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const EVENTS_SPACE = 'makolo-e2e-events';


test('visitor can understand a public possibility before authentication and auth starts only on action @firefox', async ({ page }) => {
  await page.goto('/discover/?q=Festival+Makolo+E2E');

  const card = page.locator('article').filter({ hasText: 'Festival Makolo E2E' }).first();
  await expect(card).toBeVisible();
  await expect(page).not.toHaveURL(/\/me\//);
  await expect(page.getByText('Discovery Private E2E')).toHaveCount(0);

  await card.getByRole('link').filter({ hasText: 'Festival Makolo E2E' }).first().click();
  await expect(page).toHaveURL(/\/events\/festival-makolo-e2e\/$/);
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E', exact: true })).toBeVisible();

  await page.getByRole('link', { name: /Acheter le billet|Obtenir des billets/i }).click();
  await expect(page).toHaveURL(/\/login\/\?next=.*festival-makolo-e2e/i);
  await expect(page).not.toHaveURL(/\/me\//);
});


test('Home distinguishes immediate action from a genuinely calm state', async ({ page }) => {
  await login(page, 'invitee.participant@e2e.makolo.test');
  await page.goto('/me/');
  await expect(page.getByRole('heading', { name: 'Qu’est-ce qui compte maintenant ?' })).toBeVisible();
  await expect(page.getByText('Invitation communautaire E2E').first()).toBeVisible();
  await expect(page.getByText('Tout est en ordre. ✓')).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/me/');
  await expect(page.getByRole('heading', { name: 'Tout est en ordre. ✓' })).toBeVisible();
  await expect(page.getByText('Aucune action, décision ou information importante ne réclame votre attention maintenant.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ce qui demande quelque chose de moi' })).toHaveCount(0);
});


test('Space membership does not grant access-control authority on the server', async ({ page }) => {
  await login(page, 'finance@e2e.makolo.test');
  let response = await page.goto(`/spaces/${EVENTS_SPACE}/control/`);
  expect(response.status()).toBe(403);
  await expect(page.getByText(/Erreur 403/i)).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'owner@e2e.makolo.test');
  response = await page.goto(`/spaces/${EVENTS_SPACE}/control/`);
  expect(response.status()).toBe(200);
  await expect(page.getByRole('heading', { name: /Contrôle d’accès|Contrôle des accès/i }).first()).toBeVisible();
});


test('login required validation keeps a coherent keyboard focus path', async ({ page }) => {
  await page.goto('/login/');
  const email = page.getByLabel('Adresse e-mail');
  const password = page.getByLabel('Mot de passe', { exact: true });
  const forgot = page.getByRole('link', { name: 'Mot de passe oublié ?' });
  const submit = page.getByRole('button', { name: 'Se connecter' });

  await expect(email).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(forgot).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(password).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(submit).toBeFocused();

  await page.keyboard.press('Enter');
  await expect(email).toBeFocused();
});
