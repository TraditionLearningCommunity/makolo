import { test, expect } from '../fixtures/makolo.mjs';


test('visitor discovers an event and its public organizer @firefox', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Trouvez quoi faire/i })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Connexion' })).toBeVisible();

  await page.getByLabel('Rechercher une activité').fill('Festival Makolo E2E');
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
  await expect(page.getByRole('heading', { name: 'Trouver une activité' })).toBeVisible();
});


test('private participant surface sends visitor to login with next preserved', async ({ page }) => {
  await page.goto('/tickets/');
  await expect(page).toHaveURL(/\/login\/\?next=\/tickets\//);
  await expect(page.getByRole('heading', { name: 'Bon retour.' })).toBeVisible();
});


test('mobile public home remains usable without horizontal overflow @mobile', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Trouvez quoi faire/i })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Connexion' })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.getByLabel('Rechercher une activité').fill('Atelier Makolo Visuel');
  await page.getByRole('button', { name: 'Rechercher' }).click();
  await expect(page.getByText('Atelier Makolo Visuel').first()).toBeVisible();
});
