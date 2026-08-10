import { execFileSync } from 'node:child_process';
import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const shot = async (page, name, options = {}) => {
  await expect(page).toHaveScreenshot(name, {
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.01,
    ...options,
  });
};

async function useLight(page) {
  await page.goto('/');
  await page.evaluate(() => localStorage.setItem('theme', 'light'));
  await page.reload();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
}

async function useDark(page) {
  await page.evaluate(() => localStorage.setItem('theme', 'dark'));
  await page.reload();
  await expect(page.locator('html')).toHaveClass(/dark/);
}

async function stableScanner(page) {
  await expect(page.locator('#camera-state')).not.toContainText('Initialisation');
  await page.getByRole('button', { name: 'Arrêter' }).click();
  await expect(page.locator('#camera-state')).toHaveText('Caméra arrêtée');
}


test.beforeAll(() => {
  execFileSync('python', ['manage.py', 'prepare_e2e'], { stdio: 'inherit' });
});


test('representative light desktop surfaces @visual', async ({ page }) => {
  await useLight(page);
  await shot(page, 'home-light-desktop.png');
  await page.goto('/discover/');
  await shot(page, 'discovery-light-desktop.png');

  await login(page, 'visual.participant@e2e.makolo.test');
  await shot(page, 'participant-dashboard-light-desktop.png');
  await page.goto('/tickets/');
  await page.getByRole('link', { name: /Invitation E2E/i }).first().click();
  await shot(page, 'ticket-light-desktop.png');

  await page.context().clearCookies();
  await login(page, 'new.organizer@e2e.makolo.test');
  await shot(page, 'organizer-dashboard-light-desktop.png');

  await page.context().clearCookies();
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await stableScanner(page);
  await shot(page, 'scanner-light-desktop.png');

  await page.context().clearCookies();
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/operations/');
  await shot(page, 'operations-light-desktop.png', {
    mask: [page.getByText(/^Généré /)],
  });
});


test('representative dark desktop surfaces @visual', async ({ page }) => {
  await useLight(page);
  await login(page, 'visual.participant@e2e.makolo.test');
  await useDark(page);
  await shot(page, 'participant-dashboard-dark-desktop.png');
  await page.goto('/discover/');
  await shot(page, 'discovery-dark-desktop.png');

  await page.context().clearCookies();
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await stableScanner(page);
  await shot(page, 'scanner-dark-desktop.png');
});


test('representative mobile surfaces @visual @mobile @mobile-only', async ({ page }) => {
  await useLight(page);
  await shot(page, 'home-light-mobile.png');
  await page.goto('/discover/');
  await shot(page, 'discovery-light-mobile.png');

  await login(page, 'visual.participant@e2e.makolo.test');
  await shot(page, 'participant-dashboard-light-mobile.png');

  await page.context().clearCookies();
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await stableScanner(page);
  await shot(page, 'scanner-light-mobile.png');
});
