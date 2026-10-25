import { test, expect } from '@playwright/test';

test.setTimeout(60000);

test('landing demo explains capabilities and connects to the working notebook', async ({
  page,
}, info) => {
  const errors: string[] = [];
  const writes: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('request', (request) => {
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(request.method())) writes.push(request.url());
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Read the paper.Question it.Make it run.',
  );
  await expect(page.getByRole('link', { name: 'PaperLab home' })).toContainText('[p.]');
  await expect(
    page.getByText('Agent orchestration and execution are on the roadmap.'),
  ).toBeVisible();
  await page.screenshot({ path: info.outputPath('landing-desktop.png'), fullPage: true });
  await page.screenshot({ path: info.outputPath('landing-hero.png') });
  await page.getByRole('button', { name: 'Using a model API' }).click();
  await expect(page.locator('.demo-sheet')).toContainText('Experiment API budget');
  await expect(page.locator('.demo-sheet')).not.toContainText('GPU time ceiling');
  await page.getByRole('button', { name: 'Apply to this example' }).click();
  await expect(page.locator('.added-row')).toContainText('Public datasets only');
  await expect(page.locator('.demo-sheet-top')).toContainText('REVISION 02');
  await expect(page.getByRole('status')).toContainText('Your real projects are unchanged');
  await page.getByRole('button', { name: 'Training a model' }).click();
  await expect(page.locator('.demo-sheet')).toContainText('Accelerator memory');
  await expect(page.locator('.added-row')).toHaveCount(0);
  await page.getByRole('button', { name: 'Apply to this example' }).click();
  await page.getByRole('button', { name: 'Reset example' }).click();
  await expect(page.locator('.demo-sheet-top')).toContainText('REVISION 01');
  await page.getByRole('link', { name: 'Start an experiment' }).click();
  await expect(page).toHaveURL(/\/projects\/new$/);
  await expect(page.getByLabel('Project name', { exact: true })).toBeVisible();
  await expect(page.locator('.landing-shell')).toHaveCount(0);
  await page.getByRole('link', { name: 'PaperLab home' }).click();
  await expect(page.locator('.landing-shell')).toBeVisible();
  await page.getByRole('link', { name: 'Your notebook', exact: true }).click();
  await expect(page).toHaveURL(/\/projects$/);
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});

test('landing works on narrow screens and supports keyboard and reduced motion', async ({
  page,
}, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.screenshot({ path: info.outputPath('landing-mobile-hero.png') });
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await page.getByRole('button', { name: 'Using a model API' }).click();
  await page.getByRole('button', { name: 'Apply to this example' }).click();
  await expect(page.locator('.added-row')).toBeVisible();
  expect(
    await page.locator('.human-note').evaluate((el) => getComputedStyle(el).animationName),
  ).toBe('none');
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('landing-mobile.png'), fullPage: true });
  await page.getByRole('link', { name: 'Write your first brief' }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.getByLabel('Project name', { exact: true })).toBeVisible();
});
