/**
 * scrollChain.ts — 滚轮「向下先外层、向上先内层」的滚动链工具
 *
 * 浏览器默认的滚动链方向是「由内向外」：指针落在内层可滚动区域时，先把内层滚到顶/底，
 * 再把剩余的滚动量交给外层页面。对于「页面里嵌一张定高表格」这类布局，向下滚时这会让用户
 * 在表格上滚动时页面纹丝不动、表格先跑到底，非常反直觉。
 *
 * 本工具只反转**向下**的方向：
 *   - 向下滚（deltaY > 0）：先把外层页面滚到底，剩余滚动量才落到内层区域；
 *   - 向上滚（deltaY < 0）：完全交还浏览器默认 —— 内层先滚回顶部，到顶后再链式滚回页面。
 * 这样向下时页面不会被表格「卡住」，向上时表格内容也随时能原路滚回去。
 *
 * 用法：
 *   const detach = attachOuterFirstWheel(wrapEl);
 *   onBeforeUnmount(detach);
 */

/** 只有这几个 overflow 值才算「可滚动容器」，hidden 不算（隐藏溢出但不可滚动） */
const SCROLLABLE_OVERFLOW = /^(auto|scroll|overlay)$/;

/** 内层滚动容器的候选选择器：Element Plus 表格真正的滚动体在 el-scrollbar 的 wrap 上 */
const INNER_SCROLLER_SELECTOR = '.el-scrollbar__wrap, .el-table__body-wrapper';

/** 元素自身是否是可纵向滚动的容器（overflow 允许滚动，且内容确实溢出） */
const isScrollableY = (el: HTMLElement): boolean => {
  if (!SCROLLABLE_OVERFLOW.test(getComputedStyle(el).overflowY)) return false;
  return el.scrollHeight - el.clientHeight > 1;
};

/** 归一化滚轮位移为像素：行模式/页模式的浏览器给出的不是像素值 */
const normalizeDelta = (event: WheelEvent, pageSize: number): number => {
  if (event.deltaMode === 1) return event.deltaY * 16;
  if (event.deltaMode === 2) return event.deltaY * pageSize;
  return event.deltaY;
};

/**
 * 从内向外依次消费滚动位移（先近后远、每层滚到边界再继续往外），
 * 返回没有被任何外层消费掉的余量。
 */
const consumeOuterScroll = (start: HTMLElement, delta: number): number => {
  const chain: HTMLElement[] = [];
  let node = start.parentElement;
  while (node && node !== document.body) {
    if (isScrollableY(node)) chain.push(node);
    node = node.parentElement;
  }
  // 文档滚动体（html）不参与 overflow 计算，需要显式补进链条末尾
  const root = (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
  if (root) chain.push(root);

  let rest = delta;
  for (const el of chain) {
    if (rest === 0) break;
    const max = el.scrollHeight - el.clientHeight;
    if (max <= 1) continue;
    const target = Math.min(Math.max(el.scrollTop + rest, 0), max);
    const applied = target - el.scrollTop;
    if (applied === 0) continue; // 这一层已经到顶/底，继续往外
    el.scrollTop = target;
    rest -= applied;
  }
  return rest;
};

/**
 * 找内层真正的滚动容器：优先按指针命中的元素向上找（最准确）；
 * 指针落在表头等不可滚动死区时，按结构在容器内兜底查找。
 */
const findInnerScroller = (wrap: HTMLElement, event: WheelEvent): HTMLElement | null => {
  const hit = document.elementFromPoint(event.clientX, event.clientY);
  let node: HTMLElement | null = hit instanceof HTMLElement ? hit : null;
  while (node && node !== wrap) {
    if (isScrollableY(node)) return node;
    node = node.parentElement;
  }
  const candidates = Array.from(wrap.querySelectorAll<HTMLElement>(INNER_SCROLLER_SELECTOR));
  for (const candidate of candidates) {
    if (isScrollableY(candidate)) return candidate;
  }
  return null;
};

/**
 * 给内层滚动区域挂上「向下先外层、向上先内层」的滚轮处理。
 *
 * @param wrap 内层滚动容器的外层包裹元素（滚轮事件在该元素上监听）
 * @returns 卸载函数，组件销毁时调用
 */
export const attachOuterFirstWheel = (wrap: HTMLElement): (() => void) => {
  const onWheel = (event: WheelEvent) => {
    // 缩放（Ctrl/⌘+滚轮）与横向滚动（Shift+滚轮）保持浏览器默认行为
    if (event.ctrlKey || event.metaKey || event.shiftKey) return;

    // 向上滚动不接管：交还浏览器默认的「内层优先」——
    // 表格先滚回顶部，表格到顶后由原生链式滚动把剩余量给页面。
    if (event.deltaY <= 0) return;

    const inner = findInnerScroller(wrap, event);
    if (!inner) return;
    const innerMax = inner.scrollHeight - inner.clientHeight;
    if (innerMax <= 1) return;

    const delta = normalizeDelta(event, inner.clientHeight);
    if (delta === 0) return;

    // 向下时外层先吃：页面还有余量就滚页面，页面到底后余量才给内层。
    // 这里对「余量」始终自己处理、不交还浏览器原生滚动 —— 页面被推动后表格会从指针
    // 下方移开，交给原生滚动就会因为命中点已不在滚动体上而整个失效。
    const rest = consumeOuterScroll(wrap, delta);
    event.preventDefault();
    if (rest !== 0) {
      inner.scrollTop = Math.min(Math.max(inner.scrollTop + rest, 0), innerMax);
    }
  };

  wrap.addEventListener('wheel', onWheel, { passive: false });
  return () => wrap.removeEventListener('wheel', onWheel);
};
