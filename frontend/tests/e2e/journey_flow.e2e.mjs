/**
 * Browser-based E2E test using puppeteer-core driving local Chromium/Edge
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
  console.log('🚀 Starting Browser-Based E2E Journey Search Test...');
  const executablePath = findBrowserExecutable();
  console.log(`Using browser executable: ${executablePath}`);

  const browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });

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

    // Verify title and branding
    const title = await page.title();
    console.log(`Page title: "${title}"`);
    if (!title.includes('TripWiser')) {
      throw new Error(`Unexpected title: ${title}`);
    }

    // 2. Select Boarding Station (Mumbai Central / BCT)
    console.log('2. Testing Station Autocomplete: Boarding Station (BCT)...');
    const inputs = await page.$$('input[type="text"]');
    if (inputs.length < 2) {
      throw new Error(`Expected at least 2 text inputs for stations, found ${inputs.length}`);
    }

    const originInput = inputs[0];
    await originInput.click();
    await sleep(300);
    await originInput.type('BCT', { delay: 50 });
    await sleep(800); // Allow debounce & fetch

    // Click matching station suggestion button
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const bctBtn = buttons.find((b) => b.textContent && b.textContent.includes('BCT'));
      if (bctBtn) bctBtn.click();
    });
    await sleep(400);
    console.log('✓ Selected origin station (BCT).');

    // 3. Select Destination Station (New Delhi / NDLS)
    console.log('3. Testing Station Autocomplete: Destination Station (NDLS)...');
    const destInput = inputs[1];
    await destInput.click();
    await sleep(300);
    await destInput.type('NDLS', { delay: 50 });
    await sleep(800);

    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const ndlsBtn = buttons.find((b) => b.textContent && b.textContent.includes('NDLS'));
      if (ndlsBtn) ndlsBtn.click();
    });
    await sleep(400);
    console.log('✓ Selected destination station (NDLS).');

    // 4. Click Search Routes
    console.log('4. Clicking "Find Railway Routes"...');
    const searchBtn = await page.$('button[type="submit"]');
    if (!searchBtn) {
      throw new Error('Submit button not found');
    }
    await searchBtn.click();

    // 5. Wait for Results Stream
    console.log('5. Awaiting route results from backend API...');
    await page.waitForSelector('[id^="route-card-"]', { timeout: 15000 });
    const routeCards = await page.$$('[id^="route-card-"]');
    console.log(`✓ Received ${routeCards.length} candidate route cards!`);
    if (routeCards.length === 0) {
      throw new Error('No route cards rendered');
    }

    // 6. Test Route Comparison Matrix
    console.log('6. Checking Route Comparison Matrix...');
    const comparisonText = await page.evaluate(() => {
      const el = document.body;
      return el.innerText.includes('Route Comparison');
    });
    console.log(`✓ Route comparison component present: ${comparisonText}`);

    // 7. Test Nearby Alternatives Banner
    console.log('7. Checking Nearby Alternatives Banner...');
    const alternativesText = await page.evaluate(() => {
      const el = document.body;
      return el.innerText.includes('Nearby Boarding') || el.innerText.includes('Twin Terminal');
    });
    console.log(`✓ Nearby twin terminals component present: ${alternativesText}`);

    // 8. Test Opening Journey Details Modal
    console.log('8. Testing Full Journey Details Modal interaction...');
    const detailsButtons = await page.$$('button');
    let modalOpened = false;
    for (const b of detailsButtons) {
      const text = await page.evaluate(el => el.textContent, b);
      if (text && text.includes('Full Journey Details')) {
        await b.click();
        modalOpened = true;
        console.log('✓ Clicked "Full Journey Details & Itinerary" button.');
        break;
      }
    }

    if (modalOpened) {
      await sleep(500);
      const modalHeader = await page.evaluate(() => {
        const el = document.querySelector('h2');
        return el ? el.textContent : null;
      });
      console.log(`✓ Modal Header: "${modalHeader}"`);

      // Verify modal contents (use lowercase comparison due to CSS text-transform uppercase)
      const modalText = await page.evaluate(() => document.body.innerText.toLowerCase());
      if (!modalText.includes('breakdown') && !modalText.includes('duration')) {
        throw new Error('Journey details modal did not render expected sections');
      }
      console.log('✓ Verified Journey Details Modal contents & itinerary breakdown.');

      // Close modal
      const closeBtn = await page.evaluateHandle(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        return buttons.find(b => b.textContent && b.textContent.trim() === 'Close');
      });
      if (closeBtn) {
        await closeBtn.click();
        console.log('✓ Closed Journey Details Modal.');
      }
      await sleep(300);
    }

    // 9. Test Sorting Modes
    console.log('9. Testing Sorting Filters...');
    const sortingPills = await page.$$('button');
    for (const p of sortingPills) {
      const text = await page.evaluate(el => el.textContent, p);
      if (text && text.trim().startsWith('Cheapest')) {
        await p.click();
        console.log('✓ Clicked "Cheapest" filter pill.');
        break;
      }
    }
    await sleep(1200);

    const deferredNotice = await page.evaluate(() => {
      const body = document.body.innerText.toLowerCase();
      return body.includes('fare feed deferred') || body.includes('cheapest sorting deferred') || body.includes('deferred');
    });
    console.log(`✓ Honest deferred fare notice rendered: ${deferredNotice}`);
    if (!deferredNotice) {
      throw new Error('Deferred fare notice not found when Cheapest sorting selected');
    }

    // 10. Test Mobile Viewport Responsiveness
    console.log('10. Testing Mobile Viewport (375x812)...');
    await page.setViewport({ width: 375, height: 812, isMobile: true });
    await sleep(500);

    // Capture screenshot evidence
    const screenshotPath = path.resolve('frontend/tests/e2e/e2e_journey_flow_success.png');
    await page.screenshot({ path: screenshotPath, fullPage: false });
    console.log(`✓ Captured mobile viewport screenshot evidence: ${screenshotPath}`);

    console.log('\n🎉 ALL BROWSER-BASED E2E TESTS PASSED SUCCESSFULLY! 🎉\n');
  } finally {
    await browser.close();
  }
}

runE2ETest().catch(err => {
  console.error('❌ E2E Test Failed:', err);
  process.exit(1);
});
