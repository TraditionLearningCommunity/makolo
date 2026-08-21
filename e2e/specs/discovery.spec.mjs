import { test, expect } from '../fixtures/makolo.mjs';


test('discovery finds Event and Transport by place and date @firefox', async ({ page }) => {
  await page.goto('/discover/?place=Lubumbashi&when=tomorrow');
  await expect(page.getByRole('heading', { name: 'Trouver une activité' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Lubumbashi → Kolwezi E2E' })).toBeVisible();
  await expect(page.getByText('Discovery Unlisted E2E')).toHaveCount(0);
  await expect(page.getByText('Discovery Private E2E')).toHaveCount(0);

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


test('MapLibre renders discovery points and selecting a point highlights its result', async ({ page }) => {
  await page.goto('/discover/?q=Discovery+Event+E2E&place=Lubumbashi&when=tomorrow&vertical=event');
  const map = page.locator('#discovery-map');
  await expect(map).toBeVisible();
  await map.scrollIntoViewIfNeeded();
  await page.waitForFunction(() => window.__makoloDiscoveryMap?.getSource('discovery-results'));
  await page.evaluate(() => {
    window.__makoloDiscoveryMap.resize();
    window.__makoloDiscoveryMap.triggerRepaint();
  });
  await expect(map.locator('canvas')).toBeVisible();

  const marker = map.locator('.discovery-map-marker');
  await expect(marker).toBeVisible();
  const first = await page.locator('#discovery-map-data').evaluate(node => JSON.parse(node.textContent)[0]);
  await marker.click();
  await expect(page.locator(`[data-discovery-result="${first.occurrence_id}"]`)).toHaveClass(/ring-2/);
  await expect(page.getByRole('link', { name: first.cta_label }).last()).toBeVisible();
});


test('mobile discovery keeps list primary and can switch to map @mobile', async ({ page }) => {
  await page.goto('/discover/?place=Lubumbashi&when=tomorrow');
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.locator('#discovery-map-panel')).toBeHidden();
  await page.getByRole('button', { name: 'Carte' }).click();
  await expect(page.locator('#discovery-map-panel')).toBeVisible();
  await expect(page.locator('#discovery-map canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Liste' }).click();
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
});
