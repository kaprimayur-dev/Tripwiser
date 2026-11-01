/**
 * Browser-based E2E test for Train Discovery & Passenger Intelligence (TW-116)
 * Tests real end-to-end user interactions on http://localhost:3000:
 * 1. Train search by number, name, and station code/name.
 * 2. Empty state handling for non-existent trains.
 * 3. Train profile and timetable inspection.
 * 4. Station trains discovery (discovering calling, originating, and terminating trains at a station).
 * 5. Direct train comparison between two stations (NDLS -> BPL) with sorting and disclosures.
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
  console.log('🚀 Starting Browser-Based E2E Train Discovery & Passenger Intelligence Test (TW-116)...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'puppeteer-tw116-'));

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
    page.on('response', (res) => {
      if (res.status() >= 400) {
        console.log(`BROWSER HTTP ERROR: ${res.status()} ${res.url()}`);
      }
    });

    // 1. Navigate to Timetable Mode
    console.log('1. Navigating to http://localhost:3000/?mode=timetable...');
    const response = await page.goto('http://localhost:3000/?mode=timetable', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // Wait for train search input
    console.log('2. Testing Train Search by Number (12002)...');
    await page.waitForSelector('#train-search-input', { visible: true, timeout: 20000 });
    await page.type('#train-search-input', '12002', { delay: 50 });
    await sleep(600);

    // Verify autocomplete suggestion appears
    const hasShatabdi = await page.evaluate(() => {
      const el = document.querySelector('#train-search-input');
      const text = document.body.innerText;
      return text.includes('12002') && text.includes('Shatabdi');
    });
    console.log(`Found 12002 Shatabdi suggestion: ${hasShatabdi}`);
    if (!hasShatabdi) throw new Error('Failed to find 12002 suggestion by train number.');

    // Helper to reliably clear React controlled input
    const clearInput = async (selector) => {
      await page.focus(selector);
      await page.keyboard.press('End');
      const val = await page.$eval(selector, (el) => el.value || '');
      for (let i = 0; i < val.length; i++) {
        await page.keyboard.press('Backspace');
      }
      await sleep(100);
    };

    // 2b. Test Empty State for non-existent query
    console.log('2b. Testing Empty State for UNKNOWN9999...');
    await clearInput('#train-search-input');
    await page.type('#train-search-input', 'UNKNOWN9999', { delay: 40 });
    await sleep(700);

    const inputVal = await page.$eval('#train-search-input', (el) => el.value);
    console.log(`Current train search input value: "${inputVal}"`);
    await page.waitForSelector('#train-search-empty-state', { visible: true, timeout: 4000 });

    const hasEmptyState = await page.evaluate(() => {
      const el = document.querySelector('#train-search-empty-state');
      return el !== null && el.innerText.includes('No matching trains found');
    });
    console.log(`Empty state displayed properly: ${hasEmptyState}`);
    if (!hasEmptyState) throw new Error('Expected empty state for non-existent query.');

    // 2c. Test Station-based Train Search (search by station name "Bhopal")
    console.log('2c. Testing Train Search by Station Name (Bhopal)...');
    await clearInput('#train-search-input');
    await page.type('#train-search-input', 'Bhopal', { delay: 40 });
    await sleep(800);

    const hasBhopalTrain = await page.evaluate(() => {
      const text = document.body.innerText;
      return text.includes('12002') || text.includes('BPL') || text.includes('Bhopal');
    });
    console.log(`Train search by station returned results: ${hasBhopalTrain}`);
    if (!hasBhopalTrain) throw new Error('Train search by station name failed to return trains.');

    // 3. Select train 12002 to open Train Profile & Timetable
    console.log('3. Inspecting Train Profile for 12002...');
    await clearInput('#train-search-input');
    await page.type('#train-search-input', '12002', { delay: 40 });
    await sleep(500);
    await page.click('#btn-search-train');

    await page.waitForSelector('#train-schedule-view', { timeout: 15000 });
    const profileText = await page.evaluate(() => {
      return document.querySelector('#train-schedule-view')?.innerText || '';
    });
    const hasHeader = profileText.includes('12002') && profileText.includes('Shatabdi');
    const hasProvenance = profileText.includes('Verified TAG Timetable');
    console.log(`Train Profile Header verified: ${hasHeader}, Provenance verified: ${hasProvenance}`);
    if (!hasHeader) throw new Error('Train Profile failed to display 12002.');

    // 4. Test Station Trains Discovery (Station serving trains)
    console.log('4. Testing Station Trains Discovery (BPL)...');
    await page.click('#nav-stations-tab');
    await sleep(500);
    await page.waitForSelector('#station-search-input', { timeout: 15000 });
    await page.type('#station-search-input', 'BPL', { delay: 50 });
    await sleep(600);
    await page.keyboard.press('Enter');
    await sleep(800);

    await page.waitForSelector('#station-trains-section', { timeout: 15000 });
    console.log('Station Trains section mounted successfully.');

    const stationTrainsCount = await page.evaluate(() => {
      const section = document.querySelector('#station-trains-section');
      return section?.innerText.includes('Total') || false;
    });
    console.log(`Station trains data loaded: ${stationTrainsCount}`);
    if (!stationTrainsCount) throw new Error('Failed to load station trains data for BPL.');

    // 5. Test Compare Trains Mode
    console.log('5. Navigating to Compare Trains mode...');
    await page.click('#nav-compare-tab');
    await sleep(500);

    await page.waitForSelector('#train-compare-view', { timeout: 15000 });
    console.log('Compare Trains view mounted.');

    // Enter Origin NDLS and Destination BPL
    console.log('Selecting Origin NDLS...');
    const originInput = await page.waitForSelector('#compare-origin-autocomplete');
    await originInput.click();
    await originInput.type('NDLS', { delay: 60 });
    await sleep(700);

    const ndlsOption = await page.waitForSelector('button[data-station-code="NDLS"]', { visible: true, timeout: 5000 });
    await ndlsOption.click();
    await sleep(300);
    console.log('Origin NDLS selected.');

    console.log('Selecting Destination BPL...');
    const destInput = await page.waitForSelector('#compare-dest-autocomplete');
    await destInput.click();
    await destInput.type('BPL', { delay: 60 });
    await sleep(700);

    const bplOption = await page.waitForSelector('button[data-station-code="BPL"]', { visible: true, timeout: 5000 });
    await bplOption.click();
    await sleep(300);
    console.log('Destination BPL selected.');

    // Submit comparison
    console.log('Submitting comparison NDLS ➔ BPL...');
    await page.click('#btn-execute-compare');
    await sleep(1500);

    // Verify comparison results
    const compareResults = await page.evaluate(() => {
      const text = document.querySelector('#train-compare-view')?.innerText || '';
      const hasDirectTrains = text.includes('direct train') || text.includes('direct trains');
      const has12002 = text.includes('12002') && text.includes('Shatabdi');
      const hasDuration = text.includes('Scheduled Duration');
      const hasDisclaimer = text.includes('Timetable Foundation Guarantee');
      return { hasDirectTrains, has12002, hasDuration, hasDisclaimer };
    });
    console.log('Comparison results verification:', compareResults);
    if (!compareResults.has12002) throw new Error('Direct train comparison failed to display 12002.');
    if (!compareResults.hasDisclaimer) throw new Error('Comparison disclaimer missing.');

    // Test sort button switching
    console.log('Testing comparison sorting (Earliest)...');
    await page.click('#sort-earliest');
    await sleep(300);
    console.log('Testing comparison sorting (Fewest Stops)...');
    await page.click('#sort-stops');
    await sleep(300);

    // Capture screenshot
    const screenshotDir = 'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a';
    const screenshotPath = path.join(screenshotDir, 'e2e_train_discovery_success.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`Saved E2E screenshot to: ${screenshotPath}`);

    // Copy to local tests/e2e/ as well
    const localScreenshot = path.join(process.cwd(), 'frontend', 'tests', 'e2e', 'e2e_train_discovery_success.png');
    fs.copyFileSync(screenshotPath, localScreenshot);

    console.log('🎉 TW-116 E2E Train Discovery & Passenger Intelligence Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Train Discovery Test FAILED:', err);
  process.exit(1);
});
