const { chromium } = require('playwright');
const path = require('path');
const OUT = path.resolve(__dirname);
const BASE = 'http://127.0.0.1:5173';

/**
 * 库里只有 admin 能登录（其余种子账号 401），因此这里用「改写登录/me 响应里的角色」
 * 的方式模拟另外两级角色，仅用于验证设置页的渲染与可见性逻辑，不写任何数据。
 */
const ROLES = [
  { role: 'SCENARIO_ADMIN', scenario_code: 'network_security', name: 'net_admin' },
  { role: 'SCENARIO_USER', scenario_code: 'network_security', name: 'alice' },
  { role: 'SCENARIO_USER', scenario_code: 'power_system', name: 'bob' },
];

async function rewrite(route, patch) {
  const res = await route.fetch();
  let body;
  try { body = await res.json(); } catch { return route.fulfill({ response: res }); }
  const apply = u => { if (u && typeof u === 'object') Object.assign(u, patch); };
  if (body?.data?.user) apply(body.data.user);
  if (body?.data && body.data.role) apply(body.data);
  await route.fulfill({ response: res, body: JSON.stringify(body) });
}

(async () => {
  const browser = await chromium.launch();
  for (const r of ROLES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
    page.on('console', m => { if (m.type() === 'error' && !m.text().includes('401')) errors.push('CONSOLE: ' + m.text()); });
    const patch = { role: r.role, scenario_code: r.scenario_code, scenario_id: 1, username: r.name };
    await page.route('**/api/v1/auth/login', route => rewrite(route, patch));
    await page.route('**/api/v1/auth/me', route => rewrite(route, patch));

    await page.goto(BASE + '/#/login', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.login-field__input', { timeout: 20000 });
    await page.fill('input[placeholder="请输入用户名"]', 'admin');
    await page.fill('input[placeholder="请输入密码"]', '123456');
    await page.click('.login-btn');
    await page.waitForFunction(() => !location.hash.includes('/login'), { timeout: 20000 });

    await page.goto(BASE + '/#/settings', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.settings-tabs', { timeout: 20000 });
    await page.waitForTimeout(1800);

    const tabs = await page.$$eval('.settings-tab', els => els.map(e => e.textContent.trim()));
    const acct = await page.$$eval('.settings-panel.is-active .detail-info > div', els =>
      els.map(e => e.textContent.replace(/\s+/g, ' ').trim()));
    const nav = await page.$$eval('.nav-tabs__item', els => els.map(e => e.textContent.trim()));

    console.log(`\n### ${r.role} / ${r.scenario_code}`);
    console.log('  NAV  =', JSON.stringify(nav));
    console.log('  TABS =', JSON.stringify(tabs));
    console.log('  ACCT =', JSON.stringify(acct));
    console.log('  hints=', await page.$$eval('.settings-section__hint', e => e.length));

    for (let i = 1; i <= tabs.length; i++) {
      await page.click(`.settings-tab:nth-child(${i})`);
      await page.waitForTimeout(450);
      const kids = await page.$$eval('.settings-panel.is-active > section', e => e.length);
      const th = await page.$$eval('.settings-panel.is-active .threshold-bar__head', els =>
        els.map(e => e.textContent.replace(/\s+/g, ' ').trim()));
      console.log(`  tab${i} "${tabs[i - 1]}" cards=${kids}${th.length ? ' thresholdHead=' + JSON.stringify(th) : ''}`);
    }

    await page.click('.settings-tab:nth-child(1)');
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(OUT, `shot-role-${r.role}-${r.scenario_code}.png`), fullPage: true });
    console.log('  ERRORS =', JSON.stringify(errors));
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
