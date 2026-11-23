import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

async function setup(page) {
  await login(page, 'empty.participant@e2e.makolo.test');
  await page.goto('/me/');
  await expect(page.locator('script[src*="makolo-interactions-f2.js"]')).toHaveCount(1);
}

test('F2 selection is local and supports explicit clearing', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const fixture = document.createElement('section');
    fixture.id = 'f2-select';
    fixture.setAttribute('data-mk-selection-scope', '');
    fixture.innerHTML = [
      '<label><input type="checkbox" data-mk-select-item value="a"> Alpha</label>',
      '<label><input type="checkbox" data-mk-select-item value="b"> Beta</label>',
      '<label><input type="checkbox" data-mk-select-item value="private" disabled> Privé</label>',
      '<div data-mk-selection-bar hidden>',
      '  <span data-mk-selection-count>0</span>',
      '  <button type="button" data-mk-selection-clear>Terminer la sélection</button>',
      '</div>'
    ].join('');
    document.getElementById('main-content').append(fixture);
  });
  const fixture = page.locator('#f2-select');
  await fixture.getByRole('checkbox', { name: 'Alpha' }).check();
  await fixture.getByRole('checkbox', { name: 'Beta' }).check();
  await expect(fixture.locator('[data-mk-selection-count]')).toHaveText('2');
  await expect(fixture.locator('[data-mk-selection-bar]')).toBeVisible();
  expect(await page.evaluate(() => window.MakoloInteractions.selectedIds(
    document.querySelector('#f2-select')))).toEqual(['a', 'b']);
  await fixture.getByRole('button', { name: 'Terminer la sélection' }).click();
  await expect(fixture.locator('[data-mk-selection-bar]')).toBeHidden();
  expect(await page.evaluate(() => window.MakoloInteractions.selectedIds(
    document.querySelector('#f2-select')))).toEqual([]);
});

test('F2 local query filters only acquired corpus and restores stable order', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const fixture = document.createElement('section');
    fixture.id = 'f2-query';
    fixture.setAttribute('data-mk-query-scope', '');
    fixture.dataset.mkQueryLocal = 'true';
    fixture.dataset.mkSortKeys = 'name';
    fixture.innerHTML = [
      '<label>Recherche locale<input type="search" data-mk-query-search></label>',
      '<label>Trier<select data-mk-query-sort><option value="">Sans tri</option>',
      '<option value="name">Nom</option></select></label>',
      '<label>Filtrer<select data-mk-query-filter><option value="">Tous</option>',
      '<option value="active">Actif</option></select></label>',
      '<div data-mk-query-items>',
      '<p data-mk-query-item data-mk-filter-value="active" data-mk-sort-name="Beta">Beta</p>',
      '<p data-mk-query-item data-mk-filter-value="inactive" data-mk-sort-name="Alpha">Alpha</p>',
      '<p data-mk-query-item data-mk-filter-value="active" data-mk-sort-name="Gamma">Gamma</p>',
      '</div>',
      '<p data-mk-query-empty hidden>Aucun résultat dans ces éléments.</p>',
      '<output data-mk-query-count></output>'
    ].join('');
    document.getElementById('main-content').append(fixture);
    window.MakoloInteractions.applyLocalQuery(fixture);
  });
  const fixture = page.locator('#f2-query');
  const visible = () => fixture.locator('[data-mk-query-item]:visible').allTextContents();
  expect(await visible()).toEqual(['Beta', 'Alpha', 'Gamma']);
  await fixture.getByLabel('Trier').selectOption('name');
  expect(await visible()).toEqual(['Alpha', 'Beta', 'Gamma']);
  await fixture.getByLabel('Filtrer').selectOption('active');
  expect(await visible()).toEqual(['Beta', 'Gamma']);
  await fixture.getByLabel('Recherche locale').fill('Impossible');
  await expect(fixture.locator('[data-mk-query-empty]')).toBeVisible();
  await fixture.getByLabel('Recherche locale').fill('');
  await fixture.getByLabel('Filtrer').selectOption('');
  await fixture.getByLabel('Trier').selectOption('');
  expect(await visible()).toEqual(['Beta', 'Alpha', 'Gamma']);
});

test('F2 preview uses native dialog and restores trigger focus', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const section = document.createElement('section');
    section.innerHTML = [
      '<button type="button" data-mk-preview-target="f2-preview">Aperçu F2</button>',
      '<dialog id="f2-preview" class="mk-interaction-preview" data-mk-preview',
      ' aria-labelledby="f2-title"><h2 id="f2-title">Dossier acquis</h2>',
      '<button type="button" data-mk-preview-close>Fermer l’aperçu</button></dialog>',
    ].join('');
    document.getElementById('main-content').append(section);
  });
  const button = page.getByRole('button', { name: 'Aperçu F2' });
  await button.click();
  await expect(page.getByRole('dialog', { name: 'Dossier acquis' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Dossier acquis' })).toBeHidden();
  await expect(button).toBeFocused();
});

test('F2 inline editor discards draft without posting owner form', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const section = document.createElement('section');
    section.id = 'f2-editor';
    section.setAttribute('data-mk-inline-edit', '');
    section.innerHTML = [
      '<div data-mk-edit-view><span>Valeur canonique</span>',
      '<button type="button" data-mk-edit-open>Modifier le titre</button></div>',
      '<form data-mk-edit-form action="/should-not-be-called/" method="post" hidden>',
      '<input name="title" aria-label="Titre" value="Valeur canonique">',
      '<button type="button" data-mk-edit-cancel>Annuler la modification</button>',
      '</form>'
    ].join('');
    document.getElementById('main-content').append(section);
  });
  const section = page.locator('#f2-editor');
  await section.getByRole('button', { name: 'Modifier le titre' }).click();
  await section.getByRole('textbox', { name: 'Titre' }).fill('Un brouillon');
  await page.keyboard.press('Escape');
  await expect(section.getByRole('textbox', { name: 'Titre' })).toBeHidden();
  await expect(section.getByText('Valeur canonique')).toBeVisible();
  await section.getByRole('button', { name: 'Modifier le titre' }).click();
  await expect(section.getByRole('textbox', { name: 'Titre' })).toHaveValue('Valeur canonique');
});

test('F2 reorder keeps DOM unchanged until owner confirms and provides keyboard alternative', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const section = document.createElement('section');
    section.id = 'f2-reorder';
    section.setAttribute('data-mk-reorder-scope', '');
    section.innerHTML = [
      '<div data-mk-reorder-items>',
      '<div data-mk-reorder-item data-mk-reorder-id="a">Alpha',
      '<button type="button" data-mk-reorder-down>Descendre Alpha</button></div>',
      '<div data-mk-reorder-item data-mk-reorder-id="b">Beta',
      '<button type="button" data-mk-reorder-up>Monter Beta</button></div>',
      '</div>',
    ].join('');
    document.getElementById('main-content').append(section);
  });
  const order = () => page.locator('#f2-reorder [data-mk-reorder-item]')
    .evaluateAll((nodes) => nodes.map((node) => node.dataset.mkReorderId));
  const button = page.getByRole('button', { name: 'Descendre Alpha' });
  await button.click();
  expect(await order()).toEqual(['a', 'b']);
  await page.evaluate(() => window.MakoloInteractions.registerReorder(
    document.querySelector('#f2-reorder'), async () => false));
  await button.click();
  await expect(page.locator('#f2-reorder')).not.toHaveAttribute('aria-busy', 'true');
  expect(await order()).toEqual(['a', 'b']);
  await page.evaluate(() => window.MakoloInteractions.registerReorder(
    document.querySelector('#f2-reorder'), async () => true));
  await button.click();
  await expect.poll(order).toEqual(['b', 'a']);
});

test('F2 move cannot register without fallback and confirms only after owner reply', async ({ page }) => {
  await setup(page);
  const accepted = await page.evaluate(() => {
    const section = document.createElement('section');
    section.id = 'f2-move';
    section.setAttribute('data-mk-move-scope', '');
    section.innerHTML = [
      '<div data-mk-move-source data-mk-move-id="dossier1">',
      '<button type="button" draggable="true" data-mk-move-handle>Déplacer Dossier</button></div>',
      '<div data-mk-move-destination data-mk-destination-id="project2">Projet cible</div>',
      '<p data-mk-move-status role="status"></p>'
    ].join('');
    document.getElementById('main-content').append(section);
    return window.MakoloInteractions.registerMove(section, async () => true);
  });
  expect(accepted).toBe(false);

  const acceptedWithFallback = await page.evaluate(() => {
    const scope = document.getElementById('f2-move');
    const form = document.createElement('form');
    form.setAttribute('data-mk-move-form', '');
    form.method = 'post';
    form.action = '/owner-action-only/';
    form.innerHTML = [
      '<input type="hidden" name="csrfmiddlewaretoken" value="fixture">',
      '<select name="destination_id" aria-label="Choisir un projet">',
      '<option value="project2">Projet cible</option></select>',
      '<button type="submit">Déplacer via formulaire</button>',
    ].join('');
    scope.append(form);
    return window.MakoloInteractions.registerMove(scope, async () => false);
  });
  expect(acceptedWithFallback).toBe(true);
  const source = page.getByRole('button', { name: 'Déplacer Dossier' });
  const target = page.locator('#f2-move [data-mk-move-destination]');
  await source.dragTo(target);
  await expect(page.locator('#f2-move [data-mk-move-status]'))
    .toHaveText('Déplacement non confirmé.');

  await page.evaluate(() => window.MakoloInteractions.registerMove(
    document.querySelector('#f2-move'), async () => true));
  await source.dragTo(target);
  await expect(page.locator('#f2-move [data-mk-move-status]'))
    .toHaveText('Déplacement confirmé.');
});


test('F2 context restore refuses another actor scope and preserves local choices', async ({ page }) => {
  await setup(page);
  const result = await page.evaluate(() => {
    const make = (key) => {
      const root = document.createElement('section');
      root.setAttribute('data-mk-context-key', key);
      root.setAttribute('data-mk-query-scope', '');
      root.dataset.mkQueryLocal = 'true';
      root.setAttribute('data-mk-selection-scope', '');
      root.innerHTML = [
        '<input data-mk-query-search value="">',
        '<div data-mk-query-items>',
        '<p data-mk-query-item>Alpha</p>',
        '<p data-mk-query-item>Beta</p>',
        '</div>',
        '<input type="checkbox" data-mk-select-item value="alpha">',
        '<span data-mk-selection-count>0</span>',
      ].join('');
      document.querySelector('#main-content').append(root);
      return root;
    };
    const source = make('actor-one');
    source.querySelector('[data-mk-query-search]').value = 'Alpha';
    source.querySelector('[data-mk-select-item]').checked = true;
    const captured = window.MakoloInteractions.captureContext(source);
    const other = make('actor-two');
    const refused = window.MakoloInteractions.restoreContext(other, captured);
    const target = make('actor-one');
    const applied = window.MakoloInteractions.restoreContext(target, captured);
    return {
      refused, applied,
      query: target.querySelector('[data-mk-query-search]').value,
      checked: target.querySelector('[data-mk-select-item]').checked,
      count: target.querySelector('[data-mk-selection-count]').textContent,
    };
  });
  expect(result).toEqual({
    refused: false, applied: true, query: 'Alpha', checked: true, count: '1',
  });
});

test('F2 right-click opens only opt-in contextual menu, not inputs', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const root = document.createElement('section');
    root.id = 'f2-context-menu';
    root.setAttribute('data-mk-context-shortcut', '');
    root.innerHTML = [
      '<p>Objet avec actions</p>',
      '<div data-mk-action-menu>',
      '<button type="button" data-mk-action-trigger aria-label="Options F2"',
      ' aria-expanded="false">⋯</button>',
      '<div data-mk-action-panel hidden><button type="button"',
      ' class="mk-action-item">Inspecter</button></div>',
      '</div>',
      '<input aria-label="Texte sans raccourci">',
    ].join('');
    document.querySelector('#main-content').append(root);
  });
  await page.getByText('Objet avec actions').click({ button: 'right' });
  await expect(page.getByRole('button', { name: 'Options F2' }))
    .toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Options F2' }))
    .toHaveAttribute('aria-expanded', 'false');
});


test('F2 semantic icon registry and shared button tokens are available globally', async ({ page }) => {
  await setup(page);
  const result = await page.evaluate(() => {
    const button = document.createElement('button');
    button.className = 'mk-action-button';
    button.setAttribute('data-variant', 'primary');
    button.textContent = 'Confirmer';
    document.querySelector('#main-content').append(button);
    return {
      intents: Object.keys(window.MakoloInteractionIcons || {}),
      move: window.MakoloInteractionIcons?.move,
      font: getComputedStyle(button).fontFamily,
      height: button.getBoundingClientRect().height,
    };
  });
  expect(result.intents).toHaveLength(15);
  expect(result.move).toBe('folder-input');
  expect(result.font).toBeTruthy();
  expect(result.height).toBeGreaterThanOrEqual(44);
});

test('F2 shared primary button and preview remain accessible on compact Web @mobile', async ({ page }) => {
  await setup(page);
  await page.evaluate(() => {
    const section = document.createElement('section');
    section.innerHTML = [
      '<button class="mk-action-button" data-variant="primary"',
      ' data-mk-preview-target="f2-compact-preview">Voir</button>',
      '<dialog class="mk-interaction-preview" data-mk-preview',
      ' id="f2-compact-preview" aria-label="Aperçu compact">',
      '<p>Contenu utile</p>',
      '<button type="button" data-mk-preview-close>Fermer</button></dialog>',
    ].join('');
    document.querySelector('#main-content').append(section);
  });
  await page.getByRole('button', { name: 'Voir' }).click();
  await expect(page.getByRole('dialog', { name: 'Aperçu compact' })).toBeVisible();
  const measures = await page.locator('#f2-compact-preview').evaluate((dialog) => {
    const rect = dialog.getBoundingClientRect();
    return { left: rect.left, right: rect.right, viewport: innerWidth };
  });
  expect(measures.left).toBeGreaterThanOrEqual(0);
  expect(measures.right).toBeLessThanOrEqual(measures.viewport + 1);
  await page.getByRole('button', { name: 'Fermer' }).click();
  await expect(page.getByRole('dialog', { name: 'Aperçu compact' })).toBeHidden();
});
