import { test, expect, Page } from '@playwright/test';
import { Workspace, Run, Stage } from '../src/app/research/research-api';

test.setTimeout(60000);
const projectId = '00000000-0000-4000-8000-000000000111';
const paperText = 'We evaluate a linear classifier on a held-out validation set. '.repeat(12);

async function mockWorkspace(page: Page, configured = true, pending = false) {
  const state: Workspace = {
    version: 1,
    project_revision: 1,
    active_run: null,
    approved_plan: null,
    source: null,
    artifacts: {},
    feedback: '',
    evidence: {},
    runs: [],
    total_tokens: 0,
    cost_note: 'Test fixture',
  };
  const calls: { stage: Stage; message: string; feedback: string }[] = [];
  const project = {
    id: projectId,
    revision: 1,
    status: 'draft',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    setup: {
      name: 'Research workflow test',
      paper_url: 'https://arxiv.org/abs/1512.03385',
      target_result: 'Check one result',
      dataset: 'Fixture data',
      metric: 'accuracy',
      reproduction_mode: 'reimplement',
      control_mode: 'guided',
      learning_mode: true,
      resource_plan: { workload: 'cpu', environment: 'local', requirements: [] },
    },
  };
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path === '/api/ai/status')
      return route.fulfill({ json: { configured, model: 'test-model', provider: 'Groq' } });
    if (path === `/api/projects/${projectId}`) return route.fulfill({ json: project });
    if (method === 'GET') return route.fulfill({ json: state });
    const body = route.request().postDataJSON();
    if (body.expected_version !== state.version)
      return route.fulfill({
        status: 409,
        json: { detail: 'The workspace changed. Refresh before continuing.' },
      });
    if (path.endsWith('/source/text')) {
      state.version++;
      state.source = {
        id: 'fixture-source',
        name: body.name,
        digest: 'abc123abc123',
        pages: [{ page: 1, text: body.text }],
      };
    } else if (path.endsWith('/runs')) {
      const run: Run = {
        id: `${body.stage}-${state.version}-${state.runs.length}`,
        stage: body.stage,
        status: pending ? 'running' : 'completed',
        workspace_version: state.version,
        project_revision: 1,
        output: pending
          ? {}
          : {
              title: 'Fixture draft',
              summary: 'A source-grounded test draft.',
              sections: [{ heading: 'Method', body: 'Use a validation split.' }],
              citations: [{ page: 1, quote: 'We evaluate a linear classifier' }],
              tasks:
                body.stage === 'plan'
                  ? [
                      {
                        id: 'load',
                        title: 'Load the dataset',
                        description: 'Split data before preprocessing.',
                        depends_on: [],
                        acceptance: 'No split overlap',
                      },
                    ]
                  : [],
              files:
                body.stage === 'implementation'
                  ? [{ path: 'src/train.py', content: 'print("review before running")' }]
                  : [],
              warnings: ['AI draft; not executed.'],
            },
        usage: { model: 'test-model', total_tokens: 200 },
        error: '',
        message: body.message,
        feedback: state.feedback,
        created_at: new Date().toISOString(),
        finished_at: null,
      };
      calls.push({ stage: body.stage, message: body.message, feedback: state.feedback });
      state.runs.unshift(run);
      if (pending) state.active_run = run.id;
      else if (body.stage !== 'chat') state.artifacts[body.stage as Stage] = run;
      return route.fulfill({ status: 202, json: run });
    } else if (path.endsWith('/approve')) state.approved_plan = body.plan_id;
    else if (path.endsWith('/feedback')) {
      state.version++;
      state.feedback += body.message;
      const order: Stage[] = [
        'analysis',
        'plan',
        'implementation',
        'review',
        'results',
        'extensions',
        'report',
      ];
      for (const stage of order.slice(order.indexOf(body.stage))) delete state.artifacts[stage];
      state.approved_plan = null;
    } else if (path.endsWith('/cancel')) {
      state.runs[0].status = 'cancelled';
      state.active_run = null;
      state.version++;
    } else if (path.endsWith('/evidence'))
      state.evidence = { ...body, provenance: 'self-reported' };
    return route.fulfill({ json: state });
  });
  return { state, calls };
}

async function attach(page: Page) {
  await page.getByLabel('Paper text', { exact: true }).fill(paperText);
  await page.getByRole('button', { name: 'Save paper text', exact: true }).click();
  await expect(page.getByText('Paper saved. Start the analysis when ready.')).toBeVisible();
}
async function run(page: Page, name: string) {
  await page
    .getByRole('button', { name: new RegExp(name) })
    .first()
    .click();
  await page.getByRole('button', { name: 'Run this step', exact: true }).click();
  await expect(page.getByText('A source-grounded test draft.', { exact: true })).toBeVisible();
}

test('guided UI saves a source, approves a plan and regenerates affected work', async ({
  page,
}, info) => {
  const { calls, state } = await mockWorkspace(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/projects/${projectId}/research`);
  await attach(page);
  await run(page, 'Understand the paper');
  await run(page, 'Plan the experiment');
  await page
    .getByRole('button', { name: /Draft the code/ })
    .first()
    .click();
  await expect(page.getByRole('button', { name: 'Run this step' })).toBeDisabled();
  await page
    .getByRole('button', { name: /Plan the experiment/ })
    .first()
    .click();
  await page.getByRole('button', { name: 'Approve this plan' }).click();
  await run(page, 'Draft the code');
  await expect(page.getByText('src/train.py', { exact: true })).toBeVisible();
  await run(page, 'Review the method');
  await page.screenshot({ path: info.outputPath('research-desktop.png'), fullPage: true });
  const originalAnalysis = state.artifacts.analysis?.id;
  await page.getByLabel('What should change?').fill('Use CPU only and report F1.');
  await page.getByRole('button', { name: 'Apply feedback & regenerate' }).click();
  await expect.poll(() => calls.length).toBe(5);
  expect(calls.at(-1)?.feedback).toContain('CPU only');
  expect(state.artifacts.analysis?.id).toBe(originalAnalysis);
  expect(state.artifacts.implementation).toBeUndefined();
  expect(state.approved_plan).toBeNull();
  await page.getByRole('button', { name: 'Ask about the paper', exact: true }).click();
  await page.getByLabel('Your question').fill('What split does the paper use?');
  await page.getByRole('button', { name: 'Ask Groq', exact: true }).click();
  await expect.poll(() => calls.length).toBe(6);
  expect(calls.at(-1)?.stage).toBe('chat');
  await page.reload();
  await expect(page.getByText('Pasted paper', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download project ZIP' })).toHaveAttribute(
    'href',
    `/api/projects/${projectId}/research/export`,
  );
});

test('missing key disables AI; workspace fits small screens', async ({ page }, info) => {
  await mockWorkspace(page, false);
  await page.goto(`/projects/${projectId}/research`);
  await attach(page);
  await page.getByRole('button', { name: /Understand the paper/ }).click();
  await expect(page.getByRole('button', { name: 'Run this step' })).toBeDisabled();
  await expect(
    page.getByText('Configure GROQ_API_KEY on the backend.', { exact: true }),
  ).toBeVisible();
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath('research-mobile.png'), fullPage: true });
});

test('an in-flight AI step can be stopped from the UI', async ({ page }) => {
  const { state } = await mockWorkspace(page, true, true);
  await page.goto(`/projects/${projectId}/research`);
  await attach(page);
  await page.getByRole('button', { name: /Understand the paper/ }).click();
  await page.getByRole('button', { name: 'Run this step' }).click();
  await page.getByRole('button', { name: 'Stop this step' }).click();
  await expect.poll(() => state.active_run).toBeNull();
  expect(state.runs[0].status).toBe('cancelled');
  await expect(page.getByRole('button', { name: 'Run this step' })).toBeEnabled();
});

test('a failed provider call shows its error in the selected stage and allows retry', async ({
  page,
}) => {
  const { state } = await mockWorkspace(page, true, true);
  await page.goto(`/projects/${projectId}/research`);
  await attach(page);
  await page.getByRole('button', { name: /Understand the paper/ }).click();
  await page.getByRole('button', { name: 'Run this step' }).click();
  await expect.poll(() => state.runs.length).toBe(1);
  state.runs[0].status = 'failed';
  state.runs[0].error = 'Groq rate or token limit reached. Wait, then retry this step.';
  state.active_run = null;
  await expect(page.getByRole('alert')).toContainText('Groq rate or token limit reached');
  await expect(page.getByRole('button', { name: 'Run this step' })).toBeEnabled();
});
