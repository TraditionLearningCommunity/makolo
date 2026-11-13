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

function visibleJourneysSection(page) {
  // The icon-only views do not repeat a presentation heading.
  return page.locator('[data-dossier-content]');
}

async function linkJourney(page, name) {
  await page.locator('[data-dialog-open="dossier-link"]').click();
  await page.locator('#dossier-link select[name="journey"]').selectOption({
    label: name,
  });
  await page.locator('#dossier-link button[type="submit"]').click();
}

test('one Objectives organizer shares its icon views and filters across actor scopes', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  for (const route of [
    '/objectives/',
    '/objectives/?context=space&space=makolo-e2e-events',
  ]) {
    await page.goto(route);
    await expect(page.getByRole('heading', { name: 'Mes démarches' })).toBeVisible();
    await expect(page.locator('[data-filter-relation]')).toHaveCount(0);
    await expect(page.locator('[data-filter-placement]')).toHaveCount(1);
    await expect(page.getByRole('note', { name: /Espace actif/i })).toHaveCount(0);
    for (const mode of ['cards', 'list', 'explorer']) {
      const button = page.locator('[data-view="' + mode + '"]');
      await expect(button).toHaveAttribute('aria-label', /\S/);
      await expect(button).toHaveText('');
    }
    await expectNoHorizontalOverflow(page);
  }
});

test('visitor cannot open private Objectives surfaces', async ({ page }) => {
  await page.goto('/objectives/');
  await expect(page).toHaveURL(/\/login\/\?next=/);

  await page.goto('/objectives/projects/');
  await expect(page).toHaveURL(/\/login\/\?next=/);
});

test('participant can compose a Dossier, dependencies and a Project', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/objectives/');

  await expect(page.getByRole('heading', { name: 'Mes démarches' })).toBeVisible();
  await page.getByRole('link', { name: /Créer un dossier/i }).click();

  await page.locator('input[name="title"]').fill('Préparer le départ D6 bis');
  await page.locator('textarea[name="description"]').fill('Smoke test produit du train Objectives.');
  await page.getByRole('button', { name: /Créer le dossier/i }).click();
  await expect(page.getByRole('heading', { name: 'Préparer le départ D6 bis' })).toBeVisible();
  const dossierUrl = page.url();

  await linkJourney(page, 'Accompagnement Services V1 E2E');
  await expect(visibleJourneysSection(page).getByText('Accompagnement Services V1 E2E', { exact: true })).toBeVisible();

  await linkJourney(page, 'Inscription communautaire E2E');
  await expect(visibleJourneysSection(page).getByText('Inscription communautaire E2E', { exact: true })).toBeVisible();

  await page.locator('[data-dialog-open="dossier-dependency"]').click();
  await page.locator('#dossier-dependency select[name="dependent_link"]')
    .selectOption({ label: 'Accompagnement Services V1 E2E' });
  await page.locator('#dossier-dependency select[name="required_link"]')
    .selectOption({ label: 'Inscription communautaire E2E' });
  await page.locator('#dossier-dependency button[type="submit"]').click();
  await page.locator('[data-dossier-view="dependencies"]').click();
  await expect(page.locator('.mk-dossier__dep-list')).toContainText('Inscription communautaire E2E');
  await expect(page.locator('.mk-dossier__dep-list')).toContainText('Accompagnement Services V1 E2E');
  await expect(page.locator('.mk-dossier__dep-list')).toContainText('est requis avant');

  await page.locator('[data-dialog-open="dossier-link"]').click();
  const nativeJourneySelect = page.locator('#dossier-link select[name="journey"]');
  await nativeJourneySelect.focus();
  await expect(nativeJourneySelect).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dossier-link button[type="submit"]')).toBeFocused();
  await page.locator('#dossier-link [data-dialog-close]').click();
  await expectNoSeriousAxeViolations(page);

  await page.goto('/objectives/projects/new/');
  await page.locator('input[name="title"]').fill('Projet D6 bis E2E');
  await page.locator('textarea[name="description"]').fill('Horizon durable du smoke Objectives.');
  await page.getByRole('button', { name: /Créer le projet/i }).click();
  await expect(page.getByRole('heading', { name: 'Projet D6 bis E2E' })).toBeVisible();
  await expect(page.locator('.mk-project__title-row .mk-project__exchange'))
    .toHaveAttribute('aria-label', 'Échanger autour du Projet');
  await expect(page.locator('.mk-project__view-toolbar .mk-project__create-icon'))
    .toHaveAttribute('aria-label', 'Créer un dossier');
  await expect(page.locator('.mk-project__commands')).toHaveCount(0);
  await expect(page.locator('.mk-project__description'))
    .toContainText('Horizon durable du smoke Objectives.');
  await expect(page.locator('[data-project-top-menu] > summary'))
    .toHaveAttribute('aria-label', 'Actions du Projet');

  await page.locator('[data-project-top-menu] > summary').click();
  await page.locator('[data-project-top-menu] [data-dialog-open="project-link"]').click();
  await page.locator('#project-link select[name="dossier"]')
    .selectOption({ label: 'Préparer le départ D6 bis' });
  await page.locator('#project-link button[type="submit"]').click();
  await expect(page.getByText('Préparer le départ D6 bis', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Détacher Préparer le départ D6 bis' }).click();
  await page.locator('dialog.mk-project__dialog button').filter({ hasText: 'Détacher' }).click();
  await expect(page.getByText('Aucun Dossier visible.')).toBeVisible();

  await page.goto(dossierUrl);
  await expect(page.getByRole('heading', { name: 'Préparer le départ D6 bis' })).toBeVisible();
});

test('authorized Space owner can create Space Dossier and Project', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  await page.goto('/objectives/new/?context=space&space=makolo-e2e-events');
  await page.locator('input[name="title"]').fill('Dossier Espace D6 bis');
  await expect(page.getByLabel('Espace porteur')).toHaveCount(0);
  await page.getByRole('button', { name: /Créer le dossier/i }).click();
  await expect(page.getByRole('heading', { name: 'Dossier Espace D6 bis' })).toBeVisible();

  await page.goto('/objectives/projects/new/?context=space&space=makolo-e2e-events');
  await page.locator('input[name="title"]').fill('Projet Espace D6 bis');
  await expect(page.getByLabel('Espace porteur')).toHaveCount(0);
  await page.getByRole('button', { name: /Créer le projet/i }).click();
  await expect(page.getByRole('heading', { name: 'Projet Espace D6 bis' })).toBeVisible();
  await expect(page.locator('.mk-project__title-row .mk-project__exchange')).toBeVisible();
  await expect(page.locator('.mk-project__view-toolbar .mk-project__create-icon')).toBeVisible();
  await expect(page.locator('.mk-project__commands')).toHaveCount(0);

  await page.locator('[data-project-top-menu] > summary').click();
  await page.locator('[data-project-top-menu] [data-dialog-open="project-link"]').click();
  await page.locator('#project-link select[name="dossier"]')
    .selectOption({ label: 'Dossier Espace D6 bis' });
  await page.locator('#project-link button[type="submit"]').click();
  await expect(page.getByText('Dossier Espace D6 bis', { exact: true })).toBeVisible();
});

test('membership alone is not Dossier authority and Dossier access does not reveal a private Journey', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/objectives/new/?context=space&space=makolo-e2e-services');
  await page.locator('input[name="title"]').fill('Dossier confidentiel D6 bis');
  await expect(page.getByLabel('Espace porteur')).toHaveCount(0);
  await page.getByRole('button', { name: /Créer le dossier/i }).click();
  const dossierUrl = page.url();

  await linkJourney(page, 'Accompagnement Services V1 E2E');
  await expect(visibleJourneysSection(page).getByText('Accompagnement Services V1 E2E', { exact: true })).toBeVisible();

  await page.context().clearCookies();
  await login(page, 'service.same-space@e2e.makolo.test');
  let response = await page.goto(dossierUrl);
  expect(response?.status()).toBe(404);

  await page.context().clearCookies();
  await login(page, 'staff@e2e.makolo.test');
  await page.goto(dossierUrl);
  await page.locator('[data-dialog-open="dossier-authority"]').click();
  const collaborator = page.locator('#dossier-authority select[name="profile"]');
  await collaborator.selectOption({ label: 'Service Same-Space' });
  await selectFirstRealOption(page.locator('#dossier-authority select[name="role"]'));
  await page.locator('#dossier-authority button[type="submit"]').click();

  await page.context().clearCookies();
  await login(page, 'service.same-space@e2e.makolo.test');
  response = await page.goto(dossierUrl);
  expect(response?.status()).toBe(200);
  await expect(page.getByRole('heading', { name: 'Dossier confidentiel D6 bis' })).toBeVisible();
  await expect(visibleJourneysSection(page).getByText('Accompagnement Services V1 E2E', { exact: true })).toHaveCount(0);
  await expect(visibleJourneysSection(page).getByText('Aucune démarche visible.')).toBeVisible();
  await expectNoSeriousAxeViolations(page);
});

test('@mobile Objectives Dossier and Project surfaces remain touch-usable without horizontal overflow', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/objectives/');
  await expect(page.getByRole('heading', { name: 'Mes démarches' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);
  await expectNoSeriousAxeViolations(page);

  await page.getByRole('link', { name: /Créer un dossier/i }).click();
  await expectNoHorizontalOverflow(page);
  await page.locator('input[name="title"]').fill('Dossier mobile D6 bis');
  await page.getByRole('button', { name: /Créer le dossier/i }).click();
  await expect(page.getByRole('heading', { name: 'Dossier mobile D6 bis' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);

  await page.goto('/objectives/projects/');
  await expect(page.getByRole('heading', { name: 'Projets' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectTouchTargets(page);
  await expectNoSeriousAxeViolations(page);
});
