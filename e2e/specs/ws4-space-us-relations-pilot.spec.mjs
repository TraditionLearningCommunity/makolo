import { expect, test } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE = '/spaces/makolo-e2e-events/';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test('WS4 Nous stays human and responsive across Makolo regimes @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  for (const viewport of [
    { width: 400, height: 844 },
    { width: 800, height: 1024 },
    { width: 1199, height: 900 },
    { width: 1200, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto(`${SPACE}us/`);
    await expect(
      page.getByRole('heading', {
        name: /Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés/,
      }),
    ).toBeVisible();
    await expect(page.getByText('Personnes & relations', { exact: true })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});

test('WS4 secondary surfaces keep routes, back-forward and relation semantics coherent', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${SPACE}us/`);

  await page.getByRole('link', { name: /Personnes & relations/ }).click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/relationships\/$/);
  await expect(page.getByRole('heading', { name: 'Avec qui avançons-nous ?' })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goBack();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/us\/$/);

  const pilot = page.getByRole('link', { name: /Piloter/ });
  await expect(pilot).toBeVisible();
  await pilot.click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/pilot\/$/);
  await expect(
    page.getByRole('heading', {
      name: /Est-ce que cela fonctionne .* Qu’est-ce qui change .* Que devons-nous ajuster/,
    }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
