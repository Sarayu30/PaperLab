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
  await expect(
    page.getByRole('heading', { name: 'Which result would you like to check?' }),
  ).toBeVisible();
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
  await createProject(page, 'API recovery example');
  await page.goto('/projects/new');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByText('Enter a project name.', { exact: true })).toBeVisible();
  await page.route('**/api/projects?*', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/projects');
  await expect(page.getByRole('alert')).toContainText('The API is unavailable');
  await page.unroute('**/api/projects?*');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'API recovery example' })).toBeVisible();
});

test('requirements adapt without losing values and preserve custom history', async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/projects/new');
  await expect(page.getByLabel('Kind of work')).toHaveValue('undecided');
  await expect(page.locator('.resource-rows input')).toHaveCount(0);
  await page.getByRole('button', { name: 'Use sample setup' }).click();
  await page.getByLabel('Project name', { exact: true }).fill('Hosted evaluation notebook');
  await page.getByLabel('Kind of work').selectOption('cpu');
  await expect(
    page.locator('.resource-suggestions').getByRole('button', { name: /GPU/ }),
  ).toHaveCount(0);
  await page.getByRole('button', { name: '+ System RAM available', exact: true }).click();
  await page.getByLabel('System RAM available', { exact: true }).fill('16');
  await page.getByLabel('Kind of work').selectOption('api');
  await expect(page.getByLabel('System RAM available', { exact: true })).toHaveValue('16');
  await page.getByRole('button', { name: '+ Experiment API budget', exact: true }).click();
  await page.getByLabel('Experiment API budget', { exact: true }).fill('0');
  await page.getByRole('button', { name: '+ API request quota', exact: true }).click();
  await page.getByText('Add another requirement', { exact: true }).click();
  await page.getByRole('button', { name: '+ Custom requirement', exact: true }).click();
  await page.getByLabel('Requirement name', { exact: true }).fill('Dataset license');
  await page.getByLabel('Requirement details', { exact: true }).fill('Research use only');
  await page.getByLabel('Where you plan to run it').selectOption('colab');
  await expect(page.locator('.platform-note')).toBeVisible();
  await page.screenshot({ path: info.outputPath('desktop-form.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('mobile-form.png'), fullPage: true });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(
    page.getByRole('heading', { name: 'Hosted evaluation notebook', exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator('.requirements-ledger')).toContainText('0 USD');
  await expect(page.locator('.requirements-ledger')).toContainText('To be confirmed');
  await expect(page.locator('.requirements-ledger')).toContainText('Research use only');
  await page.getByRole('link', { name: 'Revise setup' }).click();
  await page.getByRole('button', { name: 'Remove System RAM available', exact: true }).click();
  await page.getByLabel('Experiment API budget', { exact: true }).fill('12');
  await page
    .getByLabel('Reason for the revision')
    .fill('Use hosted inference; remove local memory constraint.');
  await page.getByRole('button', { name: 'Save revision' }).click();
  await expect(page.locator('.requirements-ledger')).not.toContainText('System RAM available');
  await expect(page.locator('.requirements-ledger')).toContainText('12 USD');
  const old = page.locator('.revision-list li').filter({ hasText: 'Revision 1' });
  await old.locator('summary').click();
  await expect(old).toContainText('System RAM available: 16 GB');
  await expect(old).toContainText('Experiment API budget: 0 USD');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: info.outputPath('resources-detail.png'), fullPage: true });
});

test('resource validation and notebook search', async ({ page }, info) => {
  await page.goto('/projects/new');
  await page.getByRole('button', { name: 'Use sample setup' }).click();
  await page.getByLabel('Project name', { exact: true }).fill('CPU benchmark');
  await page.getByLabel('Kind of work').selectOption('cpu');
  await page.getByRole('button', { name: '+ CPU cores available', exact: true }).click();
  await page.getByLabel('CPU cores available', { exact: true }).fill('1.5');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('alert')).toContainText('whole numbers');
  await page.getByLabel('CPU cores available', { exact: true }).fill('4');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('heading', { name: 'CPU benchmark', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'All projects', exact: false }).click();
  await page.getByLabel('Find a project').fill('CPU benchmark');
  await expect(page.locator('.project-row')).toHaveCount(1);
  await page.getByLabel('Find a project').fill('nonexistent-experiment');
  await expect(page.locator('.no-results')).toBeVisible();
  await page.getByRole('button', { name: 'Clear search' }).click();
  await expect(page.getByRole('heading', { name: 'CPU benchmark', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: info.outputPath('desktop-index.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('mobile-index.png'), fullPage: true });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});
