const { chromium } = require('playwright');
const path = require('path');
const OUT = path.resolve(__dirname);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });
  await page.goto('http://127.0.0.1:8791/index.html', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.tabs__nav', { timeout: 15000 });
  await page.waitForTimeout(400);

  const tabs = await page.$$eval('.tabs__item', els => els.map(e => e.textContent.trim()));
  console.log('DEMO TABS =', JSON.stringify(tabs));
  console.log('DEMO hasScenario =', await page.evaluate(() => document.body.innerText.includes('场景启停')));

  const btns = await page.$$eval('.tabpanel.is-active .settings-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundColor, border: getComputedStyle(e).borderColor, color: getComputedStyle(e).color })));
  console.log('DEMO BTNS =', JSON.stringify(btns));

  for (const t of tabs) {
    const idx = tabs.indexOf(t) + 1;
    await page.click(`.tabs__item:nth-child(${idx})`);
    await page.waitForTimeout(400);
    const cards = await page.$$eval('.tabpanel.is-active > section', e => e.length);
    console.log(`  tab "${t}" -> cards=${cards}`);
  }

  await page.click('.tabs__item:nth-child(2)');
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, 'v4-demo-general.png'), fullPage: true });

  console.log('DEMO ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
