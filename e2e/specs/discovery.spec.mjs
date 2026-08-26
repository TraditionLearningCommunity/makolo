import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


test('discovery finds Event and Transport by place and date @firefox', async ({ page }) => {
  await page.goto('/discover/?place=Lubumbashi&when=tomorrow');
  await expect(page.getByRole('heading', { name: 'Trouver une activité' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Lubumbashi → Kolwezi E2E' })).toBeVisible();
  await expect(page.getByText('Discovery Unlisted E2E')).toHaveCount(0);
  await expect(page.getByText('Discovery Private E2E')).toHaveCount(0);
  await expect(page.locator('#discovery-map')).toHaveCount(0);

  await page.getByLabel('Catégorie').selectOption('transport');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByRole('heading', { name: 'Lubumbashi → Kolwezi E2E' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toHaveCount(0);
  await page.getByRole('link', { name: 'Réserver' }).first().click();
  await expect(page).toHaveURL(/\/transport\/departures\//);
  await page.goBack();

  await page.getByLabel('Catégorie').selectOption('event');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await page.getByRole('link', { name: /S’inscrire|Voir l’événement/ }).first().click();
  await expect(page).toHaveURL(/\/events\//);
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E', exact: true })).toBeVisible();
});


test('global search focuses Discovery and Activity favorite stays independent', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');
  await page.getByRole('link', { name: 'Rechercher sur Makolo' }).click();
  await expect(page).toHaveURL(/\/discover\/\?focus=search/);
  await expect(page.locator('#discover-query')).toBeFocused();

  await page.locator('#discover-query').fill('Lubumbashi → Kolwezi E2E');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  const transport = page.locator('article').filter({ hasText: 'Lubumbashi → Kolwezi E2E' }).first();
  await expect(transport).toBeVisible();
  const remove = transport.getByRole('button', { name: 'Retirer des favoris' });
  if (await remove.count()) {
    await remove.click();
    await page.waitForLoadState('domcontentloaded');
  }
  await page.locator('article').filter({ hasText: 'Lubumbashi → Kolwezi E2E' }).first().getByRole('button', { name: 'Enregistrer dans les favoris' }).click();
  await page.goto('/discover/bookmarks/');
  await expect(page.getByRole('heading', { name: 'Lubumbashi → Kolwezi E2E' })).toBeVisible();
});


test('Discovery keeps results usable when MapLibre tile loading fails', async ({ page }) => {
  await page.route('https://tile.openstreetmap.org/**', route => route.fulfill({
    status: 200,
    contentType: 'image/png',
    body: 'not-a-valid-png',
  }));
  await page.goto('/discover/?q=Discovery+Event+E2E&when=tomorrow&vertical=event&lat=-11.6647&lon=27.4794&radius_km=10');

  const map = page.locator('#discovery-map');
  const fallback = page.locator('#discovery-map-fallback');
  await expect(fallback).toBeVisible();
  await expect(map).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.getByRole('link', { name: /S’inscrire|Voir l’événement/ }).first()).toBeVisible();
});


test('mobile discovery is list-first and enables map only after nearby action @mobile', async ({ page, context }) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: -11.6647, longitude: 27.4794 });
  await page.goto('/discover/?place=Lubumbashi&when=tomorrow');
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.locator('#discovery-map-panel')).toHaveCount(0);

  await page.getByRole('button', { name: 'Autour de moi' }).click();
  await expect(page).toHaveURL(/lat=-11\.6647/);
  await expect(page.getByText(/Proximité active/)).toBeVisible();
  await expect(page.locator('#discovery-map-panel')).toBeHidden();
  await page.getByRole('button', { name: 'Carte' }).click();
  await expect(page.locator('#discovery-map-panel')).toBeVisible();
  await expect(page.locator('#discovery-map canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Liste' }).click();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
});


test('nearby permission denial keeps textual Discovery usable', async ({ page, context }) => {
  await context.clearPermissions();
  await page.goto('/discover/?q=Discovery+Event+E2E&when=tomorrow');
  await expect(page.locator('#discovery-map')).toHaveCount(0);
  await page.getByRole('button', { name: 'Autour de moi' }).click();
  await expect(page.getByRole('status')).toContainText(/Localisation indisponible|position n’est pas disponible/i);
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
});
