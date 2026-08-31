import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

const SPACE_SLUG = 'makolo-e2e-events';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}


test('Profile can inspect Subscription, preview without mutation and request an eligible transition', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/subscription/');

  await expect(page.getByRole('heading', { name: 'Mon abonnement' })).toBeVisible();
  await expect(page.getByText('Makolo Base — Profil')).toBeVisible();
  const target = page.locator('article').filter({ hasText: 'Makolo E2E Profil Plus' });
  await expect(target).toBeVisible();
  await target.getByRole('link', { name: 'Voir ce qui changerait' }).click();

  await expect(page.getByRole('heading', { name: 'Ce qui changerait' })).toBeVisible();
  await expect(page.getByText('Cet aperçu ne modifie pas l’abonnement')).toBeVisible();
  await page.getByRole('button', { name: 'Confirmer le changement' }).click();

  await page.waitForURL('/subscription/');
  await expect(page.getByText('Makolo E2E Profil Plus').first()).toBeVisible();
  await expect(page.getByText(/1 \/ 2 conditions remplies/)).toBeVisible();
  await expect(page.getByText('Confirmer votre choix')).toBeVisible();
});


test('Space owner sees canonical usage and can request a Space plan change', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto(`/spaces/${SPACE_SLUG}/subscription/`);

  await expect(page.getByRole('heading', { name: 'Abonnement de l’Espace' })).toBeVisible();
  await expect(page.getByText('Espace · Makolo E2E Events')).toBeVisible();
  const target = page.locator('article').filter({ hasText: 'Makolo E2E Espace Plus' });
  await expect(target).toBeVisible();
  await target.getByRole('link', { name: 'Voir ce qui changerait' }).click();
  await expect(page.getByRole('heading', { name: 'Ce qui changerait' })).toBeVisible();
  await page.getByRole('button', { name: 'Confirmer le changement' }).click();

  await page.waitForURL(`/spaces/${SPACE_SLUG}/subscription/`);
  await expect(page.getByText('Makolo E2E Espace Plus').first()).toBeVisible();
  await expect(page.getByText(/Prête|En cours/).first()).toBeVisible();
});


test('Space viewer can inspect and preview but never receives mutation controls', async ({ page }) => {
  await login(page, 'subscription.viewer@e2e.makolo.test');
  await page.goto(`/spaces/${SPACE_SLUG}/subscription/`);

  await expect(page.getByRole('heading', { name: 'Abonnement de l’Espace' })).toBeVisible();
  const target = page.locator('article').filter({ hasText: 'Makolo E2E Espace Plus' });
  await expect(target).toBeVisible();
  await target.getByRole('link', { name: 'Voir ce qui changerait' }).click();
  await expect(page.getByRole('heading', { name: 'Ce qui changerait' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmer le changement' })).toHaveCount(0);
  await expect(page.getByText('Vous pouvez consulter cet aperçu')).toBeVisible();
});


test('TeamMembership alone does not open the Space Subscription console', async ({ page }) => {
  await login(page, 'subscription.member@e2e.makolo.test');
  const response = await page.goto(`/spaces/${SPACE_SLUG}/subscription/`);
  expect(response?.status()).toBe(403);
});


test('Platform Mandate can create a private Staff Plan draft and publish through the business service UI', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/operations/subscriptions/catalog/');

  await expect(page.getByRole('heading', { name: 'Plans' })).toBeVisible();
  const code = `e2e.staff.${Date.now()}`;
  const createPlan = page.getByRole('heading', { name: 'Créer un Plan' }).locator('..');
  await createPlan.locator('input[name="code"]').fill(code);
  await createPlan.locator('select[name="plan_type"]').selectOption('base');
  await createPlan.locator('select[name="subject_type"]').selectOption('profile');
  await createPlan.locator('input[name="is_active"]').check();
  await createPlan.getByRole('button', { name: 'Créer le Plan' }).click();

  await expect(page.getByRole('heading', { name: code })).toBeVisible();
  const draftForm = page.getByRole('heading', { name: 'Nouvelle version draft' }).locator('..');
  await draftForm.locator('input[name="name"]').fill('Plan interne E2E Staff');
  await draftForm.locator('input[name="short_description"]').fill('Plan navigateur réservé à la release gate.');
  await draftForm.locator('select[name="catalog_visibility"]').selectOption('internal');
  await draftForm.locator('select[name="acquisition_mode"]').selectOption('staff_only');
  await draftForm.locator('input[name="display_order"]').fill('90');
  await draftForm.getByRole('button', { name: 'Créer le draft' }).click();

  await expect(page.getByRole('heading', { name: 'Plan interne E2E Staff' })).toBeVisible();
  await expect(page.getByText('draft').first()).toBeVisible();
  await page.getByRole('button', { name: 'Publier via le service' }).click();
  await expect(page.getByText('published').first()).toBeVisible();
  await expect(page.getByText('Cette version est historique et consultable')).toBeVisible();
});


test('Subscription Profile and Space surfaces stay usable at phone width @mobile', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/subscription/');
  await expect(page.getByRole('heading', { name: 'Mon abonnement' })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.context().clearCookies();
  await login(page, 'owner@e2e.makolo.test');
  await page.goto(`/spaces/${SPACE_SLUG}/subscription/`);
  await expect(page.getByRole('heading', { name: 'Abonnement de l’Espace' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
