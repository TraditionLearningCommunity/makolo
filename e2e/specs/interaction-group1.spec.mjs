import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const primary = [
  { path: '/me/', surface: 'now' },
  { path: '/discover/', surface: 'discover' },
  { path: '/me/ongoing/', surface: 'ongoing' },
  { path: '/me/moi/', surface: 'me' },
  { path: '/mark/', surface: 'mark' },
];

test('Group 1: every principal Web surface shares a single interaction stylesheet', async ({ page }) => {
  test.setTimeout(90_000);
  await login(page, 'participant@e2e.makolo.test');
  for (const item of primary) {
    await page.goto(item.path);
    await expect(page.locator('link[href*="makolo-interactions.css"]')).toHaveCount(1);
    await expect(page.locator('script[src*="makolo-interactions-f2.js"]')).toHaveCount(1);
    if (item.surface === 'discover') {
      await expect(page.locator('.mk-discovery-workspace')).toBeVisible();
    } else {
      await expect(page.locator('[data-mk-surface="' + item.surface + '"]')).toBeVisible();
    }
  }
});

test('Group 1: Discover uses shared action skins but preserves owner-backed GET search', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/discover/');
  const search = page.locator('#discovery-search-form');
  await expect(search).toHaveAttribute('method', 'get');
  const action = search.getByRole('button', { name: 'Découvrir' });
  await expect(action).toHaveClass(/mk-action-button/);
  await expect(action).toHaveAttribute('data-variant', 'primary');
  const presentation = await action.evaluate((button) => ({
    minHeight: parseFloat(getComputedStyle(button).minHeight),
    background: getComputedStyle(button).backgroundColor,
  }));
  expect(presentation.minHeight).toBeGreaterThanOrEqual(44);
  expect(presentation.background).not.toBe('rgba(0, 0, 0, 0)');
  await expect(page.locator('.mk-discovery-workspace[data-mk-query-local="true"]')).toHaveCount(0);
});

test('Group 1: Now and Ongoing retain owner actions with shared presentation', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');
  const nowLegacy = page.locator('[data-mk-surface="now"] .mk-now-cta:not(.mk-action-button)');
  await expect(nowLegacy).toHaveCount(0);
  const directActions = page.locator('[data-mk-surface="now"] form[data-now-direct]');
  expect(await directActions.evaluateAll((forms) => forms.every(
    (form) => form.method.toLowerCase() === 'post' &&
      Boolean(form.querySelector('input[name="csrfmiddlewaretoken"]'))
  ))).toBe(true);
  await page.goto('/me/ongoing/');
  const ongoingLegacy = page.locator('[data-mk-surface="ongoing"] .mk-ongoing-unit__primary:not(.mk-action-button)');
  await expect(ongoingLegacy).toHaveCount(0);
  await expect(page.locator('[data-mk-surface="ongoing"]')).toBeVisible();
});

test('Group 1: Moi and Mark use canonical text/primary action components', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/moi/');
  await expect(page.locator('head link[href*="me-n1.css"]')).toHaveCount(1);
  await expect(page.locator('main link[href*="me-n1.css"]')).toHaveCount(0);
  const passport = page.getByRole('link', { name: /Modifier mon passeport/ });
  await expect(passport).toHaveClass(/mk-action-button/);
  await expect(passport).toHaveAttribute('data-variant', 'link');
  await page.goto('/mark/');
  const continueButton = page.getByRole('button', { name: 'Continuer' });
  await expect(continueButton).toHaveClass(/mk-action-button/);
  await expect(continueButton).toHaveAttribute('data-variant', 'primary');
  await expect(continueButton.locator('..')).toHaveAttribute('method', 'post');
});

test('Group 1: mobile Web keeps action targets accessible @mobile', async ({ page }) => {
  test.setTimeout(60_000);
  await login(page, 'participant@e2e.makolo.test');
  for (const [path,role,accessible] of [
    ['/discover/', 'button', 'Découvrir'],
    ['/me/moi/', 'link', /Modifier mon passeport/],
    ['/mark/', 'button', 'Continuer'],
  ]) {
    await page.goto(path);
    const action = page.getByRole(role, { name: accessible }).first();
    await expect(action).toBeVisible();
    const dimensions = await action.evaluate((node) => {
      const box = node.getBoundingClientRect();
      return { height: box.height, width: box.width };
    });
    expect(dimensions.height).toBeGreaterThanOrEqual(44);
    expect(dimensions.width).toBeGreaterThanOrEqual(44);
  }
});

test('Group 1: public Discover receives the same shared control CSS and behavior', async ({ page }) => {
  await page.goto('/discover/');
  await expect(page.locator('link[href*="makolo-interactions.css"]')).toHaveCount(1);
  await expect(page.locator('script[src*="makolo-interactions.js"]')).toHaveCount(1);
  await expect(page.locator('script[src*="makolo-interactions-f2.js"]')).toHaveCount(1);
  const search = page.locator('#discovery-search-form');
  await expect(search).toHaveAttribute('method', 'get');
  const action = search.getByRole('button', { name: 'Découvrir' });
  await expect(action).toHaveAttribute('data-variant', 'primary');
  await expect(action).toHaveClass(/mk-action-button/);
  const minimum = await action.evaluate((node) => parseFloat(getComputedStyle(node).minHeight));
  expect(minimum).toBeGreaterThanOrEqual(44);
});
