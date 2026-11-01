/**
 * Browser-based E2E test for TW-112:
 * Train Network Intelligence, Interchange Discovery & Multi-Transfer Route Discovery
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';

const CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function findBrowserExecutable() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  throw new Error('No local Chrome or Edge executable found on host system.');
}

async function runE2ETest() {
  console.log('🚀 Starting Browser-Based E2E Network Intelligence & Multi-Transfer Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 1100 });

    page.on('console', (msg) => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', (err) => console.log('BROWSER PAGE ERROR:', err.message));
    page.on('requestfailed', (req) => console.log('REQUEST FAILED:', req.url(), req.failure()?.errorText));
    page.on('response', (res) => {
      if (res.url().includes('/api/')) {
        console.log(`API RESPONSE [${res.status()}]: ${res.url()}`);
      }
    });

    // 1. Navigate to TripWiser Home
    console.log('1. Navigating to http://localhost:3000...');
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    console.log(`Page HTTP status: ${response.status()}`);
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // 2. Select Boarding Station (Mumbai Central / BCT)
    console.log('2. Entering origin station: BCT...');
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length < 2) {
      throw new Error(`Expected at least 2 text inputs for stations, found ${inputs.length}`);
    }
    const originInput = inputs[0];
    await originInput.click();
    await sleep(200);
    await originInput.type('BCT', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bctBtn = buttons.find((b) => b.textContent && b.textContent.includes('BCT'));
      if (bctBtn) bctBtn.click();
    });
    await sleep(400);

    // 3. Select Destination Station (Howrah / HWH)
    console.log('3. Entering destination station: HWH...');
    const destInput = inputs[1];
    await destInput.click();
    await sleep(200);
    await destInput.type('HWH', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const hwhBtn = buttons.find((b) => b.textContent && b.textContent.includes('HWH'));
      if (hwhBtn) hwhBtn.click();
    });
    await sleep(400);

    // 4. Select Date (2026-11-02)
    console.log('4. Setting journey date to 2026-11-02...');
    await page.evaluate(() => {
      const dateInput = document.querySelector('input[type="date"]');
      if (dateInput) {
        dateInput.value = '2026-11-02';
        dateInput.dispatchEvent(new Event('input', { bubbles: true }));
        dateInput.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await sleep(300);

    // 5. Select 2 Transfers
    console.log('5. Selecting 2 Transfers option (#btn-transfers-2)...');
    const transfers2Btn = await page.$('#btn-transfers-2');
    if (!transfers2Btn) {
      throw new Error('Could not find #btn-transfers-2 button');
    }
    await transfers2Btn.click();
    await sleep(300);

    // 6. Submit Search
    console.log('6. Submitting route search...');
    const submitBtn = await page.$('button[type="submit"]');
    if (!submitBtn) {
      throw new Error('Submit button not found');
    }
    await submitBtn.click();

    // 7. Wait for multi-transfer route results
    console.log('7. Waiting for multi-transfer route results...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 25000 });

    const routeCards = await page.$$('[id^="route-card-"]');
    console.log(`Found ${routeCards.length} route cards.`);
    if (routeCards.length === 0) {
      throw new Error('Expected at least 1 route card');
    }

    // Check cards for 2 TRANSFERS badge
    const cardTexts = await page.$$eval('[id^="route-card-"]', (els) => els.map((e) => e.innerText));
    const twoTransferCard = cardTexts.find((t) => t.includes('2 TRANSFERS'));
    if (!twoTransferCard) {
      throw new Error('Expected at least one route card with "2 TRANSFERS" badge on BCT -> HWH');
    }
    console.log('Verified 2-Transfer Route Card:\n' + twoTransferCard.slice(0, 300) + '...\n');

    // 6. Verify Interchange Junctions Card
    console.log('6. Verifying Interchange Junctions Card (#interchange-hubs-section)...');
    await page.waitForSelector('#interchange-hubs-section', { timeout: 10000 });

    // Expand interchanges
    const toggleInterchangesBtn = await page.$('#btn-toggle-interchanges');
    if (toggleInterchangesBtn) {
      await toggleInterchangesBtn.click();
      await sleep(600);
      const hubItems = await page.$$('[data-testid="interchange-hub-item"]');
      console.log(`Discovered ${hubItems.length} verified corridor interchange hubs.`);
      if (hubItems.length === 0) {
        throw new Error('Expected at least 1 interchange hub item');
      }
    }

    // Capture screenshot evidence
    const artifactScreenshotPath = 'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_multi_transfer_success.png';
    const localScreenshotPath = path.resolve('frontend/tests/e2e/e2e_multi_transfer_success.png');
    await page.screenshot({ path: artifactScreenshotPath, fullPage: true });
    await page.screenshot({ path: localScreenshotPath, fullPage: true });
    console.log(`Saved Multi-Transfer & Network screenshot to ${artifactScreenshotPath}`);

    // 7. Verify Regression: Direct search BCT -> NDLS with Direct Only
    console.log('7. Verifying regression: BCT -> NDLS with Direct Only...');
    const destInput2 = (await page.$$('input[type="text"]'))[1];
    await destInput2.focus();
    await page.keyboard.down('Control');
    await page.keyboard.press('A');
    await page.keyboard.up('Control');
    await page.keyboard.press('Backspace');
    await sleep(200);

    await destInput2.type('NDLS', { delay: 50 });
    await sleep(800);
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const ndlsBtn = buttons.find((b) => b.textContent && b.textContent.includes('NDLS'));
      if (ndlsBtn) ndlsBtn.click();
    });
    await sleep(400);

    const transfers0Btn = await page.$('#btn-transfers-0');
    if (transfers0Btn) {
      await transfers0Btn.click();
      await sleep(200);
    }

    const submitBtn2 = await page.$('button[type="submit"]');
    if (submitBtn2) {
      await submitBtn2.click();
    }

    await page.waitForSelector('[id^="route-card-"]', { timeout: 20000 });
    const directCardText = await page.$eval('[id^="route-card-"]', (el) => el.innerText);
    if (!directCardText.includes('DIRECT SERVICE')) {
      throw new Error('Expected DIRECT SERVICE badge on direct BCT -> NDLS query');
    }
    console.log('Direct search regression verified: Direct Service confirmed.');

    console.log('🎉 TW-112 E2E Multi-Transfer & Network Intelligence Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Multi-Transfer Test FAILED:', err);
  process.exit(1);
});
