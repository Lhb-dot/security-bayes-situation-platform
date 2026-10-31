/**
 * 翻页时的滚动锚定
 * 分页条在列表最下面，用户是滚到页面底部去点它的。换页后新一页可能更长（分页条被推到
 * 视口外），也可能更短（页面高度骤降，浏览器把 scrollTop 夹到新的最大值），两种都会让
 * 分页条从指针下面跑掉。
 */

import { nextTick } from 'vue';
import { SCROLLABLE_OVERFLOW } from '@/utils/scrollChain';

const POSITION_EPSILON_PX = 0.5;

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
  top: number;
  max: number;
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
    const target = bottomGap <= viewport ? nextMax - bottomGap : top;
    const clamped = Math.max(0, Math.min(nextMax, target));
    if (Math.abs(el.scrollTop - clamped) > POSITION_EPSILON_PX) el.scrollTop = clamped;
  }
};

export const keepScroll = async (
  action: () => unknown,
  anchor?: HTMLElement | null,
  isCurrent: () => boolean = () => true,
): Promise<void> => {
  const anchors = capture(anchor);
  try {
    await action();
  } finally {
    if (isCurrent()) {
      restore(anchors);
      await nextTick();
      if (isCurrent()) {
        restore(anchors);
        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
        if (isCurrent()) restore(anchors);
      }
    }
  }
};
