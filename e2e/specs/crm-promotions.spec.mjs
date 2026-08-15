import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';


test('marketing creates an audience and targets an Event promotion to it', async ({ page }) => {
  await login(page, 'marketing@e2e.makolo.test');

  let response = await page.goto('/crm/org/makolo-e2e-events/audiences/new/');
  expect(response.status()).toBe(200);
  await page.getByLabel('Nom').fill('Audience Marketing E2E');
  await page.getByLabel('Description').fill('Audience statique pour la configuration Promotion E2E.');
  await page.getByLabel('Source').selectOption('static');
  await page.getByRole('button', { name: "Créer l’Audience" }).click();
  await expect(page.getByRole('heading', { name: 'Audience Marketing E2E' })).toBeVisible();
  await expect(page.getByText('0 membre(s)')).toBeVisible();

  response = await page.goto('/promotions/org/makolo-e2e-events/new/');
  expect(response.status()).toBe(200);
  await page.locator('input[name="name"]').fill('Promotion Audience E2E');
  await page.locator('select[name="event"]').selectOption({ label: 'Festival Makolo E2E' });
  await page.locator('select[name="discount_type"]').selectOption('percent');
  await page.locator('input[name="discount_value"]').fill('15.00');
  await page.locator('input[name="currency"]').fill('USD');

  const festivalTicket = page.locator('label').filter({ hasText: 'Festival Makolo E2E — Pass standard' });
  await expect(festivalTicket).toHaveCount(1);
  await festivalTicket.locator('input[name="eligible_ticket_types"]').check();

  const audienceOption = page.locator('select[name="audience"] option').filter({ hasText: 'Audience Marketing E2E' });
  await expect(audienceOption).toHaveCount(1);
  const audienceId = await audienceOption.getAttribute('value');
  expect(audienceId).toBeTruthy();
  await page.locator('select[name="audience"]').selectOption(audienceId);

  await page.getByRole('button', { name: "Créer l’offre" }).click();

  await expect(page).toHaveURL(/\/promotions\/org\/makolo-e2e-events\/$/);
  const promotionHeading = page.getByRole('heading', { name: 'Promotion Audience E2E', exact: true });
  await expect(promotionHeading).toBeVisible();
  await promotionHeading.locator('xpath=ancestor::a[1]').click();
  await page.getByRole('link', { name: 'Modifier les règles' }).click();
  await expect(page.locator('select[name="audience"]')).toHaveValue(audienceId);
  const editedFestivalTicket = page.locator('label').filter({ hasText: 'Festival Makolo E2E — Pass standard' });
  await expect(editedFestivalTicket.locator('input[name="eligible_ticket_types"]')).toBeChecked();
});
