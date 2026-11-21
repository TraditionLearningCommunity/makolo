import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function mountMenu(page) {
  // Injected after initial load to exercise HTMX-compatible event delegation.
  await page.evaluate(() => {
    const root = document.createElement('section');
    root.id = 'interaction-foundation-fixture';
    root.innerHTML = [
      '<div class="mk-interaction mk-action-menu" data-mk-action-menu>',
      '  <button type="button" class="mk-action-button" data-variant="secondary"',
      '    data-mk-action-trigger aria-expanded="false" aria-controls="fixture-panel"',
      '    aria-label="Actions sur le Dossier">Actions</button>',
      '  <div id="fixture-panel" class="mk-action-panel" data-mk-action-panel hidden>',
      '    <button type="button" class="mk-action-item">Ouvrir</button>',
      '    <button type="button" class="mk-action-item" disabled>Déplacer</button>',
      '    <a href="#main-content" class="mk-action-item">Voir le détail</a>',
      '  </div>',
      '</div>',
    ].join('');
    document.querySelector('#main-content').append(root);
  });
}

test('shared menu opens after page load and restores focus on Escape', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/me/');
  await expect(page.locator('link[href*="makolo-interactions.css"]')).toHaveCount(1);
  await mountMenu(page);
  const trigger = page.getByRole('button', { name: 'Actions sur le Dossier' });
  const panel = page.locator('#fixture-panel');

  await trigger.click();
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  await expect(panel).toBeVisible();
  await expect(page.getByRole('button', { name: 'Ouvrir' })).toBeFocused();
  await expect(page.getByRole('button', { name: 'Déplacer' })).toBeDisabled();

  await page.keyboard.press('Escape');
  await expect(panel).toBeHidden();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await expect(trigger).toBeFocused();
});

test('shared menu keyboard arrows skip disabled actions and closes on outside click', async ({ page }) => {
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/me/');
  await mountMenu(page);
  const trigger = page.getByRole('button', { name: 'Actions sur le Dossier' });
  const panel = page.locator('#fixture-panel');

  await trigger.focus();
  await page.keyboard.press('ArrowUp');
  await expect(panel).toBeVisible();
  await expect(page.getByRole('link', { name: 'Voir le détail' })).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('button', { name: 'Ouvrir' })).toBeFocused();

  await page.locator('#main-content').click({ position: { x: 5, y: 5 } });
  await expect(panel).toBeHidden();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
});
