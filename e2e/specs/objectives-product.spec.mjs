import { expect, test } from '../fixtures/makolo.mjs';
import { expectNoSeriousAxeViolations } from '../helpers/accessibility.mjs';
import { login } from '../helpers/auth.mjs';

async function expectNoHorizontalOverflow(page) {
  const widths = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
}

async function expectTouchTargets(page) {
  const undersized = await page.locator('.mk-btn:visible').evaluateAll((nodes) => nodes
    .map((node) => {
      const rect = node.getBoundingClientRect();
      return { text: node.textContent?.trim() || '', width: rect.width, height: rect.height };
    })
    .filter(({ width, height }) => width < 44 || height < 44));
  expect(undersized).toEqual([]);
}

async function selectFirstRealOption(select) {
  const value = await select.locator('option').evaluateAll((options) => {
    const option = options.find((candidate) => candidate.value);
    return option?.value || '';
  });
  expect(value).not.toBe('');
  await select.selectOption(value);
}

test('visitor cannot open private Objectives surfaces', async ({ page }) => {
  await page.goto('/objectives/');
  await expect(page).toHaveURL(/\/login\/\?next=/);

  await page.goto('/objectives/projects/');
  await expect(page).toHaveURL(/\/login\/\?next=/);
});

test('participant can compose a Dossier, dependencies and a Project', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/objectives/');

  await expect(page.getByRole('heading', { name: 'Mes Dossiers' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dossiers & Projets' })).toBeVisible();
  await page.getByRole('link', { name: 'Créer un Dossier' }).click();

  await page.getByLabel(/^Objectif\s*:$/).fill('Préparer le départ D6 bis');
  await page.getByLabel(/^Contexte\s*:$/).fill('Smoke test produit du train Objectives.');
  await page.getByRole('button', { name: 'Créer le Dossier' }).click();
  await expect(page.getByRole('heading', { name: 'Préparer le départ D6 bis' })).toBeVisible();
  const dossierUrl = page.url();

  const journeySelect = page.getByLabel(/^Démarche\s*:$/);
  await journeySelect.selectOption({ label: 'Accompagnement Services V1 E2E' });
  await page.getByRole('button', { name: 'Lier la démarche' }).click();
  await expect(page.getByText('Accompagnement Services V1 E2E', { exact: true })).toBeVisible();

  await page.getByLabel(/^Démarche\s*:$/).selectOption({ label: 'Inscription communautaire E2E' });
  await page.getByRole('button', { name: 'Lier la démarche' }).click();
  await expect(page.getByText('Inscription communautaire E2E', { exact: true })).toBeVisible();

  await page.getByLabel('Démarche dépendante').selectOption({ label: 'Accompagnement Services V1 E2E' });
  await page.getByLabel('Démarche requise').selectOption({ label: 'Inscription communautaire E2E' });
  await page.getByRole('button', { name: 'Ajouter la dépendance' }).click();
  await expect(page.getByText(/Accompagnement Services V1 E2E.*nécessite.*Inscription communautaire E2E/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Avancement' })).toBeVisible();

  const nativeJourneySelect = page.getByLabel(/^Démarche\s*:$/);
  await nativeJourneySelect.focus();
  await expect(nativeJourneySelect).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Lier la démarche' })).toBeFocused();
  await expectNoSeriousAxeViolations(page);

  await page.goto('/objectives/projects/new/');
  await page.getByLabel(/^Titre\s*:$/).fill('Projet D6 bis E2E');
  await page.getByLabel(/^Contexte\s*:$/).fill('Horizon durable du smoke Objectives.');
  await page.getByRole('button', { name: 'Créer le Projet' }).click();
  await expect(page.getByRole('heading', { name: 'Projet D6 bis E2E' })).toBeVisible();

  await page.getByLabel(/^Dossier\s*:$/).selectOption({ label: 'Préparer le départ D6 bis' });
  await page.getByRole('button', { name: 'Rattacher le Dossier' }).click();
  await expect(page.getByText('Préparer le départ D6 bis', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Retirer du Projet' }).click();
  await expect(page.getByText('Aucun Dossier visible dans ce Projet.')).toBeVisible();

  await page.goto(dossierUrl);
  await expect(page.getByRole('heading', { name: 'Préparer le départ D6 bis' })).toBeVisible();
});

test('authorized Space owner can create Space Dossier and Project', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  await page.goto('/objectives/new/');
  await page.getByLabel(/^Objectif\s*:$/).fill('Dossier Espace D6 bis');
  await page.getByLabel('Espace porteur').selectOption({ label: 'Makolo E2E Events' });
  await page.getByRole('button', { name: 'Créer le Dossier' }).click();
  await expect(page.getByRole('heading', { name: 'Dossier Espace D6 bis' })).toBeVisible();

  await page.goto('/objectives/projects/new/');
  await page.getByLabel(/^Titre\s*:$/).fill('Projet Espace D6 bis');
  await page.getByLabel('Espace porteur').selectOption({ label: 'Makolo E2E Events' });
  await page.getByRole('button', { name: 'Créer le Projet' }).click();
  await expect(page.getByRole('heading', { name: 'Projet Espace D6 bis' })).toBeVisible();

  await page.getByLabel(/^Dossier\s*:$/).selectOption({ label: 'Dossier Espace D6 bis' });
  await page.getByRole('button', { name: 'Rattacher le Dossier' }).click();
  await expect(page.getByText('Dossier Espace D6 bis', { exact: true })).toBeVisible();
});

test('membership alone is not Dossier authority and Dossier access does not reveal a private Journey', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/objectives/new/');
  await page.getByLabel(/^Objectif\s*:$/).fill('Dossier confidentiel D6 bis');
  await page.getByLabel('Espace porteur').selectOption({ label: 'Makolo E2E Services' });
  await page.getByRole('button', { name: 'Créer le Dossier' }).click();
  const dossierUrl = page.url();

  await page.getByLabel(/^Démarche\s*:$/).selectOption({ label: 'Accompagnement Services V1 E2E' });
  await page.getByRole('button', { name: 'Lier la démarche' }).click();
  await expect(page.getByText('Accompagnement Services V1 E2E', { exact: true })).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'service.same-space@e2e.makolo.test');
  let response = await page.goto(dossierUrl);
  expect(response?.status()).toBe(404);

  await page.context().clearCookies();
  await login(page, 'staff@e2e.makolo.test');
  await page.goto(dossierUrl);
  const collaborator = page.getByLabel(/^Collaborateur\s*:$/);
  await collaborator.selectOption({ label: 'Service Same-Space' });
  await selectFirstRealOption(page.getByLabel('Niveau d’accès'));
  await page.getByRole('button', { name: 'Accorder l’accès' }).click();

  await page.context().clearCookies();
  await login(page, 'service.same-space@e2e.makolo.test');
  response = await page.goto(dossierUrl);
  expect(response?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Dossier confidentiel D6 bis' })).toBeVisible();
  await expect(page.getByText('Accompagnement Services V1 E2E', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Aucune démarche visible liée.')).toBeVisible();
  await expectNoSeriousAxeViolations(page);
});

test('@mobile Objectives Dossier and Project surfaces remain touch-usable without horizontal overflow', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/objectives/');
  await expect(page.getByRole('heading', { name: 'Mes Dossiers' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);
  await expectNoSeriousAxeViolations(page);

  await page.getByRole('link', { name: 'Créer un Dossier' }).click();
  await expectNoHorizontalOverflow(page);
  await page.getByLabel(/^Objectif\s*:$/).fill('Dossier mobile D6 bis');
  await page.getByRole('button', { name: 'Créer le Dossier' }).click();
  await expect(page.getByRole('heading', { name: 'Dossier mobile D6 bis' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);

  await page.goto('/objectives/projects/');
  await expect(page.getByRole('heading', { name: 'Projets' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);
  await expectNoSeriousAxeViolations(page);
});
