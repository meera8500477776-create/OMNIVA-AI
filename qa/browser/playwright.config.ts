import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const frontendDir = resolve(process.env.OMNIVA_FRONTEND_DIR ?? '../../frontend');
if (!existsSync(resolve(frontendDir, 'package.json')) || !existsSync(resolve(frontendDir, 'src/App.tsx'))) {
  throw new Error('Frontend source is missing at ' + frontendDir + '. Browser suite is BLOCKED; it will not pass against an absent app.');
}

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  timeout: 45_000,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['line'], ['junit', { outputFile: 'test-results/junit.xml' }], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1440, height: 1000 },
    launchOptions: executablePath ? { executablePath } : undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    ...devices['Desktop Chrome'],
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'pnpm exec vite --host 127.0.0.1 --port 4173 --strictPort',
    cwd: frontendDir,
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: { VITE_APP_MODE: 'demo', VITE_API_BASE_URL: 'http://127.0.0.1:9/api/v1' },
  },
});
