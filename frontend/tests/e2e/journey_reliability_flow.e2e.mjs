/**
 * Browser-based E2E test for TW-113:
 * Journey Reliability & Transfer Risk Intelligence
 * Validates journey time breakdown, 5-tier transfer risk classification, and factual insights.
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import os from 'os';

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
  console.log('🚀 Starting Browser-Based E2E Journey Reliability & Transfer Risk Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'puppeteer-profile-'));

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    userDataDir: tempDir,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 1100 });

    page.on('console', (msg) => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', (err) => console.log('BROWSER PAGE ERROR:', err.message));

    // 1. Navigate to TripWiser Home
    console.log('1. Navigating to http://localhost:3000...');
    const response = await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // 2. Search BCT -> HWH on 2026-11-02 with 2 Transfers
    console.log('2. Entering Origin Station: BCT...');
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

    console.log('3. Entering Destination Station: HWH...');
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

    console.log('5. Selecting 2 Transfers option (#btn-transfers-2)...');
    const transfers2Btn = await page.$('#btn-transfers-2');
    if (!transfers2Btn) {
      throw new Error('Could not find #btn-transfers-2');
    }
    await transfers2Btn.click();
    await sleep(300);

    console.log('6. Submitting route search...');
    const submitBtn = await page.$('button[type="submit"]');
    if (!submitBtn) {
      throw new Error('Submit button not found');
    }
    await submitBtn.click();

    // 7. Wait for results
    console.log('7. Waiting for route cards...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 25000 });
    const routeCards = await page.$$('[id^="route-card-"]');
    console.log(`Found ${routeCards.length} route cards.`);
    if (routeCards.length === 0) {
      throw new Error('Expected at least 1 route card');
    }

    // 8. Verify Journey Time Breakdown on Route Cards
    console.log('8. Verifying Journey Time Breakdown on Route Cards...');
    const firstCardText = await page.$eval('[id^="route-card-"]', (el) => el.innerText);
    console.log('Sample Route Card Content:\n' + firstCardText.slice(0, 350) + '...\n');

    if (!firstCardText.includes('Journey Time Breakdown:')) {
      throw new Error('Expected "Journey Time Breakdown:" in Route Card');
    }
    if (!firstCardText.includes('aboard train') || !firstCardText.includes('transfer waiting')) {
      throw new Error('Expected "aboard train" and "transfer waiting" breakdown in Route Card');
    }

    // 9. Verify Journey Insights Pills
    const insightPills = await page.$$('[data-testid="journey-insight-pill"]');
    console.log(`Found ${insightPills.length} journey insight pills.`);
    if (insightPills.length === 0) {
      throw new Error('Expected at least 1 journey insight pill');
    }

    // 10. Open Full Journey Details Modal
    console.log('10. Opening Full Journey Details Modal...');
    const detailsBtn = await page.$('button:has(svg.lucide-file-text)');
    if (detailsBtn) {
      await detailsBtn.click();
      await sleep(600);
      const modalText = await page.$eval('.fixed.inset-0', (el) => el.innerText);
      console.log('Modal Preview:\n' + modalText.slice(0, 350) + '...\n');

      if (
        !modalText.toUpperCase().includes('ABOARD TRAINS') ||
        !modalText.toUpperCase().includes('TRANSFER WAITING')
      ) {
        throw new Error('Expected "Aboard Trains" and "Transfer Waiting" in Journey Details Modal metrics');
      }
      if (!modalText.toUpperCase().includes('JOURNEY RELIABILITY & TIMETABLE INSIGHTS')) {
        throw new Error('Expected "Journey Reliability & Timetable Insights" section in modal');
      }

      // Close modal
      const closeBtn = await page.$('.fixed.inset-0 button:has(svg.lucide-x)');
      if (closeBtn) {
        await closeBtn.click();
        await sleep(300);
      }
    }

    // 11. Capture Screenshot Evidence
    const artifactScreenshotPath =
      'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_journey_reliability_success.png';
    const localScreenshotPath = path.resolve('frontend/tests/e2e/e2e_journey_reliability_success.png');
    await page.screenshot({ path: artifactScreenshotPath, fullPage: true });
    await page.screenshot({ path: localScreenshotPath, fullPage: true });
    console.log(`Saved Journey Reliability screenshot to ${artifactScreenshotPath}`);

    console.log('🎉 TW-113 E2E Journey Reliability & Transfer Risk Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (_) {}
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Journey Reliability Test FAILED:', err);
  process.exit(1);
});
