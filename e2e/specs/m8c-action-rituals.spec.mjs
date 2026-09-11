import { expect, test } from '@playwright/test';
import { login } from '../helpers/auth.mjs';

const PARTICIPANT = 'm8c.participant@e2e.makolo.test';

async function openJourney(page, title) {
  await page.goto(`/me/journeys/?q=${encodeURIComponent(title)}`);
  const link = page.getByRole('link').filter({ hasText: title }).first();
  await expect(link).toBeVisible();
  await link.click();
}

test.describe('M8-C action rituals', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, PARTICIPANT);
  });

  test('preparation is immediately understandable', async ({ page }) => {
    await openJourney(page, 'M8-C préparation E2E');
    await expect(page.getByText('Est-ce que tout est prêt ?')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tout est prêt.' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Voir les informations pratiques' })).toBeVisible();
  });

  test('imminent occurrence hands off to real-world action', async ({ page }) => {
    await openJourney(page, 'M8-C départ E2E');
    await expect(page.getByText('Il est temps d’y aller')).toBeVisible();
    await page.getByRole('link', { name: 'Ouvrir l’action en cours' }).click();
    await expect(page.getByRole('heading', { name: 'Rejoignez Accueil principal.' })).toBeVisible();
    await expect(page.getByText('Maison de l’action E2E')).toBeVisible();
    await expect(page.getByText('Votre accès est prêt')).toBeVisible();
  });

  test('live occurrence makes the called queue action dominant', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await openJourney(page, 'M8-C action réelle E2E');
    await page.getByRole('link', { name: 'Ouvrir l’action en cours' }).click();
    await expect(page.getByText('Ce qui compte maintenant')).toBeVisible();
    await expect(page.getByRole('heading', { name: /C’est votre tour/ })).toBeVisible();
    await expect(page.getByText('Zone A · Place 7')).toBeVisible();
    await expect(page.getByText('Guichet live')).toBeVisible();
  });

  test('ended occurrence removes live movement instructions', async ({ page }) => {
    await openJourney(page, 'M8-C fin E2E');
    await page.getByRole('link', { name: 'Voir l’occurrence' }).click();
    await expect(page.getByText('Cette activité est terminée')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Cette occurrence est terminée.' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Sur place' })).toHaveCount(0);
  });
});