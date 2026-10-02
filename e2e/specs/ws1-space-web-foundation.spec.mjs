import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE = '/spaces/makolo-e2e-events/';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectSpaceNavigation(page, compact) {
  const nav = compact
    ? page.locator('#mobile-primary-nav')
    : page.locator('#desktop-sidebar .mk-mature-rail');

  await expect(nav).toBeVisible();
  const links = nav.locator(':scope > a');
  await expect(links).toHaveCount(5);
  for (let index = 0; index < 5; index += 1) {
    await expect(links.nth(index)).toBeVisible();
  }

  if (compact) {
    for (const label of ['Maintenant', 'Découvrir', 'Makolo', 'Nous']) {
      await expect(nav.getByText(label, { exact: true })).toBeVisible();
    }
  } else {
    for (const label of ['Maintenant', 'Découvrir', 'Makolo', 'Nous']) {
      await expect(nav.getByText(label, { exact: true })).toHaveCount(1);
    }
  }

  await expect(nav.getByText('En cours', { exact: true })).toHaveCount(0);
  await expect(nav.getByText('Moi', { exact: true })).toHaveCount(0);
}

test('WS1 Space shell respects Compact Adaptive and Expanded regimes @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  for (const viewport of [
    { width: 400, height: 844, compact: true },
    { width: 800, height: 1024, compact: false },
    { width: 1199, height: 900, compact: false },
    { width: 1200, height: 900, compact: false },
    { width: 1440, height: 900, compact: false },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(SPACE);
    await expectNoHorizontalOverflow(page);
    await expect(page.getByText('Agir au nom de', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Responsabilité de lecture')).toBeVisible();
    await expectSpaceNavigation(page, viewport.compact);
  }
});

test('WS1 Space navigation keeps direct URLs HTMX and browser history coherent', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(SPACE);

  const sidebar = page.locator('#desktop-sidebar');
  await sidebar.getByRole('link', { name: 'Découvrir', exact: true }).click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/discover\/$/);
  await expect(page.getByRole('heading', { name: /Qu’est-ce qui pourrait nous aider à avancer/ })).toBeVisible();

  await page.goBack();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/$/);
  await expect(sidebar.getByRole('link', { name: 'Maintenant', exact: true })).toHaveAttribute('aria-current', 'page');

  await page.goto('/spaces/makolo-e2e-events/us/');
  await expect(page.getByRole('heading', { name: /Qui sommes-nous/ })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
