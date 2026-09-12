import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}


test('mature personal navigation keeps action surfaces coherent on desktop', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');

  const sidebar = page.locator('#desktop-sidebar');
  await expect(sidebar.getByRole('link', { name: 'Accueil', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(sidebar.getByRole('link', { name: 'Mes démarches', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Conversations', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Profil', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Découvrir', exact: true })).toHaveCount(1);

  await sidebar.getByRole('link', { name: 'Conversations', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Conversations', exact: true })).toBeVisible();
  await expect(page.locator('#desktop-sidebar').getByRole('link', { name: 'Conversations', exact: true })).toHaveAttribute('aria-current', 'page');

  await page.locator('#desktop-sidebar').getByRole('link', { name: 'Profil', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Mon profil', exact: true })).toBeVisible();
  await expect(page.locator('#desktop-sidebar').getByRole('link', { name: 'Profil', exact: true })).toHaveAttribute('aria-current', 'page');
});


test('mature mobile shell stays usable from 320px through tablet @mobile', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  const viewports = [
    { width: 320, height: 700 },
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
    { width: 768, height: 1024 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await page.goto('/me/');
    await expectNoHorizontalOverflow(page);

    if (viewport.width < 768) {
      const mobileNav = page.locator('#mobile-primary-nav');
      await expect(mobileNav).toBeVisible();
      for (const label of ['Accueil', 'Démarches', 'Conversations', 'Profil', 'Plus']) {
        await expect(mobileNav.getByText(label, { exact: true })).toBeVisible();
      }
      await expect(mobileNav.getByText('Découvrir', { exact: true })).toHaveCount(0);
    }
  }
});


test('bounded Discover names the real end of the current corpus', async ({ page }) => {
  await page.goto('/discover/?q=Discovery+Event+E2E&when=tomorrow&vertical=event');
  await expect(page.getByRole('heading', { name: 'Discovery Event E2E' })).toBeVisible();
  await expect(page.getByText('Vous avez vu ce qui est pertinent ici.')).toBeVisible();
  await expect(page.getByText(/ne relâche pas vos critères en silence/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Modifier ma recherche' })).toBeVisible();
});


test('Space Now keeps collective context explicit and action-oriented', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/overview/');

  await expect(page.getByText('Agir au nom de', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Makolo E2E Events', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ce qui compte maintenant', exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Contexte de l’Espace' })).toBeVisible();
});
