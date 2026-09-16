const { chromium } = require('playwright');
const path = require('path');
const OUT = path.resolve(__dirname);
const BASE = 'http://127.0.0.1:5173';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('401')) errors.push('CONSOLE: ' + m.text()); });

  await page.goto(BASE + '/#/login', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.login-field__input', { timeout: 20000 });
  await page.fill('input[placeholder="请输入用户名"]', 'admin');
  await page.fill('input[placeholder="请输入密码"]', '123456');
  await page.click('.login-btn');
  await page.waitForFunction(() => !location.hash.includes('/login'), { timeout: 20000 });

  await page.goto(BASE + '/#/settings', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.settings-tabs', { timeout: 20000 });
  await page.waitForTimeout(1500);

  // ---- 账号与安全 ----
  const acct = await page.$$eval('.settings-panel.is-active .detail-info > div', els =>
    els.map(e => e.textContent.replace(/\s+/g, ' ').trim()));
  console.log('ACCT =', JSON.stringify(acct));
  const pwdBtn = await page.$eval('.settings-panel.is-active .settings-btn', e => ({
    text: e.textContent.trim(),
    bg: getComputedStyle(e).backgroundImage,
    color: getComputedStyle(e).color,
  }));
  console.log('PWD_BTN =', JSON.stringify(pwdBtn));
  await page.screenshot({ path: path.join(OUT, 'v2-account.png'), fullPage: true });

  // ---- 基础设置 ----
  await page.click('.settings-tab:nth-child(2)');
  await page.waitForTimeout(600);
  const genBtns = await page.$$eval('.settings-panel.is-active .settings-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundImage, color: getComputedStyle(e).color })));
  console.log('GENERAL_BTNS =', JSON.stringify(genBtns, null, 1));
  await page.screenshot({ path: path.join(OUT, 'v2-general.png'), fullPage: true });

  // ---- 风险阈值 ----
  await page.click('.settings-tab:nth-child(3)');
  await page.waitForTimeout(900);
  const th = await page.evaluate(() => {
    const p = document.querySelector('.settings-panel.is-active');
    const txt = p.textContent.replace(/\s+/g, ' ').trim();
    return {
      hasSceneCode: /network_security|power_system|geological_risk|flightdeck_operation/.test(txt),
      hasCurrent: txt.includes('当前值'),
      hasRule: txt.includes('要求'),
      head: [...p.querySelectorAll('.threshold-bar__head')].map(e => e.textContent.replace(/\s+/g, ' ').trim()),
      fields: [...p.querySelectorAll('.threshold-field label')].map(e => e.textContent.trim()),
      btn: p.querySelector('.settings-btn')?.textContent.trim(),
    };
  });
  console.log('THRESHOLD =', JSON.stringify(th));
  await page.screenshot({ path: path.join(OUT, 'v2-threshold.png'), fullPage: true });

  // ---- 场景管理 ----
  await page.click('.settings-tab:nth-child(4)');
  await page.waitForTimeout(600);
  const sc = await page.$$eval('.settings-panel.is-active .settings-switches__item', els =>
    els.map(e => ({
      label: e.textContent.trim(),
      on: !!e.querySelector('.settings-switches__toggle.is-on'),
    })));
  console.log('SCENARIO count =', sc.length, JSON.stringify(sc));
  await page.screenshot({ path: path.join(OUT, 'v2-scenario.png'), fullPage: true });

  // ---- 改密弹窗 ----
  await page.click('.settings-tab:nth-child(1)');
  await page.waitForTimeout(400);
  await page.click('.settings-panel.is-active .settings-btn--primary');
  await page.waitForTimeout(700);
  const dlg = await page.evaluate(() => {
    const d = document.querySelector('.pwd-setting-dialog');
    const btns = [...d.querySelectorAll('.el-dialog__footer .el-button')].map(b => ({
      text: b.textContent.trim(), bg: getComputedStyle(b).backgroundImage || getComputedStyle(b).backgroundColor, color: getComputedStyle(b).color,
    }));
    return { visible: !!d && d.offsetParent !== null, btns };
  });
  console.log('PWD_DIALOG =', JSON.stringify(dlg));
  await page.screenshot({ path: path.join(OUT, 'v2-pwd-dialog.png') });

  console.log('ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
