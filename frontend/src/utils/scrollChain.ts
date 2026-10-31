/**
 * 滚轮「向下先外层、向上先内层」的滚动链工具
 * 浏览器默认的滚动链方向是「由内向外」：指针落在内层可滚动区域时，先把内层滚到顶/底，
 * 再把剩余的滚动量交给外层页面。对于「页面里嵌一张定高表格」这类布局，向下滚时这会让用户
 * 在表格上滚动时页面纹丝不动、表格先跑到底，非常反直觉。
 */

export const SCROLLABLE_OVERFLOW = /^(auto|scroll|overlay)$/;

const SCROLL_EPSILON_PX = 1;

const LINE_HEIGHT_PX = 16;

const INNER_SCROLLER_SELECTOR = '.el-scrollbar__wrap, .el-table__body-wrapper';

const isScrollableY = (el: HTMLElement): boolean => {
  if (!SCROLLABLE_OVERFLOW.test(getComputedStyle(el).overflowY)) return false;
  return el.scrollHeight - el.clientHeight > SCROLL_EPSILON_PX;
};

const normalizeDelta = (event: WheelEvent, pageSize: number): number => {
  if (event.deltaMode === 1) return event.deltaY * LINE_HEIGHT_PX;
  if (event.deltaMode === 2) return event.deltaY * pageSize;
  return event.deltaY;
};

const consumeOuterScroll = (start: HTMLElement, delta: number): number => {
  const chain: HTMLElement[] = [];
  let node = start.parentElement;
  while (node && node !== document.body) {
    if (isScrollableY(node)) chain.push(node);
    node = node.parentElement;
  }
  const root = (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
  if (root) chain.push(root);

  let rest = delta;
  for (const el of chain) {
    if (rest === 0) break;
    const max = el.scrollHeight - el.clientHeight;
    if (max <= SCROLL_EPSILON_PX) continue;
    const target = Math.min(Math.max(el.scrollTop + rest, 0), max);
    const applied = target - el.scrollTop;
    if (applied === 0) continue; // 这一层已经到顶/底，继续往外
    el.scrollTop = target;
    rest -= applied;
  }
  return rest;
};

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

export const attachOuterFirstWheel = (wrap: HTMLElement): (() => void) => {
  const onWheel = (event: WheelEvent) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey) return;

    if (event.deltaY <= 0) return;

    const inner = findInnerScroller(wrap, event);
    if (!inner) return;
    const innerMax = inner.scrollHeight - inner.clientHeight;
    if (innerMax <= SCROLL_EPSILON_PX) return;

    const delta = normalizeDelta(event, inner.clientHeight);
    if (delta === 0) return;

    const rest = consumeOuterScroll(wrap, delta);
    event.preventDefault();
    if (rest !== 0) {
      inner.scrollTop = Math.min(Math.max(inner.scrollTop + rest, 0), innerMax);
    }
  };

  wrap.addEventListener('wheel', onWheel, { passive: false });
  return () => wrap.removeEventListener('wheel', onWheel);
};
