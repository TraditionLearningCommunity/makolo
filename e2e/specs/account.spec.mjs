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
  await expect(page.getByText('Les mots de passe ne correspondent pas.')).toBeVisible();

  // Password fields are intentionally cleared by Django after an invalid POST.
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByLabel('Confirmer le mot de passe').fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Créer mon compte' }).click();
  await expect(page).toHaveURL(/\/login\/\?email=signup\.user%40e2e\.makolo\.test$/);
  await expect(page.getByLabel('Adresse e-mail')).toHaveValue('signup.user@e2e.makolo.test');
  await expect(page.getByText(/Compte créé/i)).toBeVisible();

  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/me/');
  await expect(page.getByRole('heading', { name: /Que dois-je faire maintenant/i })).toBeVisible();
});


test('login rejects a bad password and preserves next on success', async ({ page }) => {
  await page.goto('/tickets/');
  await page.getByLabel('Adresse e-mail').fill('participant@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill('wrong-password');
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page.getByText(/Adresse e-mail ou mot de passe incorrect/i)).toBeVisible();

  // The login form does not echo credentials after failure; re-enter both fields.
  await page.getByLabel('Adresse e-mail').fill('participant@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(E2E_PASSWORD);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/tickets/');
  await expect(page.locator('#main-content')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mes accès', exact: true }).first()).toBeVisible();
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
  await page.getByLabel('Nouveau mot de passe', { exact: true }).fill(newPassword);
  await page.getByLabel('Confirmer le nouveau mot de passe', { exact: true }).fill(newPassword);
  await page.getByRole('button').filter({ hasText: /Réinitialiser|Enregistrer/ }).click();
  await expect(page).toHaveURL('/login/');

  await page.getByLabel('Adresse e-mail').fill('reset.user@e2e.makolo.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(newPassword);
  await page.getByRole('button', { name: 'Se connecter' }).click();
  await expect(page).toHaveURL('/me/');

  await page.goto(resetLink);
  await page.locator('[name="new_password"]').fill('Another-Makolo-E2E-2026!');
  await page.locator('[name="new_password_confirm"]').fill('Another-Makolo-E2E-2026!');
  await page.getByRole('button').filter({ hasText: /Réinitialiser|Enregistrer/ }).click();
  await expect(page.getByText('Le lien de réinitialisation est invalide ou expiré.')).toBeVisible();
});


test('profile edits and appearance persist after reload', async ({ page }) => {
  await login(page, 'profile.user@e2e.makolo.test');
  await page.goto('/account/profile/');
  await page.getByLabel('Prénom', { exact: true }).fill('Grace');
  await page.getByLabel('Nom', { exact: true }).fill('Makolo');
  await page.getByLabel('Ville', { exact: true }).fill('Lubumbashi');
  await page.getByLabel('Profession', { exact: true }).fill('Ingénieure événementielle');
  await page.getByLabel('Présentation', { exact: true }).fill('Profil modifié par le parcours Playwright.');
  await page.getByRole('button', { name: /Enregistrer mon profil/i }).click();
  await expect(page.getByText(/Profil mis à jour/i)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Prénom', { exact: true })).toHaveValue('Grace');
  await expect(page.getByLabel('Ville', { exact: true })).toHaveValue('Lubumbashi');
  await expect(page.getByLabel('Profession', { exact: true })).toHaveValue('Ingénieure événementielle');
  await expect(page.getByLabel('Présentation', { exact: true })).toHaveValue('Profil modifié par le parcours Playwright.');
  await expect(page.getByLabel('SMS', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Notifications push', { exact: true })).toHaveCount(0);
  await expect(page.getByText('E-mails', { exact: true })).toBeVisible();
  await expect(page.getByText('Sécurité du compte', { exact: true }).first()).toBeVisible();

  await page.getByLabel('Sombre', { exact: true }).check();
  await page.getByRole('button', { name: 'Enregistrer l’apparence' }).click();
  await expect(page.getByText('Apparence mise à jour.')).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Sombre', { exact: true })).toBeChecked();
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', 'dark');
  await expect(page.locator('html')).toHaveClass(/dark/);
});


test('theme bootstrap tolerates unavailable browser storage', async ({ page }) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    const blocked = () => { throw new DOMException('Storage blocked', 'SecurityError'); };
    Storage.prototype.getItem = blocked;
    Storage.prototype.setItem = blocked;
    Storage.prototype.removeItem = blocked;
  });
  await page.goto('/login/');
  await expect(page.getByRole('heading', { name: 'Bon retour.' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', 'system');
  expect(pageErrors).toEqual([]);
});


test('theme bootstrap ignores an invalid cached value', async ({ page }) => {
  await page.addInitScript(() => {
    const originalGetItem = Storage.prototype.getItem;
    Storage.prototype.getItem = function getItem(key) {
      if (key === 'theme') return 'sepia';
      return originalGetItem.call(this, key);
    };
  });
  await page.goto('/login/');
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', 'system');
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
  await page.getByRole('button', { name: 'Confirmer la suppression' }).click();
  await expect(page).toHaveURL('/');
  await expect(page.getByText(/désactivé et anonymisé/i)).toBeVisible();

  await login(page, 'sole.owner@e2e.makolo.test');
  await page.goto('/account/delete/');
  await expect(page.getByText(/dernier propriétaire/i)).toBeVisible();
  await expect(page.getByText(/Ajoutez ou transférez la propriété/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmer la suppression' })).toBeDisabled();
  await expect(page).toHaveURL('/account/delete/');
});
