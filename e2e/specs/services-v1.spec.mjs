import { expect, test } from '@playwright/test';
import { login } from '../helpers/auth.mjs';

const JOURNEY_ID = '2ba34e06-cf8d-4e66-8a55-f7271bac6cf0';
const ACTIVITY_ID = '693d18fe-e954-4bcb-836f-cdfffa64d361';

async function expectNoHorizontalOverflow(page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
}

test('participant can use the seeded Services V1 workspace', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto(`/me/journeys/${JOURNEY_ID}/`);

  await expect(page.getByText('Accompagnement Services V1 E2E')).toBeVisible();
  await expect(page.getByText('Document complémentaire requis')).toBeVisible();
  await expect(page.getByText('Fournir le document demandé')).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test('manager and facilitator stay inside their canonical Services case scopes', async ({ page }) => {
  await login(page, 'service.manager@e2e.makolo.test');
  await page.goto(`/services/operator/journeys/${JOURNEY_ID}/`);
  await expect(page.getByText('Accompagnement Services V1 E2E')).toBeVisible();
  await expect(page.getByText('Document complémentaire requis')).toBeVisible();
  await expect(page.getByText('Document restreint Services E2E')).toHaveCount(0);

  await page.context().clearCookies();
  await login(page, 'service.facilitator@e2e.makolo.test');
  await page.goto(`/services/operator/journeys/${JOURNEY_ID}/`);
  await expect(page.getByText('Accompagnement Services V1 E2E')).toBeVisible();
  await expect(page.getByText('Document complémentaire requis')).toBeVisible();
  await expect(page.getByText('Document restreint Services E2E')).toHaveCount(0);
});

test('reviewer sees only the assigned restricted review', async ({ page }) => {
  await login(page, 'service.reviewer@e2e.makolo.test');
  await page.goto('/services/operator/reviews/');

  await expect(page.getByRole('heading', { name: 'Documents à revoir' })).toBeVisible();
  await expect(page.getByText('Document restreint Services E2E')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Document' })).toBeVisible();
});

test('same-Space membership without Services authority cannot open the case', async ({ page }) => {
  await login(page, 'service.same-space@e2e.makolo.test');
  const response = await page.goto(`/services/operator/journeys/${JOURNEY_ID}/`);
  expect(response?.status()).toBe(404);
});

test('platform staff can read Services analytics with separate fulfillment and external outcome metrics', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto(`/analytics/services/activities/${ACTIVITY_ID}/`);

  await expect(page.getByRole('heading', { name: 'Accompagnement Services V1 E2E' })).toBeVisible();
  await expect(page.getByText('Accomplissement Makolo')).toBeVisible();
  await expect(page.getByText('Succès externe')).toBeVisible();
  await expect(page.getByText('Overdue actuel')).toBeVisible();
});

test('@mobile participant Services workspace has no critical horizontal overflow', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto(`/me/journeys/${JOURNEY_ID}/`);
  await expect(page.getByText('Accompagnement Services V1 E2E')).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
