import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';


test('groups cover community membership, invitation security and scoped administration', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');

  await page.goto('/groups/new/');
  await page.getByLabel('Nom').fill('Groupe E2E A');
  await page.getByLabel('Description').fill('Population E2E créée depuis le navigateur.');
  await page.getByRole('button', { name: 'Créer le Groupe' }).click();
  await expect(page.getByRole('heading', { name: 'Groupe E2E A', exact: true })).toBeVisible();
  await expect(page.getByText('Uniquement les personnes autorisées', { exact: true })).toBeVisible();
  await expect(page.getByText('Sur invitation', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Administrer' }).click();
  await page.getByRole('link', { name: 'Importer CSV' }).click();
  await page.locator('input[name="csv_file"]').setInputFiles({
    name: 'groupe-e2e.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(
      'email,external_reference,first_name,last_name\n' +
      'participant@e2e.makolo.test,E2E-001,Participant,E2E\n' +
      'personne.absente@e2e.makolo.test,E2E-002,Absente,E2E\n',
      'utf8',
    ),
  });
  await page.getByRole('button', { name: 'Analyser et importer' }).click();
  const importResult = page.locator('#group-import-result');
  await expect(importResult).toBeVisible();
  await expect(importResult.getByText('1', { exact: true }).first()).toBeVisible();
  await expect(importResult.getByText('membres ajoutés', { exact: true })).toBeVisible();
  await expect(importResult.getByText('invitations créées', { exact: true })).toBeVisible();

  await page.getByRole('link', { name: 'Membres' }).click();
  await expect(page.getByText('participant@e2e.makolo.test')).toBeVisible();
  await expect(page.getByText('personne.absente@e2e.makolo.test')).toBeVisible();

  await page.getByRole('link', { name: 'Inviter' }).click();
  await page.getByLabel('E-mail').fill('profile.user@e2e.makolo.test');
  await page.getByRole('button', { name: 'Créer l’invitation' }).click();
  const invitationHref = await page.locator('#group-invitation-link').getAttribute('href');
  expect(invitationHref).toMatch(/^\/groups\/invitations\//);

  await page.goto('/groups/new/');
  await page.getByLabel('Nom').fill('Groupe E2E B');
  await page.getByRole('button', { name: 'Créer le Groupe' }).click();
  await expect(page.getByRole('heading', { name: 'Groupe E2E B', exact: true })).toBeVisible();

  await page.goto('/groups/new/');
  await page.getByLabel('Nom').fill('Anciens MAPENDO E2E');
  await page.getByLabel('Description').fill('Groupe trouvable avec adhésion sur demande.');
  await page.getByLabel('Qui peut trouver ce Groupe ?').selectOption('listed');
  await page.getByLabel('Qui peut rejoindre ?').selectOption('request');
  await page.getByRole('button', { name: 'Créer le Groupe' }).click();
  await expect(page.getByRole('heading', { name: 'Anciens MAPENDO E2E', exact: true })).toBeVisible();
  await expect(page.getByText('Trouvable dans Makolo', { exact: true })).toBeVisible();
  await expect(page.getByText('Sur demande', { exact: true })).toBeVisible();

  await logout(page);
  await login(page, 'participant@e2e.makolo.test');

  await page.goto('/groups/explore/?q=MAPENDO');
  await expect(page.getByRole('link', { name: /Anciens MAPENDO E2E/ })).toBeVisible();
  await page.getByRole('link', { name: /Anciens MAPENDO E2E/ }).click();
  await expect(page.getByRole('heading', { name: 'Anciens MAPENDO E2E', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Demander à rejoindre' }).click();
  await expect(page.getByText('Demande envoyée.', { exact: true })).toBeVisible();
  await expect(page.getByText('Demande en attente', { exact: true })).toBeVisible();

  const hidden = await page.goto('/groups/groupe-e2e-b/');
  expect(hidden.status()).toBe(404);

  await page.goto('/groups/groupe-e2e-a/');
  await expect(page.getByRole('heading', { name: 'Groupe E2E A', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Administrer' })).toHaveCount(0);
  let forbidden = await page.goto('/groups/groupe-e2e-a/members/');
  expect(forbidden.status()).toBe(403);

  await logout(page);
  await login(page, 'owner@e2e.makolo.test');

  await page.goto('/groups/anciens-mapendo-e2e/members/');
  await expect(page.getByText('e2e-participant', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Approuver' }).click();
  await expect(page.getByText(/membre est maintenant actif/i)).toBeVisible();

  await page.goto('/groups/groupe-e2e-a/members/');
  await page.getByRole('link', { name: 'Déléguer' }).click();
  await page.getByLabel('Profil').fill('participant@e2e.makolo.test');
  await page.getByLabel('Responsabilité').selectOption('group-admin');
  await page.getByRole('button', { name: 'Accorder le Mandat' }).click();
  await expect(page.getByText(/Responsabilité Groupe mise à jour/i)).toBeVisible();

  await logout(page);
  await login(page, 'participant@e2e.makolo.test');
  await page.goto('/groups/anciens-mapendo-e2e/');
  await expect(page.getByText('Membre', { exact: true })).toBeVisible();

  await page.goto('/groups/groupe-e2e-a/');
  await expect(page.getByRole('link', { name: 'Administrer' })).toBeVisible();
  forbidden = await page.goto('/groups/groupe-e2e-b/members/');
  expect(forbidden.status()).toBe(403);

  await logout(page);
  await login(page, 'profile.user@e2e.makolo.test');
  await page.goto(invitationHref);
  await expect(page.getByText(/correspond à l’identité prévue/i)).toBeVisible();
  await page.getByRole('button', { name: 'Rejoindre le Groupe' }).click();
  await expect(page.getByRole('heading', { name: 'Groupe E2E A', exact: true })).toBeVisible();
  await expect(page.getByText(/Invitation acceptée/i)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Administrer' })).toHaveCount(0);
});
