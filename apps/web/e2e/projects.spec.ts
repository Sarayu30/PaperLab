import { test, expect, Page } from '@playwright/test';

async function createProject(page: Page, name: string) {
  await page.goto('/projects/new');
  await page.getByRole('button', { name: 'Use sample setup' }).click();
  await page.getByLabel('Project name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
}

test('create, refresh, revise and inspect preserved history', async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/projects');
  await expect(page.getByRole('heading', { name: 'Your first paper starts here.' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('desktop-empty.png'), fullPage: true });
  await createProject(page, 'ResNet reproduction');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'ResNet reproduction' })).toBeVisible();
  await page.getByRole('link', { name: 'Revise setup' }).click();
  await page.getByLabel('Evaluation metric', { exact: true }).fill('macro_f1');
  await page
    .getByLabel('Reason for the revision')
    .fill('Correct the metric after reviewing the paper.');
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByText('Revision 2', { exact: true })).toBeVisible();
  await expect(page.getByText('Correct the metric after reviewing the paper.')).toBeVisible();
  const original = page.locator('.revision-list li').filter({ hasText: 'Revision 1' });
  await original.locator('summary').click();
  await expect(original.getByText('test_error', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('desktop-detail.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('mobile-detail.png'), fullPage: true });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.getByRole('link', { name: 'All projects', exact: false }).click();
  await expect(page.getByRole('heading', { name: 'ResNet reproduction' })).toBeVisible();
});

test('stale human edits require reloading the latest revision', async ({ page, context }) => {
  await createProject(page, 'Concurrent review');
  const url = page.url() + '/edit';
  await page.goto(url);
  const other = await context.newPage();
  await other.goto(url);
  await expect(other.getByLabel('Evaluation metric', { exact: true })).toHaveValue('test_error');
  await page.getByLabel('Evaluation metric', { exact: true }).fill('accuracy');
  await page.getByLabel('Reason for the revision').fill('Use accuracy for this run.');
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.getByText('Revision 2', { exact: true })).toBeVisible();
  await other.getByLabel('Evaluation metric', { exact: true }).fill('f1');
  await other.getByLabel('Reason for the revision').fill('Another reviewer chose F1.');
  await other.getByRole('button', { name: 'Save revision' }).click();
  await expect(other.getByRole('alert')).toContainText('A newer revision was saved');
  await expect(other.getByRole('button', { name: 'Save revision' })).toBeDisabled();
  await other.getByRole('button', { name: 'Reload latest setup' }).click();
  await expect(other.getByLabel('Evaluation metric', { exact: true })).toHaveValue('accuracy');
  await other.close();
});

test('invalid setup is rejected and API failures offer retry', async ({ page }) => {
  await page.goto('/projects/new');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByText('Enter a project name.', { exact: true })).toBeVisible();
  await page.route('**/api/projects?*', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/projects');
  await expect(page.getByRole('alert')).toContainText('The API is unavailable');
  await page.unroute('**/api/projects?*');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Concurrent review' })).toBeVisible();
});
