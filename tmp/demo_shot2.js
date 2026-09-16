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

  const acct = await page.$$eval('.tabpanel.is-active .detail-info > div', els =>
    els.map(e => e.textContent.replace(/\s+/g, ' ').trim()));
  console.log('DEMO ACCT =', JSON.stringify(acct));
  const btn = await page.$eval('.tabpanel.is-active .settings-btn', e => ({
    text: e.textContent.trim(), bg: getComputedStyle(e).backgroundImage, color: getComputedStyle(e).color }));
  console.log('DEMO BTN =', JSON.stringify(btn));
  await page.screenshot({ path: path.join(OUT, 'v2-demo-account.png'), fullPage: true });

  // 风险阈值
  await page.click('.tabs__item[data-tab="threshold"]');
  await page.waitForTimeout(400);
  const th = await page.evaluate(() => {
    const p = document.querySelector('.tabpanel.is-active');
    const t = p.textContent.replace(/\s+/g, ' ').trim();
    return { hasSceneCode: /network_security|power_system|geological_risk|flightdeck_operation/.test(t),
             hasCurrent: t.includes('当前值'), hasRule: t.includes('要求'),
             head: [...p.querySelectorAll('.threshold-bar__head')].map(e => e.textContent.replace(/\s+/g,' ').trim()) };
  });
  console.log('DEMO THRESHOLD =', JSON.stringify(th));
  await page.screenshot({ path: path.join(OUT, 'v2-demo-threshold.png'), fullPage: true });

  // 场景管理（4 个）
  await page.click('.tabs__item[data-tab="scenario"]');
  await page.waitForTimeout(400);
  const sc = await page.$$eval('.tabpanel.is-active .settings-switches__item', els => els.map(e => e.textContent.trim()));
  console.log('DEMO SCENARIO =', sc.length, JSON.stringify(sc));
  await page.screenshot({ path: path.join(OUT, 'v2-demo-scenario.png'), fullPage: true });

  console.log('DEMO ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
