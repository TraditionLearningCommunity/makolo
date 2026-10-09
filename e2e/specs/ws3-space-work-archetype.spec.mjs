import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const WORK = '/spaces/makolo-e2e-events/work/';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test('WS3 Métier stays usable across Compact Adaptive and Expanded regimes @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  for (const viewport of [
    { width: 400, height: 844 },
    { width: 800, height: 1024 },
    { width: 1199, height: 900 },
    { width: 1200, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    const response = await page.goto(WORK);
    expect(response.status()).toBe(200);
    await expectNoHorizontalOverflow(page);
    const work = page.locator('[data-ws3-work]');
    await expect(work).toBeVisible();
    await expect(work.getByRole('heading', { name: 'Activités', exact: true })).toBeVisible();
    const ownerBackedItem = work.locator('[data-work-item]').first();
    const honestEmpty = work.locator('#work-empty-title');
    expect((await ownerBackedItem.count()) + (await honestEmpty.count())).toBeGreaterThan(0);
    if (await honestEmpty.count()) {
      await expect(honestEmpty).toContainText('Aucune activité visible');
    }
  }
});

test('WS3 owner handoff keeps standard navigation and browser history', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(WORK);

  const ownerLink = page.locator('[data-work-item] a', { hasText: 'Ouvrir' }).first();
  if (await ownerLink.count()) {
    const workUrl = page.url();
    await ownerLink.click();
    await expect(page).not.toHaveURL(workUrl);
    await page.goBack();
    await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/work\/$/);
    await expect(page.locator('[data-ws3-work]')).toBeVisible();
  }
});
