import { test, expect } from '../fixtures/makolo.mjs';
import { login, logout } from '../helpers/auth.mjs';

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => (
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  ));
  expect(overflow).toBeFalsy();
}

test('Space Team operations remain usable and authority-safe on mobile @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/overview/');

  const menuButton = page.getByRole('button', { name: 'Ouvrir la navigation' });
  await expect(menuButton).toHaveAttribute('aria-expanded', 'false');
  await menuButton.click();
  await expect(menuButton).toHaveAttribute('aria-expanded', 'true');
  await page.locator('#app-sidebar').getByRole('link', { name: 'Équipe', exact: true }).click();
  await expect(page).toHaveURL(/\/spaces\/makolo-e2e-events\/team\/$/);
  await expectNoHorizontalOverflow(page);

  await page.getByRole('link', { name: 'Créer une équipe', exact: true }).first().click();
  await page.getByLabel('Nom de l’équipe').fill('Finance mobile E2E');
  await page.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(page.getByRole('heading', { name: 'Finance mobile E2E', exact: true })).toBeVisible();

  let financeTeam = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Finance mobile E2E', exact: true }) });
  await financeTeam.getByRole('link', { name: 'Ajouter', exact: true }).click();
  await page.getByLabel('Collaborateur Makolo').fill('finance@e2e.makolo.test');
  await page.getByRole('button', { name: 'Ajouter à cette équipe' }).click();
  financeTeam = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Finance mobile E2E', exact: true }) });
  await expect(financeTeam.getByText('finance@e2e.makolo.test', { exact: true })).toBeVisible();

  page.once('dialog', dialog => dialog.accept());
  await financeTeam.getByRole('button', { name: 'Retirer de cette équipe' }).click();
  financeTeam = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Finance mobile E2E', exact: true }) });
  await expect(financeTeam.getByText('finance@e2e.makolo.test', { exact: true })).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await logout(page);
  await login(page, 'finance@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/payments/');
  await expect(page.getByRole('heading', { name: 'Paiements', exact: true }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test('Space Scanner exposes safe camera fallbacks and tactile refusal feedback on mobile @mobile', async ({ page }) => {
  await page.addInitScript(() => {
    const denied = () => Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        enumerateDevices: async () => [
          { kind: 'videoinput', deviceId: 'rear-e2e', label: 'Caméra arrière E2E' },
        ],
        getUserMedia: denied,
      },
    });
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true,
      value: pattern => {
        window.__makoloVibration = pattern;
        return true;
      },
    });
  });

  await login(page, 'owner@e2e.makolo.test');
  await page.goto('/spaces/makolo-e2e-events/control/');
  await expectNoHorizontalOverflow(page);
  const scannerLink = page.locator('a[href*="/control/"]').filter({ hasText: 'Ouvrir le scanner' }).first();
  await scannerLink.click();

  await expect(page.locator('#camera-state')).toContainText(/refusé|indisponible|image QR/i);
  await expect(page.getByText('Lire un QR depuis une image', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Code de l’accès')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Scanner le suivant' })).toBeHidden();
  await expectNoHorizontalOverflow(page);

  await page.getByLabel('Code de l’accès').fill('credential-invalide-t28-e2e');
  await page.getByRole('button', { name: 'Vérifier l’accès' }).click();
  await expect(page.locator('#result-title')).toContainText(/QR|Contrôle|Billet/i);
  await expect.poll(() => page.evaluate(() => window.__makoloVibration)).toEqual([25, 35, 25]);

  await page.goto('/spaces/makolo-e2e-events/operations/');
  await expect(page.getByRole('heading', { name: 'Opérations', exact: true }).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test('Space operational surfaces avoid critical horizontal overflow across representative viewports @mobile', async ({ page }) => {
  await login(page, 'owner@e2e.makolo.test');
  const viewports = [
    { width: 375, height: 667 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
    { width: 768, height: 1024 },
  ];
  const paths = [
    '/spaces/makolo-e2e-events/overview/',
    '/spaces/makolo-e2e-events/team/',
    '/spaces/makolo-e2e-events/operations/',
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    for (const path of paths) {
      await page.goto(path);
      await expectNoHorizontalOverflow(page);
    }
  }
});
