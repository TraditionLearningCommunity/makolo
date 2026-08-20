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
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'auto';
    document.documentElement.style.overflowAnchor = 'none';
    document.body.style.overflowAnchor = 'none';
  });
  await expect(page.locator('#camera-state')).not.toContainText('Initialisation');
  await page.getByRole('button', { name: 'Arrêter' }).click();
  await expect(page.locator('#camera-state')).toHaveText('Caméra arrêtée');
  await page.keyboard.press('Escape');
  await page.evaluate(() => {
    document.activeElement?.blur();
    window.scrollTo(0, 0);
  });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
}

async function stableDiscoveryMap(page) {
  const mapContainer = page.locator('#discovery-map');
  await expect(mapContainer).toBeVisible();
  await mapContainer.scrollIntoViewIfNeeded();
  await expect(mapContainer.locator('canvas')).toBeVisible();
  await page.waitForFunction(() => {
    const map = window.__makoloDiscoveryMap;
    if (!map?.getSource('discovery-results')) return false;
    if (document.querySelector('.discovery-map-marker')) return true;
    const layers = ['discovery-clusters', 'discovery-points'].filter((id) => map.getLayer(id));
    return layers.length > 0 && map.queryRenderedFeatures({ layers }).length > 0;
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
}

async function assertDesktopShellStable(page) {
  await expect(page.locator('aside.mk-sidebar').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ouvrir la navigation' })).toBeHidden();
  await expect(page.getByRole('dialog', { name: 'Navigation Makolo' })).toBeHidden();

  const layout = await page.evaluate(() => {
    const offenders = [...document.querySelectorAll('body *')]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          id: element.id || '',
          className: typeof element.className === 'string' ? element.className.slice(0, 160) : '',
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter(({ left, right, width }) => width > 0 && (left < -1 || right > window.innerWidth + 1))
      .slice(0, 12);
    return {
      viewportWidth: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      offenders,
    };
  });
  expect(layout.overflow, JSON.stringify(layout)).toBeLessThanOrEqual(1);
}


test.beforeAll(() => {
  execFileSync('python', ['manage.py', 'prepare_e2e'], { stdio: 'inherit' });
  execFileSync('python', ['manage.py', 'prepare_transport_e2e'], { stdio: 'inherit' });
  execFileSync('python', ['manage.py', 'prepare_discovery_e2e'], { stdio: 'inherit' });
});


test('representative light desktop surfaces @visual', async ({ page }) => {
  await useLight(page);
  await shot(page, 'home-light-desktop.png');
  await page.goto('/discover/');
  await stableDiscoveryMap(page);
  await shot(page, 'discovery-light-desktop.png');

  await login(page, 'visual.participant@e2e.makolo.test');
  await shot(page, 'participant-dashboard-light-desktop.png');
  await page.goto('/tickets/');
  await page.getByRole('link', { name: /Invitation E2E/i }).first().click();
  await shot(page, 'ticket-light-desktop.png', {
    mask: [page.getByRole('img', { name: 'QR du ticket' })],
  });

  await page.context().clearCookies();
  await login(page, 'new.organizer@e2e.makolo.test');
  await shot(page, 'organizer-dashboard-light-desktop.png');

  await page.context().clearCookies();
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await stableScanner(page);
  await assertDesktopShellStable(page);
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
  await stableDiscoveryMap(page);
  await shot(page, 'discovery-dark-desktop.png');

  await page.context().clearCookies();
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/event/festival-makolo-e2e/');
  await stableScanner(page);
  await assertDesktopShellStable(page);
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
