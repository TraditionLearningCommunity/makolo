import { test, expect } from '../fixtures/makolo.mjs';


test('visitor discovers an event and its public organizer @firefox', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Ça vous intéresserait/i })).toBeVisible();
  await expect(page.getByRole('banner').getByRole('link', { name: 'Connexion', exact: true })).toBeVisible();

  await page.getByLabel('Rechercher des possibilités').fill('Festival Makolo E2E');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page).toHaveURL(/\/discover\/\?q=Festival/);
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E' }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Makolo E2E Events' }).first().click();
  await expect(page.getByRole('heading', { name: 'Makolo E2E Events', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Festival Makolo E2E', exact: true })).toBeVisible();
  await page.getByRole('link', { name: /Retour à la découverte/i }).click();
  await expect(page.getByRole('heading', { name: 'Qu’avez-vous envie de vivre, faire ou obtenir ?' })).toBeVisible();
});



test('guest home explains the action path and exposes existing Discover filters', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Makolo vous accompagne jusqu’à l’action' })).toBeVisible();
  const journey = page.getByRole('complementary', { name: 'Makolo vous accompagne jusqu’à l’action' });
  await expect(journey.getByRole('heading', { name: 'Découvrez' })).toBeVisible();
  await expect(journey.getByRole('heading', { name: 'Préparez' })).toBeVisible();
  await expect(journey.getByRole('heading', { name: 'Avancez' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Explorer les possibilités' })
    .getByRole('link', { name: 'Participer' }).click();
  await expect(page).toHaveURL(/\/discover\/\?vertical=event/);
});

test('private participant surface sends visitor to login with next preserved', async ({ page }) => {
  await page.goto('/tickets/');
  await expect(page).toHaveURL(/\/login\/\?next=\/tickets\//);
  await expect(page.getByRole('heading', { name: 'Bon retour.' })).toBeVisible();
});


test('mobile public home remains usable without horizontal overflow @mobile', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Ça vous intéresserait/i })).toBeVisible();
  await expect(page.getByRole('banner').getByRole('link', { name: 'Connexion', exact: true })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.getByLabel('Rechercher des possibilités').fill('Atelier Makolo Visuel');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByText('Atelier Makolo Visuel').first()).toBeVisible();
});
