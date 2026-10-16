import { describe, expect, it } from 'vitest';
import { taxonomyCount } from './landslideTaxonomy';
describe('滑坡细分类统计', () => {
  it('仅汇总明确匹配的原始亚类，未返回的类别显示未知而非零', () => {
    const rows = [{ value: '残积土滑坡', count: 3 }, { value: ' 残积土滑坡 ', count: 2 }, { value: 'landslide', count: 88 }, { value: '泥石流', count: 17 }];
    expect(taxonomyCount(rows, 'residual')).toBe(5);
    expect(taxonomyCount(rows, 'loess')).toBeNull();
    expect(taxonomyCount([], 'fill')).toBeNull();
    expect(taxonomyCount([{ value: '填土滑坡', count: 0 }], 'fill')).toBe(0);
  });
});
