const { chromium } = require('playwright');
const path = require('path');
const OUT = path.resolve(__dirname);
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('401')) errors.push('CONSOLE: ' + m.text()); });

  await page.goto(BASE + '/#/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.login-field__input', { timeout: 20000 });
  await page.fill('input[placeholder="请输入用户名"]', 'admin');
  await page.fill('input[placeholder="请输入密码"]', '123456');
  await page.click('.login-btn');
  await page.waitForFunction(() => !location.hash.includes('/login'), { timeout: 20000 });

  await page.goto(BASE + '/#/users', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);

  const btns = await page.$$eval('.users-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundColor, border: getComputedStyle(e).borderColor, color: getComputedStyle(e).color })));
  console.log('USERS-BTN =', JSON.stringify(btns, null, 1));

  // 打开创建账号弹窗，确认弹窗内按钮
  await page.click('.users-btn--primary');
  await page.waitForTimeout(800);
  const dlgBtns = await page.evaluate(() => [...document.querySelectorAll('.el-dialog__footer .el-button')].map(b => ({ text: b.textContent.trim(), bg: getComputedStyle(b).backgroundColor, color: getComputedStyle(b).color })));
  console.log('CREATE DIALOG BTNS =', JSON.stringify(dlgBtns));
  await page.screenshot({ path: path.join(OUT, 'v4-create-dialog.png') });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, 'v4-usermgmt.png'), fullPage: true });

  console.log('ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
