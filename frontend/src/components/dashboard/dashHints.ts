/**
 * 看板「提示性小字」总开关。
 *
 * 统一控制三类提示性小字是否渲染：
 *   1. 页面顶部副标题        —— DashShell.subtitle
 *   2. KPI 卡片口径副标题     —— DashKpis.items[].sub
 *   3. 卡片底部口径来源脚注   —— DashCard.source / DashScatter 内置脚注
 *
 * 当前按需求关闭（演示态界面更干净）。口径文案仍完整保留在各页面的数据里，
 * 需要恢复时把此开关置为 true 即可，无需改动任何页面文件。
 */
export const SHOW_DASH_HINTS = false;
