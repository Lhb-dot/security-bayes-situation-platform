/**
 * 去掉 ARFF / Weka 枚举值最外层的成对引号。
 *
 * 离散化数据集的枚举在 ARFF 里写成 `'\'(-inf-27.755]\''`，Weka 认的值是带引号的
 * `'(-inf-27.755]'`，后端 fields_schema.enum_values 也按这个存（剥掉引号会让
 * Java 侧 `setValue` 匹配不上、静默置缺失）。这层引号对用户没有意义，界面上统一
 * 剥掉显示；`select` 的 `value` 仍绑定带引号的原值，提交给后端的也是原值。
 */
export const stripArffQuotes = (value: unknown): string => {
  const text = String(value ?? '');
  const first = text[0];
  if (text.length >= 2 && first === text[text.length - 1] && (first === "'" || first === '"')) {
    return text.slice(1, -1);
  }
  return text;
};
