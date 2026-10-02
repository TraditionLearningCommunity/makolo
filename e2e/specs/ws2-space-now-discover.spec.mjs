import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE = '/spaces/makolo-e2e-events/';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectUnavailableSurface(page, surface) {
  const locator = page.locator(`[data-space-surface="${surface}"]`);
  await expect(locator).toBeVisible();
  await expect(locator).toHaveAttribute('data-space-state', 'unavailable');
  await expect(locator.getByText('La sélection n’est pas encore disponible.', { exact: true })).toBeVisible();
  await expect(locator.getByText('no_safe_selection_contract', { exact: false })).toHaveCount(0);
}

test('WS2 Maintenant and Discover stay calm and responsive across Web regimes @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  for (const viewport of [
    { width: 400, height: 844 },
    { width: 800, height: 1024 },
    { width: 1199, height: 900 },
    { width: 1200, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);

    await page.goto(SPACE);
    await expectNoHorizontalOverflow(page);
    await expect(page.getByRole('heading', { name: /Qu’est-ce qui mérite notre attention maintenant/ })).toBeVisible();
    await expectUnavailableSurface(page, 'now');
    await expect(page.getByText('Tout est en ordre. ✓', { exact: true })).toHaveCount(0);

    await page.goto(`${SPACE}discover/`);
    await expectNoHorizontalOverflow(page);
    await expect(page.getByRole('heading', { name: /Qu’est-ce qui pourrait nous aider à avancer/ })).toBeVisible();
    await expectUnavailableSurface(page, 'discover');
  }
});

test('WS2 keeps direct URLs and browser history between Maintenant and Discover', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto(SPACE);
  const sidebar = page.locator('#desktop-sidebar');
  await sidebar.getByRole('link', { name: 'Découvrir', exact: true }).click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/discover\/$/);
  await expectUnavailableSurface(page, 'discover');

  await page.goBack();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/$/);
  await expectUnavailableSurface(page, 'now');

  await page.goForward();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/discover\/$/);
  await expectUnavailableSurface(page, 'discover');
});
