import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE = '/spaces/makolo-e2e-events/';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

async function expectSharedDiscovery(page) {
  const locator = page.locator('[data-mk-surface="discover"]');
  await expect(locator).toBeVisible();
  await expect(page.locator('#discovery-search-form')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Qu’est-ce qui pourrait nous aider à avancer/ })).toBeVisible();
  await expect(page.getByText('no_safe_selection_contract', { exact: false })).toHaveCount(0);
  await expect(page.getByText('Enregistrer comme veille', { exact: true })).toHaveCount(0);

}

async function expectPartiallyCoveredNow(page) {
  const locator = page.locator('[data-space-surface="now"]');
  await expect(locator).toBeVisible();
  await expect(locator).toHaveAttribute('data-space-state', 'partial');
  await expect(locator.getByText('Certaines situations sont connues, mais tous les domaines de cet Espace ne sont pas encore couverts.', { exact: false })).toBeVisible();
  await expect(locator.getByText('Tout est en ordre. ✓', { exact: true })).toHaveCount(0);
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
    await expectPartiallyCoveredNow(page);
    await expect(page.getByText('Tout est en ordre. ✓', { exact: true })).toHaveCount(0);

    await page.goto(`${SPACE}discover/`);
    await expectNoHorizontalOverflow(page);
    await expect(page.getByRole('heading', { name: /Qu’est-ce qui pourrait nous aider à avancer/ })).toBeVisible();
    await expectSharedDiscovery(page);
  }
});

test('WS2 keeps direct URLs and browser history between Maintenant and Discover', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto(SPACE);
  const sidebar = page.locator('#desktop-sidebar');
  await sidebar.getByRole('link', { name: 'Découvrir', exact: true }).click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/discover\/$/);
  await expectSharedDiscovery(page);

  await page.goBack();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/$/);
  await expectPartiallyCoveredNow(page);

  await page.goForward();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/discover\/$/);
  await expectSharedDiscovery(page);
});
