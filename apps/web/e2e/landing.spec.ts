import { test, expect } from '@playwright/test';

test.setTimeout(60000);

test('overview uses real catalog, explains source and hands workload to the form', async ({
  page,
}, info) => {
  const errors: string[] = [];
  const writes: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(request.method())) writes.push(request.url());
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Turn research');
  await expect(page.getByRole('link', { name: 'PaperLab home' })).toContainText('[p.]');
  await expect(page.locator('.first-brief')).toBeVisible();
  await page.screenshot({ path: info.outputPath('overview-desktop.png'), fullPage: true });
  await page.screenshot({ path: info.outputPath('overview-first-screen.png') });
  await page.getByRole('button', { name: 'Hosted API experiment', exact: false }).click();
  await expect(page.locator('.workload-detail')).toContainText('API request quota');
  await expect(page.locator('.workload-detail')).not.toContainText('GPU time ceiling');
  await page.getByRole('button', { name: /The decision boundary/ }).click();
  await expect(page.locator('.implementation-detail')).toContainText(
    'Project.revision == request.expected_revision',
  );
  await expect(
    page.locator('.implementation-detail').getByRole('link', { name: 'View source' }),
  ).toHaveAttribute('href', /services\/api\/paperlab_api\/main.py$/);
  await page.getByRole('button', { name: /The record/ }).click();
  await expect(page.locator('.implementation-detail')).toContainText('contract_revisions');
  await page.getByRole('link', { name: 'Use this starting point' }).click();
  await expect(page.getByLabel('Kind of work')).toHaveValue('api');
  await expect(page.locator('.resource-rows input')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await page.getByRole('link', { name: 'PaperLab home' }).click();
  await page.getByRole('link', { name: 'Your notebook', exact: true }).click();
  await expect(page).toHaveURL(/\/projects$/);
  await page.goto('/projects/new?workload=not-a-workload');
  await expect(page.getByLabel('Kind of work')).toHaveValue('undecided');
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});

test('overview handles API failure, retries and shows returned project records', async ({
  page,
}) => {
  await page.route('**/api/projects?*', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('API is unavailable');
  await page.unroute('**/api/projects?*');
  await page.route('**/api/projects?*', (route) =>
    route.fulfill({
      json: [
        {
          id: '00000000-0000-4000-8000-000000000123',
          revision: 3,
          status: 'draft',
          created_at: '2026-10-25T00:00:00Z',
          updated_at: '2026-10-25T01:00:00Z',
          setup: {
            name: 'API response fixture',
            dataset: 'Test dataset',
            metric: 'accuracy',
            target_result: 'Check a saved target',
            resource_plan: { workload: 'cpu', environment: 'local', requirements: [] },
          },
        },
      ],
    }),
  );
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await expect(
    page.getByRole('heading', { name: 'API response fixture', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.research-entry')).toContainText('Revision 3');
  await expect(page.locator('.research-entry')).toHaveAttribute(
    'href',
    '/projects/00000000-0000-4000-8000-000000000123',
  );
});

test('overview is keyboard accessible and fits mobile and tablet', async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await page.getByRole('button', { name: 'Simulation / RL', exact: false }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.workload-detail')).toContainText('Software or simulator');
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
  }
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.screenshot({ path: info.outputPath('overview-tablet.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('overview-mobile.png'), fullPage: true });
  await page.getByRole('link', { name: 'Write the brief', exact: false }).click();
  await expect(page.getByLabel('Project name', { exact: true })).toBeVisible();
});
