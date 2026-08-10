import { promises as fs } from 'node:fs';
import { test as rawTest, expect as rawExpect } from '@playwright/test';
import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


test('Operations distinguishes demo history from a real live incident', async ({ page }) => {
  await login(page, 'staff@e2e.makolo.test');
  await page.goto('/operations/');
  await expect(page.getByRole('heading', { name: 'Makolo Operations Center' })).toBeVisible();
  await expect(page.getByText('Données de démonstration détectées')).toBeVisible();
  await expect(page.getByText('Incident réel E2E visible')).toBeVisible();
  await expect(page.getByText('Incident démo E2E à ignorer')).toHaveCount(0);
  await expect(page.getByText('CRITICAL', { exact: true }).first()).toBeVisible();
});


test('403 and public 404 are branded safe exits without tracebacks', async ({ page }) => {
  await login(page, 'participant@e2e.makolo.test');
  let response = await page.goto('/events/new/');
  expect(response.status()).toBe(403);
  await expect(page.getByText(/Erreur 403/i)).toBeVisible();
  await expect(page.getByRole('heading', { name: /Cet espace n’est pas accessible/i })).toBeVisible();
  await expect(page.getByText(/Traceback|PermissionDenied/)).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Vue d’ensemble|Découvrir/i }).first()).toBeVisible();

  await page.context().clearCookies();
  response = await page.goto('/page-e2e-qui-n-existe-pas/');
  expect(response.status()).toBe(404);
  await expect(page.getByText(/404|introuvable/i).first()).toBeVisible();
  await expect(page.getByText(/Traceback/)).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Accueil|Découvrir/i }).first()).toBeVisible();
});


rawTest('controlled 500 exposes an MKL correlation id and writes the same id to the log', async ({ page }) => {
  const response = await page.goto('/__e2e__/error/500/');
  rawExpect(response.status()).toBe(500);
  await rawExpect(page.getByRole('heading', { name: /Makolo n’a pas pu terminer/i })).toBeVisible();
  const incident = (await page.getByText(/^MKL-[A-F0-9]{6}$/).textContent()).trim();
  rawExpect(incident).toMatch(/^MKL-[A-F0-9]{6}$/);
  await rawExpect(page.getByText(/Traceback|RuntimeError/)).toHaveCount(0);

  const serverLog = process.env.E2E_SERVER_LOG || '/tmp/makolo-e2e-server.log';
  await rawExpect.poll(async () => {
    const content = await fs.readFile(serverLog, 'utf8').catch(() => '');
    return content.includes(incident);
  }).toBe(true);
});
