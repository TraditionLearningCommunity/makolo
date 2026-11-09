import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SECONDARY = [
  '/me/journeys/',
  '/me/accesses/',
  '/me/history/',
  '/me/search/',
  '/discover/bookmarks/',
  '/discover/watches/',
  '/account/settings/',
  '/library/',
  '/library/documents/',
  '/trust/proofs/',
  '/trust/credentials/',
  '/conversations/',
  '/objectives/',
  '/objectives/projects/',
  '/objectives/organizer/',
  '/notifications/',
];

test('Group 2 secondary screens consume the same global interaction foundation', async ({ page }) => {
  test.setTimeout(150_000);
  await login(page, 'participant@e2e.makolo.test');
  for (const path of SECONDARY) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBeLessThan(500);
    await expect(page.locator('link[href*="makolo-interactions.css"]'), path).toHaveCount(1);
    await expect(page.locator('script[src*="makolo-interactions-f2.js"]'), path).toHaveCount(1);
  }
});

test('Mes ressources exposes the three personal resource families without mixing their lists', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/library/');
  await expect(page.getByRole('heading', { name: 'Mes ressources' })).toBeVisible();
  await expect(page.getByText('Mes documents', { exact: true })).toBeVisible();
  await expect(page.getByText('Mes preuves', { exact: true })).toBeVisible();
  await expect(page.getByText('Mes titres', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: /Mes documents/i })).toHaveAttribute(
    'href',
    /\/library\/documents\/$/,
  );
  await expect(page.getByRole('link', { name: /Mes preuves/i })).toHaveAttribute(
    'href',
    /\/trust\/proofs\/$/,
  );
  await expect(page.getByRole('link', { name: /Mes titres/i })).toHaveAttribute(
    'href',
    /\/trust\/credentials\/$/,
  );
  await expect(page.locator('#library-search')).toHaveCount(0);
});

test('Group 2 owner-backed search uses common fields without client-only ranking', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');

  await page.goto('/me/journeys/');
  await expect(page.locator('#journey-search')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#journey-status')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#journey-search').locator('xpath=ancestor::form[1]')).toHaveAttribute('method', 'get');

  await page.goto('/me/accesses/');
  await expect(page.locator('#access-search')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#access-search').locator('xpath=ancestor::form[1]')).toHaveAttribute('method', 'get');

  await page.goto('/library/documents/');
  await expect(page.locator('#library-search')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#library-search').locator('xpath=ancestor::form[1]')).toHaveAttribute('method', 'get');
  await expect(page.locator('[data-mk-query-local="true"]')).toHaveCount(0);

  await page.goto('/trust/proofs/');
  await expect(page.locator('#proof-search')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#proof-search').locator('xpath=ancestor::form[1]')).toHaveAttribute('method', 'get');

  await page.goto('/trust/credentials/');
  await expect(page.locator('#credential-search')).toHaveClass(/mk-interaction-field/);
  await expect(page.locator('#credential-search').locator('xpath=ancestor::form[1]')).toHaveAttribute('method', 'get');
});

test('Group 2 actions on Settings and organizer remain owner/CSRF backed', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/account/settings/');
  const appearance = page.locator('form#appearance');
  await expect(appearance).toHaveAttribute('method', 'post');
  await expect(appearance.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
  await expect(appearance.getByRole('button', { name: 'Appliquer l’apparence' })).toHaveClass(/mk-action-button/);

  await page.goto('/objectives/organizer/');
  await expect(page.locator('main[data-organizer]')).toBeVisible();
  await expect(page.getByRole('link', { name: /Créer un dossier/i })).toHaveClass(/mk-action-button/);
  await expect(page.getByRole('link', { name: /Créer un projet/i })).toHaveClass(/mk-action-button/);
  await expect(page.locator('[data-reverse]')).toHaveAttribute('aria-label', 'Inverser le tri');
});

test('Group 2 Dossier and Projet create forms preserve real native submission', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  for (const [path,action] of [
    ['/objectives/new/', /Créer le dossier/i],
    ['/objectives/projects/new/', /Créer le projet/i],
  ]) {
    await page.goto(path);
    const submit = page.getByRole('button', { name: action });
    await expect(submit).toHaveClass(/mk-action-button/);
    await expect(submit).toHaveAttribute('data-variant', 'primary');
    const form = submit.locator('xpath=ancestor::form[1]');
    await expect(form).toHaveAttribute('method', 'post');
    await expect(form.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
  }
});

test('Group 2 secondary controls remain usable in compact browser @mobile', async ({ page }) => {
  test.setTimeout(90_000);
  await login(page, 'participant@e2e.makolo.test');
  for (const [path,selector] of [
    ['/account/settings/', '#appearance button[type="submit"]'],
    ['/library/documents/', 'form[role="search"] button[type="submit"]'],
    ['/objectives/organizer/', '.mk-organizer__create .mk-action-button'],
  ]) {
    await page.goto(path);
    const action = page.locator(selector).first();
    await expect(action).toBeVisible();
    const height = await action.evaluate((node) => node.getBoundingClientRect().height);
    expect(height, path).toBeGreaterThanOrEqual(44);
  }
});


test('Group 2 Connections uses external layout CSS and shared owner-backed actions', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/connections/');
  await expect(page.locator('head link[href*="personal-connections-layout.css"]')).toHaveCount(1);
  await expect(page.locator('[data-mk-surface="connections"]')).toBeVisible();
  await expect(page.locator('[data-mk-surface="connections"] style')).toHaveCount(0);
  await expect(page.locator('.mk-cx-tabs.mk-interaction-tabs')).toHaveCount(1);
  await expect(page.locator('[data-mk-surface="connections"] [data-mk-query-local="true"]')).toHaveCount(0);
});

test('Group 2 Notifications filters are shared tabs while read commands stay POST', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/notifications/?filter=unread');
  const filters = page.getByRole('navigation', { name: 'Filtrer les notifications' });
  await expect(filters).toHaveClass(/mk-interaction-tabs/);
  await expect(filters.getByRole('link', { name: /Non lues/ })).toHaveAttribute('aria-current', 'page');
  const markAll = page.getByRole('button', { name: 'Tout marquer comme lu' });
  if (await markAll.count()) {
    await expect(markAll).toHaveAttribute('data-variant', 'primary');
    const form = markAll.locator('xpath=ancestor::form[1]');
    await expect(form).toHaveAttribute('method', 'post');
    await expect(form.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
  }
});

test('Group 2 secondary Me choices reuse shared link controls', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/moi/choix/');
  await expect(page.locator('head link[href*="me-n1.css"]')).toHaveCount(1);
  await expect(page.getByRole('link', { name: 'Modifier' }).first()).toHaveClass(/mk-action-button/);
  await expect(page.locator('.mk-me-choices .mk-action-button[data-variant="link"]').first()).toBeVisible();
});


test('Group 2 History, personal resources and Conversations reuse native owner-backed tabs', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');

  for (const [path, label, firstOption] of [
    ['/me/history/', 'Filtrer l’historique', 'Tout'],
    ['/library/documents/', 'Vue des documents', 'Tous'],
    ['/trust/proofs/', 'Vue des preuves', 'Toutes'],
    ['/trust/credentials/', 'Vue des titres', 'Tous'],
    ['/conversations/', 'Conversations', 'Toutes'],
  ]) {
    await page.goto(path);
    const tabs = page.getByRole('navigation', { name: label });
    await expect(tabs).toHaveClass(/mk-interaction-tabs/);
    await expect(tabs.getByRole('link', { name: firstOption, exact: true })).toHaveAttribute(
      'aria-current', 'page',
    );
    await expect(page.locator('[data-mk-query-local="true"]')).toHaveCount(0);
  }
});


test('Group 2 account switching uses shared inverse actions and external composition', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/account/switch/');
  await expect(page.locator('head link[href*="account-switcher-layout.css"]')).toHaveCount(1);
  const add = page.getByRole('button', { name: '+ Ajouter un compte' });
  await expect(add).toHaveClass(/mk-action-button/);
  await expect(add).toHaveAttribute('data-variant', 'inverse');
  const form = add.locator('xpath=ancestor::form[1]');
  await expect(form).toHaveAttribute('method', 'post');
  await expect(form.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
});


test('Group 2 auxiliary Groups and Tickets reuse shared actions and preserve owner routes', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  for (const path of ['/groups/', '/tickets/']) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBeLessThan(500);
    await expect(page.locator('head link[href*="makolo-interactions.css"]')).toHaveCount(1);
    await expect(page.locator('main, [role="main"]').first()).toBeVisible();
  }
  await page.goto('/groups/');
  const create = page.getByRole('link', { name: 'Créer un Groupe' });
  await expect(create).toHaveClass(/mk-action-button/);
  await expect(create).toHaveAttribute('data-variant', 'primary');
});

test('Group 2 private Passport history composes shared controls without exposing revocation actions', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  const response = await page.goto('/passport/me/history/');
  expect(response?.status()).toBeLessThan(500);
  await expect(page.locator('head link[href*="makolo-interactions.css"]')).toHaveCount(1);
  const revocations = page.getByRole('button', { name: /Révoquer/ });
  for (const button of await revocations.all()) {
    await expect(button).toHaveClass(/mk-action-button/);
    await expect(button).toHaveAttribute('data-variant', 'danger');
    const form = button.locator('xpath=ancestor::form[1]');
    await expect(form).toHaveAttribute('method', 'post');
    await expect(form.locator('input[name="csrfmiddlewaretoken"]')).toHaveCount(1);
  }
});
