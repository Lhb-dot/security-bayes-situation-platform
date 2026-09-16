const { chromium } = require('playwright');
const path = require('path');

const BASE = 'http://127.0.0.1:5173';
const OUT = path.resolve(__dirname);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text()); });

  // ---------- 登录 ----------
  await page.goto(BASE + '/#/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.login-field__input', { timeout: 20000 });
  await page.fill('input[placeholder="请输入用户名"]', 'admin');
  await page.fill('input[placeholder="请输入密码"]', '123456');
  await page.click('.login-btn');
  await page.waitForFunction(() => !location.hash.includes('/login'), { timeout: 20000 });
  console.log('after login hash =', await page.evaluate(() => location.hash));

  // ---------- 设置页 ----------
  await page.goto(BASE + '/#/settings', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.settings-tabs', { timeout: 20000 });
  await page.waitForTimeout(1200);

  const tabLabels = await page.$$eval('.settings-tab', els => els.map(e => e.textContent.trim()));
  console.log('TABS =', JSON.stringify(tabLabels));

  // 提示文本是否已全部删除
  const hintCount = await page.$$eval('.settings-section__hint', els => els.length);
  console.log('HINT_COUNT =', hintCount);

  // 页面头/账号信息
  const accountRows = await page.$$eval('.settings-panel.is-active .detail-info > div', els =>
    els.map(e => e.textContent.replace(/\s+/g, ' ').trim())
  );
  console.log('ACCOUNT_ROWS =', JSON.stringify(accountRows));

  // 按钮样式
  const btnStyles = await page.$$eval('.settings-panel.is-active .settings-btn', els =>
    els.map(e => ({
      text: e.textContent.trim(),
      bg: getComputedStyle(e).backgroundImage,
      color: getComputedStyle(e).color,
      border: getComputedStyle(e).borderStyle,
    }))
  );
  console.log('BTN_STYLES =', JSON.stringify(btnStyles, null, 1));

  await page.screenshot({ path: path.join(OUT, 'shot-settings-account.png'), fullPage: true });

  // ---------- 基础设置 ----------
  await page.click('.settings-tab:nth-child(2)');
  await page.waitForTimeout(600);
  const generalHints = await page.$$eval('.settings-panel.is-active .settings-section__hint', e => e.length);
  const generalBtns = await page.$$eval('.settings-panel.is-active .settings-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundImage }))
  );
  const aiToggle = await page.$$eval('.settings-panel.is-active .settings-switches__toggle', els => els.length);
  console.log('GENERAL hints =', generalHints, '| btns =', JSON.stringify(generalBtns), '| toggles =', aiToggle);
  await page.screenshot({ path: path.join(OUT, 'shot-settings-general.png'), fullPage: true });

  // ---------- 风险阈值 ----------
  await page.click('.settings-tab:nth-child(3)');
  await page.waitForTimeout(800);
  const thCard = await page.$$eval('.settings-panel.is-active .threshold-bar', els => els.length);
  console.log('THRESHOLD bar =', thCard);
  await page.screenshot({ path: path.join(OUT, 'shot-settings-threshold.png'), fullPage: true });

  // ---------- 场景管理 ----------
  await page.click('.settings-tab:nth-child(4)');
  await page.waitForTimeout(600);
  const scSwitches = await page.$$eval('.settings-panel.is-active .settings-switches__item', els =>
    els.map(e => e.textContent.trim())
  );
  console.log('SCENARIO switches =', JSON.stringify(scSwitches));
  await page.screenshot({ path: path.join(OUT, 'shot-settings-scenario.png'), fullPage: true });

  // ---------- 修改密码弹窗 ----------
  await page.click('.settings-tab:nth-child(1)');
  await page.waitForTimeout(400);
  await page.click('.settings-panel.is-active .settings-btn--primary');
  await page.waitForTimeout(700);
  const pwdDialog = await page.$('.pwd-setting-dialog');
  console.log('PWD_DIALOG_VISIBLE =', !!pwdDialog && await pwdDialog.isVisible());
  await page.screenshot({ path: path.join(OUT, 'shot-settings-pwd-dialog.png') });

  console.log('ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
