import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE = '/spaces/makolo-e2e-events/';

test('Group 3 Space Work and owner depth navigation use the shared interaction layer', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  const response = await page.goto(SPACE + 'work/');
  expect(response?.status()).toBe(200);
  await expect(page.locator('link[href*="makolo-interactions.css"]')).toHaveCount(1);
  await expect(page.locator('[data-ws3-work]')).toBeVisible();
  const oldActions = page.locator('[data-ws3-work] a.mk-btn');
  await expect(oldActions).toHaveCount(0);
  const actions = page.locator('[data-ws3-work] a.mk-action-button');
  expect(await actions.count()).toBeGreaterThan(0);
  for (const action of await actions.all()) {
    const variant = await action.getAttribute('data-variant');
    expect(['primary', 'secondary', 'ghost', 'link']).toContain(variant);
  }
});

test('Group 3 scanner hidden command stays hidden despite shared action CSS', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto(SPACE + 'control/');
  const next = page.locator('#scan-next');
  await expect(next).toHaveClass(/mk-action-button/);
  await expect(next).toBeHidden();
  const start = page.locator('#start-camera');
  await expect(start).toHaveClass(/mk-action-button/);
  const height = await start.evaluate(node => node.getBoundingClientRect().height);
  expect(height).toBeGreaterThanOrEqual(44);
});

test('Group 3 native Space selection disclosure remains keyboard-accessible', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto(SPACE + 'work/');
  const context = page.locator('summary.mk-disclosure-trigger').first();
  if (await context.count()) {
    await context.focus();
    await page.keyboard.press('Enter');
    await expect(context.locator('xpath=ancestor::details[1]')).toHaveAttribute('open', '');
  }
});

test('Group 3 Space Work compact controls do not overflow the viewport @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(SPACE + 'work/');
  await expect(page.locator('[data-ws3-work]')).toBeVisible();
  const size = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  expect(size.content).toBeLessThanOrEqual(size.viewport + 1);
});

test('Group 3 personal scanner retains owner commands without exposing next-scan early', async ({ page }) => {
  await login(page, 'scanner@e2e.makolo.test');
  await page.goto('/scanner/');
  await expect(page.locator('link[href*="makolo-interactions.css"]')).toHaveCount(1);
  const cards = page.locator('article');
  if (await cards.count()) {
    const go = cards.first().getByRole('link', { name: /Scanner/ });
    if (await go.count()) {
      await go.click();
      await expect(page.locator('#scan-next')).toBeHidden();
      await expect(page.locator('#start-camera')).toHaveClass(/mk-action-button/);
    }
  }
});
