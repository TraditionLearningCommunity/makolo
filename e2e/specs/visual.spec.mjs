import { execFileSync } from 'node:child_process';
import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const shot = async (page, name) => {
  await expect(page).toHaveScreenshot(name, {
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.01,
  });
};

async function usePublicLight(page) {
  await page.goto('/');
  await page.evaluate(() => localStorage.setItem('theme', 'light'));
  await page.reload();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
}

async function setAccountAppearance(page, value) {
  const labels = { light: 'Clair', dark: 'Sombre' };
  await page.goto('/account/profile/#appearance');
  await page.getByLabel(labels[value], { exact: true }).check();
  await page.getByRole('button', { name: 'Enregistrer l’apparence' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', value);
}

test.beforeAll(() => {
  execFileSync('python', ['manage.py', 'prepare_e2e'], { stdio: 'inherit' });
  execFileSync('python', ['manage.py', 'prepare_transport_e2e'], { stdio: 'inherit' });
  execFileSync('python', ['manage.py', 'prepare_discovery_e2e'], { stdio: 'inherit' });
});

test('refresh Discovery light desktop baseline @visual', async ({ page }) => {
  await usePublicLight(page);
  await page.goto('/discover/');
  await expect(page.locator('#discovery-map')).toHaveCount(0);
  await shot(page, 'discovery-light-desktop.png');
});

test('refresh Discovery dark desktop baseline @visual', async ({ page }) => {
  await login(page, 'visual.participant@e2e.makolo.test');
  await setAccountAppearance(page, 'dark');
  await page.goto('/discover/');
  await expect(page.locator('#discovery-map')).toHaveCount(0);
  await shot(page, 'discovery-dark-desktop.png');
});

test('refresh Discovery light mobile baseline @visual @mobile @mobile-only', async ({ page }) => {
  await usePublicLight(page);
  await page.goto('/discover/');
  await expect(page.locator('#discovery-map-panel')).toHaveCount(0);
  await shot(page, 'discovery-light-mobile.png');
});
