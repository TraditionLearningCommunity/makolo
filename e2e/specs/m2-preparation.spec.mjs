import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


test('M2 participant completes required form, updates readiness and sees authorized resource', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/me/');

  const nextAction = page.getByRole('link', { name: /Compléter.*Informations de préparation E2E/i }).first();
  await expect(nextAction).toBeVisible();
  await nextAction.click();

  await expect(page.getByRole('heading', { name: 'Informations de préparation E2E', exact: true })).toBeVisible();
  await page.getByLabel('Point de rendez-vous préféré').fill('Accueil principal');
  await page.getByRole('button', { name: 'Soumettre', exact: true }).click();
  await expect(page.getByText('Formulaire soumis.', { exact: true })).toBeVisible();
  await expect(page.getByText(/Cette réponse a été soumise/i)).toBeVisible();

  await page.getByRole('link', { name: /Retour à la démarche/i }).click();
  await expect(page.getByRole('heading', { name: 'Documents et instructions', exact: true })).toBeVisible();
  await expect(page.getByText('Guide de préparation E2E', { exact: true })).toBeVisible();
  await expect(page.getByText(/Présentez-vous dix minutes avant/i)).toBeVisible();

  await page.goto('/me/');
  await expect(page.getByRole('link', { name: /Compléter.*Informations de préparation E2E/i })).toHaveCount(0);
});


test('M2 operator creates draft, publishes and requests a form from the Activity console', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/activities/');
  await page.getByRole('link', { name: 'Réservation sur place E2E', exact: true }).first().click();
  await page.getByRole('link', { name: 'Questionnaires', exact: true }).click();

  await expect(page.getByText('Questionnaire opérateur E2E', { exact: true })).toBeVisible();
  const pageText = await page.locator('main').innerText();
  const journeyMatch = pageText.match(/Journey\s+([0-9a-f-]{36})/i);
  expect(journeyMatch).not.toBeNull();
  const journeyId = journeyMatch[1];

  await page.getByPlaceholder('clé-stable').fill('m2-browser-created');
  await page.getByPlaceholder('Titre').fill('Questionnaire navigateur E2E');
  await page.getByRole('button', { name: 'Créer', exact: true }).click();
  await expect(page.getByText('Formulaire créé avec une version brouillon.', { exact: true })).toBeVisible();

  let formSection = page.locator('section').filter({ hasText: 'Questionnaire navigateur E2E' }).first();
  await formSection.getByPlaceholder('clé question').fill('browser-answer');
  await formSection.getByPlaceholder('Libellé').fill('Réponse navigateur');
  await formSection.locator('[name="position"]').fill('1');
  await formSection.locator('[name="required"]').check();
  await formSection.getByRole('button', { name: 'Ajouter la question', exact: true }).click();
  await expect(page.getByText('Question ajoutée.', { exact: true })).toBeVisible();

  formSection = page.locator('section').filter({ hasText: 'Questionnaire navigateur E2E' }).first();
  await formSection.getByRole('button', { name: 'Publier la version', exact: true }).click();
  await expect(page.getByText('Version publiée.', { exact: true })).toBeVisible();

  formSection = page.locator('section').filter({ hasText: 'Questionnaire navigateur E2E' }).first();
  await formSection.getByPlaceholder('UUID Journey').fill(journeyId);
  await formSection.getByRole('button', { name: 'Demander', exact: true }).click();
  await expect(page.getByText('Formulaire demandé dans la Journey.', { exact: true })).toBeVisible();
  await expect(page.getByText('Questionnaire navigateur E2E', { exact: true })).toBeVisible();
});
