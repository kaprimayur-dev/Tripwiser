/**
 * Browser-based E2E test for Station Intelligence & Nearby Station Discovery (TW-111)
 * Tests real end-to-end user interactions on http://localhost:3000
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
  console.log('🚀 Starting Browser-Based E2E Station Intelligence & Discovery Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 1000 });

    page.on('console', (msg) => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', (err) => console.log('BROWSER PAGE ERROR:', err.message));

    // 1. Navigate to TripWiser Station Discovery mode
    console.log('1. Navigating to http://localhost:3000/?mode=stations...');
    const response = await page.goto('http://localhost:3000/?mode=stations', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    console.log(`Page HTTP status: ${response.status()}`);
    if (response.status() !== 200) {
      throw new Error(`Expected HTTP 200, got ${response.status()}`);
    }

    // Wait for hydration and search input
    console.log('2. Waiting for #station-search-input to mount...');
    await page.waitForSelector('#station-search-input', { timeout: 15000 });
    console.log('Station search input mounted successfully.');

    // 3. Search Station "BPL"
    console.log('3. Searching for Station "BPL" (Bhopal Jn)...');
    const stationInput = await page.$('#station-search-input');
    if (!stationInput) {
      throw new Error('Could not find #station-search-input field');
    }
    await stationInput.click();
    await stationInput.type('BPL', { delay: 60 });
    await sleep(800); // Allow debounce & fetch

    // Wait for dropdown suggestion
    const suggestion = await page.$('#station-suggestion-0');
    if (suggestion) {
      const suggestionText = await page.$eval('#station-suggestion-0', el => el.innerText);
      console.log(`Top suggestion: ${suggestionText.trim()}`);
      if (!suggestionText.includes('BPL')) {
        throw new Error(`Expected BPL in top suggestion, got: ${suggestionText}`);
      }
      await suggestion.click();
    } else {
      console.log('Submitting station search input directly with Enter...');
      await page.keyboard.press('Enter');
    }

    // 4. Wait for #station-detail-view to render
    console.log('4. Waiting for #station-detail-view to render...');
    await page.waitForSelector('#station-detail-view', { timeout: 15000 });

    const detailText = await page.$eval('#station-detail-view', (el) => el.innerText);
    console.log('Station Detail View Sample Snippet:\n' + detailText.slice(0, 350) + '...\n');

    if (!detailText.includes('BPL') && !detailText.includes('BHOPAL')) {
      throw new Error('Detail view missing station code or name BPL/BHOPAL');
    }
    if (!detailText.includes('23.26') || !detailText.includes('77.41')) {
      throw new Error('Detail view missing geodetic coordinates (23.26, 77.41)');
    }
    if (!detailText.includes('TIMETABLE SCHEDULE COVERAGE')) {
      throw new Error('Detail view missing verified coverage metrics section');
    }
    if (!detailText.includes('Timetable Verified')) {
      throw new Error('Detail view missing verified coverage status badge');
    }

    // 5. Verify PostGIS Nearby Stations
    console.log('5. Verifying PostGIS Nearby Stations list...');
    await page.waitForSelector('#nearby-station-card-0', { timeout: 10000 });
    const nearbyStation0 = await page.$eval('#nearby-station-card-0', (el) => el.innerText);
    console.log(`First nearby station card:\n${nearbyStation0}\n`);

    if (!nearbyStation0.includes('km')) {
      throw new Error('Nearby station card does not display distance in km');
    }

    // 6. Test Radius Selector (Switch to 50 km)
    console.log('6. Testing radius selector (switching to 50 km)...');
    const radiusBtn50 = await page.$('#radius-btn-50');
    if (radiusBtn50) {
      await radiusBtn50.click();
      await sleep(1000);
      console.log('Successfully switched to 50 km radius.');
    } else {
      throw new Error('Could not find #radius-btn-50');
    }

    // Capture screenshot of Station Discovery view
    const artifactScreenshotPath = 'C:\\Users\\MAYUR\\.gemini\\antigravity\\brain\\d912be4a-adb8-4eeb-ad55-3fcedf5ab70a\\e2e_station_discovery_success.png';
    const localScreenshotPath = path.resolve('frontend/tests/e2e/e2e_station_discovery_success.png');
    await page.screenshot({ path: artifactScreenshotPath, fullPage: true });
    await page.screenshot({ path: localScreenshotPath, fullPage: true });
    console.log(`Saved Station Discovery screenshot to ${artifactScreenshotPath}`);

    // 7. Test 1-Click Action: "Set as Origin"
    console.log('7. Testing 1-click "Set as Origin" from nearby station card...');
    const setOriginBtn = await page.$('#btn-set-origin-0');
    if (!setOriginBtn) {
      throw new Error('Could not find #btn-set-origin-0 button');
    }
    await setOriginBtn.click();
    await sleep(1000);

    // Verify switched to connecting mode and search origin input is populated
    await page.waitForSelector('#tab-connecting-mode', { timeout: 5000 });
    const textInputs = await page.$$('input[type="text"]');
    if (textInputs.length === 0) {
      throw new Error('No input fields found after transitioning to connecting mode');
    }
    const originInputValue = await textInputs[0].evaluate((el) => el.value);
    console.log(`Switched to connecting mode with origin input value: "${originInputValue}"`);
    if (!originInputValue) {
      throw new Error('Origin input was not pre-populated after clicking "Set as Origin"');
    }

    // 8. Test Deep-Linking URL query parameter: ?mode=stations&station=GWL
    console.log('8. Testing deep-link URL ?mode=stations&station=GWL...');
    await page.goto('http://localhost:3000/?mode=stations&station=GWL', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    await page.waitForSelector('#station-detail-view', { timeout: 15000 });
    const gwlDetailText = await page.$eval('#station-detail-view', (el) => el.innerText);
    if (!gwlDetailText.includes('GWL') && !gwlDetailText.includes('GWALIOR')) {
      throw new Error('Deep-linked GWL station detail view failed to load');
    }
    console.log('Deep-link URL ?mode=stations&station=GWL successfully loaded Gwalior Jn details.');

    console.log('🎉 E2E Station Intelligence & Discovery Test PASSED COMPLETELY!');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch((err) => {
  console.error('❌ E2E Station Discovery Test FAILED:', err);
  process.exit(1);
});
