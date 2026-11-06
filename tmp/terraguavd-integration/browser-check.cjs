const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require(path.resolve(process.execPath, '../../node_modules/playwright'));

const dist = path.resolve('web/dist');
const contentTypes = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png' };
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  const file = path.resolve(dist, '.' + (url.pathname === '/' ? '/index.html' : url.pathname));
  if (!file.startsWith(dist + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    response.writeHead(404).end();
    return;
  }
  response.setHeader('Content-Type', contentTypes[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(response);
});

async function main() {
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ colorScheme: 'light' });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(url);
    const select = page.getByRole('combobox', { name: 'Appearance theme' });
    const background = () => page.locator('html').evaluate((node) => getComputedStyle(node).backgroundColor);
    assert.equal(await select.inputValue(), 'system');
    assert.equal(await background(), 'rgb(247, 245, 241)');
    await page.locator('.brand-mark').evaluate((img) => img.decode());
    assert.match(await page.locator('.brand-mark').getAttribute('src'), /ivory\.png$/);
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
    assert.equal(await background(), 'rgb(13, 25, 23)');
    await page.locator('.brand-mark').evaluate((img) => img.decode());
    assert.match(await page.locator('.brand-mark').getAttribute('src'), /evergreen\.png$/);
    await select.selectOption('light');
    await page.reload();
    assert.equal(await select.inputValue(), 'light');
    await page.setViewportSize({ width: 375, height: 812 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.setViewportSize({ width: 1280, height: 900 });

    const boundary = { type: 'Polygon', coordinates: [[[8.54,47.39],[8.55,47.39],[8.55,47.4],[8.54,47.39]]] };
    const submitted = {
      current: true, status: 'Pending', mission: { id: 'mission-1', name: 'Adjacent survey' }, operator_username: 'preview-operator',
      request: {
        id: 'request-1', status: 'Pending', requested_at: '2026-11-06T09:00:00Z', reason: 'Adjacent planned work', decision_reason: null,
        snapshot: { assignment: { id: 'area-1', name: 'Assigned sector', boundary, revision: 1 },
          configuration: { id: 'mission-1', name: 'Adjacent survey', boundary, waypoints: [[8.54,47.39],[8.55,47.39]] },
          outside_geometry: boundary, outside_m2: 25 },
      },
    };
    const mutations = [];
    await page.route('https://*.tile.openstreetmap.org/**', (route) => route.abort());
    await page.route('**/api/v1/**', async (route) => {
      const { pathname } = new URL(route.request().url());
      if (route.request().method() === 'POST') mutations.push(pathname);
      let json = [];
      if (pathname.endsWith('/auth/login')) json = { access_token: 'browser-fixture' };
      if (pathname.endsWith('/auth/me')) json = { id: 'sup', username: 'preview-supervisor', role: 'supervisor', permissions: ['missions:approve', 'missions:read'] };
      if (pathname.endsWith('/dashboards/supervisor')) json = { missions: [], potential_detections: [], survey_attempts: [], alerts: [] };
      if (pathname.endsWith('/mission-approvals')) json = [submitted];
      if (pathname.endsWith('/decision')) {
        assert.equal(route.request().postDataJSON().decision, 'Approved');
        submitted.status = 'Approved';
        submitted.request.status = 'Approved';
        json = { request: submitted.request };
      }
      await route.fulfill({ json });
    });
    await page.getByLabel('Username').fill('preview-supervisor');
    await page.getByLabel('Password').fill('local-mock-only');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('button', { name: 'Approvals', exact: true }).click();
    await page.getByLabel('Submitted mission boundary map').waitFor();
    await page.getByRole('button', { name: 'Approve', exact: true }).click();
    await page.getByText('Request approved. No mission was started.').waitFor();
    assert.deepEqual(mutations, ['/api/v1/auth/login', '/api/v1/mission-approvals/request-1/decision']);
    assert.deepEqual(errors, []);
    console.log('Chrome smoke passed: system and manual themes, logo assets, mobile width, and Supervisor decision UI with mocked API.');
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; }).finally(() => server.close());
