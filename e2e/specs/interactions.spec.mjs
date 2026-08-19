import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


async function forceLight(page) {
  await page.evaluate(() => localStorage.setItem('theme', 'light'));
  await page.reload();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
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
  await expect(page.getByText('Lire une image QR')).toBeVisible();
  await expect(page.getByLabel('Saisie manuelle du jeton QR')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Démarrer la caméra' })).toBeEnabled();
});


test('keyboard supports Tab, Shift+Tab, Enter, Space and Escape on the app shell', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await forceLight(page);
  await page.keyboard.press('Home');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Aller au contenu principal' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();

  const themeButton = page.getByRole('button', { name: 'Changer le thème' });
  const notifications = page.locator('header').getByRole('link', { name: 'Notifications' });
  await themeButton.focus();
  await page.keyboard.press('Shift+Tab');
  await expect(notifications).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(themeButton).toBeFocused();
  await page.keyboard.press('Space');
  await expect(page.locator('html')).toHaveClass(/dark/);

  await page.getByRole('button', { name: 'Menu utilisateur' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('menu')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toBeHidden();
});


test('mobile navigation opens, closes with Escape and does not overflow @mobile', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.getByRole('button', { name: 'Ouvrir la navigation' }).click();
  await expect(page.getByRole('dialog', { name: 'Navigation Makolo' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Découvrir' }).last()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Navigation Makolo' })).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});


test('theme choice persists and representative surfaces remain readable @mobile', async ({ page }) => {
  await login(page, 'visual.participant@e2e.makolo.test');
  await forceLight(page);
  await page.getByRole('button', { name: 'Changer le thème' }).click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.goto('/discover/');
  await expect(page.getByRole('heading', { name: /Trouvez l’événement/i })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});


test('critical discovery smoke also runs on Firefox @firefox-only @firefox', async ({ page }) => {
  await page.goto('/discover/');
  await expect(page.getByText('Festival Makolo E2E').first()).toBeVisible();
  await page.getByRole('link', { name: 'Festival Makolo E2E' }).first().click();
  await expect(page.getByRole('link', { name: /Obtenir des billets/i })).toBeVisible();
});
