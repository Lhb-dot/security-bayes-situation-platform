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

  // ============ 设置页 ============
  await page.goto(BASE + '/#/settings', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.settings-tabs', { timeout: 20000 });
  await page.waitForTimeout(1500);

  const tabs = await page.$$eval('.settings-tab', els => els.map(e => e.textContent.trim()));
  console.log('SETTINGS TABS =', JSON.stringify(tabs));
  const hasScenarioText = await page.evaluate(() => document.body.innerText.includes('场景启停') || document.body.innerText.includes('场景管理'));
  console.log('SETTINGS hasScenarioLayer =', hasScenarioText);

  const btns = await page.$$eval('.settings-panel.is-active .settings-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundColor, border: getComputedStyle(e).borderColor, color: getComputedStyle(e).color })));
  console.log('SETTINGS ACCOUNT BTNS =', JSON.stringify(btns, null, 1));

  await page.click('.settings-tab:nth-child(2)');
  await page.waitForTimeout(600);
  const genBtns = await page.$$eval('.settings-panel.is-active .settings-btn', els =>
    els.map(e => ({ text: e.textContent.trim(), bg: getComputedStyle(e).backgroundColor, border: getComputedStyle(e).borderColor, color: getComputedStyle(e).color })));
  console.log('SETTINGS GENERAL BTNS =', JSON.stringify(genBtns, null, 1));
  await page.screenshot({ path: path.join(OUT, 'v3-settings-general.png'), fullPage: true });

  // 改密弹窗
  await page.click('.settings-tab:nth-child(1)');
  await page.waitForTimeout(300);
  await page.click('.settings-panel.is-active .settings-btn--primary');
  await page.waitForTimeout(700);
  const dlg = await page.evaluate(() => {
    const d = document.querySelector('.pwd-setting-dialog');
    return { visible: !!d && d.offsetParent !== null,
      btns: [...d.querySelectorAll('.el-dialog__footer .el-button')].map(b => ({ text: b.textContent.trim(), bg: getComputedStyle(b).backgroundColor, color: getComputedStyle(b).color })) };
  });
  console.log('PWD DIALOG =', JSON.stringify(dlg));
  await page.screenshot({ path: path.join(OUT, 'v3-pwd-dialog.png') });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // ============ 用户管理 ============
  await page.goto(BASE + '/#/users', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  const um = await page.evaluate(() => {
    const t = document.body.innerText;
    return {
      hasSelfPwd: t.includes('修改本人密码') || t.includes('保存新密码'),
      hasResetPwd: t.includes('重置密码'),
      sections: [...document.querySelectorAll('.users-section h3')].map(e => e.textContent.trim()),
    };
  });
  console.log('USERMGMT =', JSON.stringify(um));
  await page.screenshot({ path: path.join(OUT, 'v3-usermgmt.png'), fullPage: true });

  console.log('ERRORS =', JSON.stringify(errors));
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
