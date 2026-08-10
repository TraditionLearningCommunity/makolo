import { test, expect } from '../fixtures/makolo.mjs';
import { E2E_PASSWORD, login } from '../helpers/auth.mjs';
import { clearE2eEmails, passwordResetLinkFor } from '../helpers/email.mjs';


test('registration shows validation and creates a usable account', async ({ page }) => {
  await page.goto('/account/register/');
  await page.getByLabel('Adresse e-mail').fill('signup.user@e2e.makolo.test');
  await page.getByLabel('Identifiant').fill('signup-e2e');
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByLabel('Confirmer le mot de passe').fill('Different-E2E-2026!');
  await page.getByRole('button', { name: 'Créer mon compte' }).click();
  await expect(page.getByText(/mots de passe/i)).toBeVisible();

  await page.getByLabel('Confirmer le mot de passe').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Créer mon compte' }).click();
  await expect(page).toHaveURL('/login/');
  await expect(page.getByText(/Compte créé/i)).toBeVisible();

  await page.getByLabel('Adresse e-mail').fill('signup.user@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/dashboard/');
});


test('login rejects a bad password and preserves next on success', async ({ page }) => {
  await page.goto('/tickets/');
  await page.getByLabel('Adresse e-mail').fill('participant@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill('wrong-password');
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page.getByText(/Identifiants incorrects/i)).toBeVisible();

  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/tickets/');
  await expect(page.getByRole('heading', { name: /Mes billets|Billetterie/i })).toBeVisible();
});


test('forgot password follows the real generated email link and token is one-use', async ({ page }) => {
  await clearE2eEmails();
  await page.goto('/account/password/forgot/');
  await page.getByLabel('Adresse e-mail').fill('reset.user@e2e.makolo.test');
  await page.getByRole('button', { name: /Envoyer|réinitialisation/i }).click();
  await expect(page.getByText(/si un compte/i)).toBeVisible();

  const resetLink = await passwordResetLinkFor('reset.user@e2e.makolo.test');
  await page.goto(resetLink);
  const newPassword = 'Makolo-New-E2E-2026!';
  await page.getByLabel('Nouveau mot de passe').fill(newPassword);
  await page.getByLabel('Confirmer le nouveau mot de passe').fill(newPassword);
  await page.getByRole('button', { name: /Réinitialiser|Enregistrer/i }).click();
  await expect(page).toHaveURL('/login/');

  await page.getByLabel('Adresse e-mail').fill('reset.user@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(newPassword);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/dashboard/');

  await page.goto(resetLink);
  await page.locator('[name="new_password"]').fill('Another-Makolo-E2E-2026!');
  await page.locator('[name="new_password_confirm"]').fill('Another-Makolo-E2E-2026!');
  await page.getByRole('button').filter({ hasText: /Réinitialiser|Enregistrer/ }).click();
  await expect(page.getByText(/invalide|expiré|utilisé/i)).toBeVisible();
});


test('profile edits persist after reload', async ({ page }) => {
  await login(page, 'profile.user@e2e.makolo.test');
  await page.goto('/account/profile/');
  await page.getByLabel('Prénom').fill('Grace');
  await page.getByLabel('Nom').fill('Makolo');
  await page.getByLabel('Ville').fill('Lubumbashi');
  await page.getByLabel('Profession').fill('Ingénieure événementielle');
  await page.getByLabel('Présentation').fill('Profil modifié par le parcours Playwright.');
  await page.getByRole('button', { name: /Enregistrer mon profil/i }).click();
  await expect(page.getByText(/Profil mis à jour/i)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Prénom')).toHaveValue('Grace');
  await expect(page.getByLabel('Ville')).toHaveValue('Lubumbashi');
  await expect(page.getByLabel('Profession')).toHaveValue('Ingénieure événementielle');
  await expect(page.getByLabel('Présentation')).toHaveValue('Profil modifié par le parcours Playwright.');
  await expect(page.getByLabel('SMS')).toBeVisible();
  await expect(page.getByLabel('Notifications push')).toBeVisible();
});


test('password change works through the real form', async ({ page }) => {
  await login(page, 'password.user@e2e.makolo.test');
  await page.goto('/account/password/');
  await page.locator('[name="old_password"]').fill(E2E_PASSWORD);
  await page.locator('[name="new_password1"]').fill('Makolo-Changed-E2E-2026!');
  await page.locator('[name="new_password2"]').fill('Makolo-Changed-E2E-2026!');
  await page.getByRole('button').filter({ hasText: /Modifier|Changer|Enregistrer/ }).click();
  await expect(page).toHaveURL('/account/profile/');
  await expect(page.getByText(/Mot de passe modifié/i)).toBeVisible();
});


test('deletion anonymizes a participant but blocks the sole organization owner', async ({ page }) => {
  await login(page, 'delete.me@e2e.makolo.test');
  await page.goto('/account/delete/');
  await page.getByLabel('Mot de passe actuel').fill(E2E_PASSWORD);
  await page.getByLabel(/Je comprends/i).check();
  await page.getByRole('button', { name: /Supprimer|Désactiver/i }).click();
  await expect(page).toHaveURL('/');
  await expect(page.getByText(/désactivé et anonymisé/i)).toBeVisible();

  await login(page, 'sole.owner@e2e.makolo.test');
  await page.goto('/account/delete/');
  await expect(page.getByText(/dernier propriétaire/i)).toBeVisible();
  await page.getByLabel('Mot de passe actuel').fill(E2E_PASSWORD);
  await page.getByLabel(/Je comprends/i).check();
  await page.getByRole('button', { name: /Supprimer|Désactiver/i }).click();
  await expect(page.getByText(/propriétaire|transfert/i)).toBeVisible();
  await expect(page).toHaveURL('/account/delete/');
});
