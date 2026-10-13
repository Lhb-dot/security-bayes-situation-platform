/**
 * 本文件由 scripts/gen_quick_login_accounts.py 从数据库（app_user / scenario）生成，请勿手改。
 * 生成时间：2026-10-12 23:49:19
 * 重新生成：python scripts/gen_quick_login_accounts.py
 */
import type { UserRole } from '@/types/security';

export interface DevQuickAccount {
  username: string;
  role: UserRole;
  /** 库里该账号 password_hash 能通过校验的口令 */
  password: string;
}

export interface DevQuickScenario {
  code: string;
  name: string;
  accounts: DevQuickAccount[];
}

export const DEV_QUICK_SUPER_ADMINS: DevQuickAccount[] = [
  { username: 'admin', role: 'SUPER_ADMIN', password: '123456' },
];

export const DEV_QUICK_SCENARIOS: DevQuickScenario[] = [
  {
    code: 'network_security',
    name: '网络安全态势',
    accounts: [
      { username: 'net_admin', role: 'SCENARIO_ADMIN', password: '123456' },
      { username: 'alice', role: 'SCENARIO_USER', password: '123456' },
      { username: 'net_user01', role: 'SCENARIO_USER', password: '123456' },
      { username: 'net_user02', role: 'SCENARIO_USER', password: '123456' },
      { username: 'net_user03', role: 'SCENARIO_USER', password: '123456' },
    ],
  },
  {
    code: 'power_system',
    name: '电力系统态势',
    accounts: [
      { username: 'power_admin', role: 'SCENARIO_ADMIN', password: '123456' },
      { username: 'bob', role: 'SCENARIO_USER', password: '123456' },
      { username: 'power_user01', role: 'SCENARIO_USER', password: '123456' },
      { username: 'power_user02', role: 'SCENARIO_USER', password: '123456' },
      { username: 'power_user03', role: 'SCENARIO_USER', password: '123456' },
    ],
  },
  {
    code: 'flightdeck_operation',
    name: '舰面调度态势',
    accounts: [
      { username: 'zs', role: 'SCENARIO_ADMIN', password: '123456' },
      { username: 'deck_user01', role: 'SCENARIO_USER', password: '123456' },
      { username: 'deck_user02', role: 'SCENARIO_USER', password: '123456' },
      { username: 'deck_user03', role: 'SCENARIO_USER', password: '123456' },
      { username: 'deck_user04', role: 'SCENARIO_USER', password: '123456' },
    ],
  },
  {
    code: 'geological_risk',
    name: '地质风险态势',
    accounts: [
      { username: 'geo_admin', role: 'SCENARIO_ADMIN', password: '123456' },
      { username: 'carol', role: 'SCENARIO_USER', password: '123456' },
      { username: 'geo_user01', role: 'SCENARIO_USER', password: '123456' },
      { username: 'geo_user02', role: 'SCENARIO_USER', password: '123456' },
      { username: 'geo_user03', role: 'SCENARIO_USER', password: '123456' },
    ],
  },
];
