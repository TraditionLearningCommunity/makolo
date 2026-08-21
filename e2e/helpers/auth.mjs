import { expect } from '@playwright/test';

export const E2E_PASSWORD = 'Makolo-E2E-2026!';

export async function login(page, email, password = E2E_PASSWORD) {
  await page.goto('/login/');
  await page.getByLabel('Adresse e-mail').fill(email);
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await Promise.all([
    page.waitForURL(/\/(?:dashboard|me|operations|spaces\/[^/]+(?:\/overview)?)\/$/),
    page.getByRole('button', { name: 'Se connecter' }).click(),
  ]);
  await expect(page.locator('#main-content')).toBeVisible();
}

export async function logout(page) {
  const menu = page.getByRole('menu');
  await page.waitForFunction(() => {
    const node = document.querySelector('[role="menu"]');
    return Boolean(node && !node.hasAttribute('x-cloak'));
  });
  await page.getByRole('button', { name: 'Menu utilisateur' }).click();
  await expect(menu).toBeVisible();
  await menu.getByRole('menuitem', { name: 'Se déconnecter' }).click();
  await page.waitForURL('/');
}
