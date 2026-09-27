/**
 * scrollAnchor.ts — 翻页时的滚动锚定
 *
 * 分页条在列表最下面，用户是滚到页面底部去点它的。换页后新一页可能更长（分页条被推到
 * 视口外），也可能更短（页面高度骤降，浏览器把 scrollTop 夹到新的最大值）—— 两种都会让
 * 分页条从指针下面跑掉。
 *
 * 所以按「距底部距离」把位置摆回去：换页前分页条在视口里的位置，换页后还是那个位置。
 * 离底部还有一屏以上时（不是在底部操作）保持绝对位置，不硬拉。
 *
 * 用法：
 *   await keepScroll(() => loadReports(target), tableWrapRef.value);
 *   // anchor 传列表容器，滚动发生在内层容器时也能锚住（不传则只锚文档滚动体）
 */

import { nextTick } from 'vue';
// 可滚动判定与 scrollChain.ts 共用同一个正则：hidden 不算（隐藏溢出但不可滚动）
import { SCROLLABLE_OVERFLOW } from '@/utils/scrollChain';

/** 位置差小于半像素就不赋值，避免无意义的 scrollTop 写入触发 scroll 事件 */
const POSITION_EPSILON_PX = 0.5;

/** anchor 自身到根之间的全部滚动容器（含文档滚动体） */
const scrollTargets = (anchor?: HTMLElement | null): HTMLElement[] => {
  const targets: HTMLElement[] = [];
  let node: HTMLElement | null = anchor ?? null;
  while (node) {
    if (SCROLLABLE_OVERFLOW.test(getComputedStyle(node).overflowY)) targets.push(node);
    node = node.parentElement;
  }
  const root = (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
  if (root && !targets.includes(root)) targets.push(root);
  return targets;
};

interface Anchor {
  el: HTMLElement;
  /** 动作前的滚动位置 */
  top: number;
  /** 动作前的可滚动余量（scrollHeight - clientHeight） */
  max: number;
  /** 动作前的容器可视高度，用来判断「是不是贴着底部在操作」 */
  viewport: number;
}

const capture = (anchor?: HTMLElement | null): Anchor[] =>
  scrollTargets(anchor).map((el) => ({
    el,
    top: el.scrollTop,
    max: el.scrollHeight - el.clientHeight,
    viewport: el.clientHeight,
  }));

const restore = (anchors: Anchor[]): void => {
  for (const { el, top, max, viewport } of anchors) {
    const nextMax = el.scrollHeight - el.clientHeight;
    const bottomGap = max - top;
    // 贴着底部操作 → 保持「距底部距离」；离底部还远 → 保持绝对位置
    const target = bottomGap <= viewport ? nextMax - bottomGap : top;
    const clamped = Math.max(0, Math.min(nextMax, target));
    if (Math.abs(el.scrollTop - clamped) > POSITION_EPSILON_PX) el.scrollTop = clamped;
  }
};

export const keepScroll = async (
  action: () => unknown,
  anchor?: HTMLElement | null
): Promise<void> => {
  const anchors = capture(anchor);
  try {
    await action();
  } finally {
    // 三次摆位：动作返回时（DOM 可能还没换）、DOM 更新后、下一帧布局定稿后
    restore(anchors);
    await nextTick();
    restore(anchors);
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    restore(anchors);
  }
};
