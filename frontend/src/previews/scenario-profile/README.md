# 四场景详情页设计预览

当前是待评审的第一版，使用示例数据，不连接业务接口。

启动前端开发服务后打开 `/profile-preview.html`，底部按钮可切换四个场景：

- `/profile-preview.html?scene=network`
- `/profile-preview.html?scene=power`
- `/profile-preview.html?scene=flightdeck`
- `/profile-preview.html?scene=geological`

入口为 `frontend/src/profile-preview.ts`。组件与样式仅由独立预览入口引用，不接入正式路由或正式首页。

后续流程：仅在预览中调整设计，设计定稿后再修改正式场景页面。正式页面入口及四个场景组件已恢复为此次改版前的版本。

已知第一版仍需调整图表比例、长名称和窄屏布局；当前为设计过程稿，非最终交付版本。
