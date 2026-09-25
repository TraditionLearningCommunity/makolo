import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


async function setAppearance(page, value) {
  const labels = { system: 'Système', light: 'Clair', dark: 'Sombre' };
  await page.goto('/account/profile/#appearance');
  await page.getByLabel(labels[value], { exact: true }).check();
  await page.getByRole('button', { name: 'Enregistrer l’apparence' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', value);
  if (value === 'dark') {
    await expect(page.locator('html')).toHaveClass(/dark/);
  } else {
    await expect(page.locator('html')).not.toHaveClass(/dark/);
  }
}


test('scanner explains denied camera permission while keeping image and manual fallbacks', async ({ page }) => {
  await page.addInitScript(() => {
    const denied = () => Promise.reject(new DOMException('Permission denied by E2E browser', 'NotAllowedError'));
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        enumerateDevices: async () => [
          { kind: 'videoinput', deviceId: 'e2e-camera-1', label: 'E2E Camera 1' },
          { kind: 'videoinput', deviceId: 'e2e-camera-2', label: 'E2E Camera 2' },
        ],
        getUserMedia: denied,
      },
    });
    try { delete window.BarcodeDetector; } catch (error) {}
  });
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await expect(page.locator('#camera-state')).toContainText(/refusé|indisponible/i);
  await expect(page.getByText('Lire un QR depuis une image')).toBeVisible();
  await expect(page.getByLabel('Code du billet')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Démarrer la caméra' })).toBeEnabled();
});


test('keyboard supports Tab, Shift+Tab, Enter and Escape on the mature app shell', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await setAppearance(page, 'light');
  await page.goto('/me/');
  await page.keyboard.press('Home');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Aller au contenu principal' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();

  const conversations = page.locator('header').getByRole('link', { name: /^Conversations/ });
  const notifications = page.locator('header').getByRole('link', { name: 'Notifications', exact: true });
  await notifications.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(conversations).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(notifications).toBeFocused();

  const userMenuButton = page.getByRole('button', { name: 'Menu utilisateur' });
  await expect(userMenuButton).toHaveAttribute('aria-expanded', 'false');
  await userMenuButton.focus();
  await page.keyboard.press('Enter');
  await expect(userMenuButton).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('menu')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(userMenuButton).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('menu')).toBeHidden();

  await userMenuButton.click();
  await page.getByRole('menuitem', { name: 'Compte et paramètres' }).click();
  await expect(page).toHaveURL(/\/account\/profile\/$/);
  await expect(page.getByText('Apparence', { exact: true }).first()).toBeVisible();
});


test('mobile primary navigation stays visible and does not overflow @mobile', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  const mobileNav = page.locator('#mobile-primary-nav');
  await expect(mobileNav).toBeVisible();
  for (const label of ['Maintenant', 'Découvrir', 'En cours', 'Moi']) {
    await expect(mobileNav.getByRole('link', { name: label, exact: true })).toBeVisible();
  }
  await expect(mobileNav.getByRole('link', { name: 'Makolo Mark' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ouvrir la navigation' })).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});


test('account appearance persists and representative surfaces remain readable @mobile', async ({ page }) => {
  await login(page, 'visual.participant@e2e.makolo.test');
  await setAppearance(page, 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.goto('/discover/');
  await expect(page.getByRole('heading', { name: 'Qu’avez-vous envie de vivre, faire ou obtenir ?' })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});


test('critical discovery smoke also runs on Firefox @firefox-only @firefox', async ({ page }) => {
  await page.goto('/discover/');
  await expect(page.getByText('Festival Makolo E2E').first()).toBeVisible();
  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await expect(page.getByRole('link', { name: /Acheter le billet/i })).toBeVisible();
});


test('expanded shell keeps the workspace stable while the desktop rail changes density', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, 'empty.participant@e2e.makolo.test');
  await expect(page.locator('.mk-workspace')).toHaveAttribute('data-workspace-layout', 'focus');
  await expect(page.locator('#mobile-primary-nav')).toBeHidden();

  const sidebar = page.locator('#desktop-sidebar');
  const toggle = page.getByRole('button', { name: 'Réduire ou développer la navigation' });
  await expect(sidebar).toHaveCSS('width', '232px');
  await sidebar.hover();
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  await expect(sidebar).toHaveCSS('width', '84px');

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});


test('workspace runtime scopes and deduplicates private projections in memory', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await expect(page.locator('#main-content')).toHaveAttribute('data-mk-runtime-scope', 'personal');

  let requests = 0;
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/me/now/') requests += 1;
  });

  const projections = await page.evaluate(async () => {
    const runtime = window.MakoloWorkspaceRuntime;
    const [first, second] = await Promise.all([
      runtime.load('/api/v1/me/now/'),
      runtime.load('/api/v1/me/now/'),
    ]);
    const cached = await runtime.load('/api/v1/me/now/');
    return [first.meta.projection, second.meta.projection, cached.meta.projection];
  });

  expect(projections).toEqual(['personal.now', 'personal.now', 'personal.now']);
  expect(requests).toBe(1);

  await page.evaluate(async () => {
    window.MakoloWorkspaceRuntime.invalidate('/api/v1/me/now/');
    await window.MakoloWorkspaceRuntime.load('/api/v1/me/now/');
  });
  expect(requests).toBe(2);
});


test('expanded personal surfaces keep context while compact links stay available', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, 'visual.participant@e2e.makolo.test');

  await page.goto('/me/ongoing/');
  await expect(page.locator('.mk-workspace')).toHaveAttribute('data-workspace-layout', 'master-detail');
  const expandedItem = page.locator('.mk-ongoing-card--expanded').first();
  const compactItem = page.locator('.mk-ongoing-card--compact').first();
  await expect(expandedItem).toBeVisible();
  await expect(compactItem).toBeHidden();

  const originalUrl = page.url();
  const selectedTitle = await expandedItem.getByRole('heading').textContent();
  await expandedItem.click();
  await expect(page).toHaveURL(originalUrl);
  await expect(page.locator('#ongoing-dates')).toBeVisible();
  await expect(page.locator('#ongoing-detail-body')).toContainText(selectedTitle.trim());

  await page.goto('/me/moi/');
  await expect(page.locator('.mk-me-grid')).toHaveCSS('display', 'grid');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
