import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { mkdirSync } from 'node:fs';

const root = path.resolve(__dirname, '../..');
const data = path.join(root, '.cache/e2e');
mkdirSync(data, { recursive: true });
process.env['PLAYWRIGHT_BROWSERS_PATH'] = path.join(root, '.cache/ms-playwright');
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4201', trace: 'retain-on-failure' },
  // Opt in only with dedicated test servers/database, never a real workspace database.
  webServer:
    process.env['PAPERLAB_E2E_EXTERNAL_SERVER'] === '1'
      ? undefined
      : {
          command: 'node ../../scripts/dev.cjs',
          url: 'http://127.0.0.1:4201',
          timeout: 120000,
          env: {
            PAPERLAB_API_PORT: '8001',
            PAPERLAB_WEB_PORT: '4201',
            PAPERLAB_DATABASE_URL: `sqlite:///${path.join(data, `test-${Date.now()}.db`).replaceAll('\\', '/')}`,
            NG_CLI_ANALYTICS: 'false',
          },
        },
});
