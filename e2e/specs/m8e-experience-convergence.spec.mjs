import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}


test('mature personal navigation keeps the five canonical contexts on desktop', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');

  const sidebar = page.locator('#desktop-sidebar');
  await expect(sidebar.getByRole('link', { name: 'Maintenant', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(sidebar.getByRole('link', { name: 'Découvrir', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Makolo Mark', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'En cours', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Moi', exact: true })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Conversations', exact: true })).toHaveCount(0);
  await expect(sidebar.getByRole('link', { name: 'Profil', exact: true })).toHaveCount(0);

  await sidebar.getByRole('link', { name: 'En cours', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ce qui continue', exact: true })).toBeVisible();
  await expect(page.locator('#desktop-sidebar').getByRole('link', { name: 'En cours', exact: true })).toHaveAttribute('aria-current', 'page');

  await page.locator('#desktop-sidebar').getByRole('link', { name: 'Moi', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Passeport Makolo', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Mes collectifs', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Mes ressources', exact: true })).toBeVisible();
  await expect(page.locator('#desktop-sidebar').getByRole('link', { name: 'Moi', exact: true })).toHaveAttribute('aria-current', 'page');
});


test('mature shell keeps Compact below 768px and switches to Adaptive at tablet width @mobile', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  const compactViewports = [
    { width: 320, height: 700 },
    { width: 360, height: 800 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
    { width: 767, height: 1024 },
  ];

  for (const viewport of compactViewports) {
    await page.setViewportSize(viewport);
    await page.goto('/me/');
    await expectNoHorizontalOverflow(page);

    const mobileNav = page.locator('#mobile-primary-nav');
    await expect(mobileNav).toBeVisible();
    for (const label of ['Maintenant', 'Découvrir', 'Makolo', 'En cours', 'Moi']) {
      await expect(mobileNav.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(mobileNav.getByText('Conversations', { exact: true })).toHaveCount(0);
    await expect(mobileNav.getByText('Profil', { exact: true })).toHaveCount(0);
    await expect(mobileNav.getByText('Plus', { exact: true })).toHaveCount(0);
  }

  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('/me/');
  await expectNoHorizontalOverflow(page);
  await expect(page.locator('#mobile-primary-nav')).toBeHidden();
  await expect(page.locator('#desktop-sidebar')).toBeVisible();
  await expect(page.locator('#desktop-sidebar')).toHaveCSS('width', '84px');
});


test('Maintenant can end calmly without filling the screen', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');

  const home = page.locator('#main-content');
  await expect(home.getByText('Ensuite', { exact: true })).toHaveCount(0);
  await expect(home.getByText('Et maintenant ?', { exact: true })).toHaveCount(0);
  await expect(home.getByText('Ce que je dois savoir', { exact: true })).toHaveCount(0);
});


test('Makolo Mark starts from one natural-language intake and stays conservative', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/mark/');

  await expect(page.getByRole('heading', { name: 'Qu’est-ce que vous avez en tête ?' })).toBeVisible();
  const input = page.getByLabel('Ce que vous voulez donner à Makolo');
  await expect(input).toBeVisible();
  await input.fill('Je cherche quelque chose à faire ce soir');
  await page.getByRole('button', { name: 'Continuer' }).click();
  await expect(page).toHaveURL(/\/discover\/\?q=/);
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
