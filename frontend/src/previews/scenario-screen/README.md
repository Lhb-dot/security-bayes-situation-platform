# 四场景管理员大屏 · 独立设计预览

直接双击、离线打开：`frontend/scenario-screen-preview-standalone.html`。该文件已经内嵌 Vue、ECharts、页面代码和样式，不需要开发服务。修改预览后，在 frontend 目录执行 `node src/previews/scenario-screen/export-standalone.mjs` 重新导出。

`frontend/scenario-screen-preview.html` 是 Vue 开发入口，需要通过下面的开发服务地址访问，不支持直接双击运行。

启动已有前端开发服务后，访问：

http://127.0.0.1:5173/scenario-screen-preview.html

底部四个按钮切换网络安全、电力系统、航保作业、滑坡灾害。右上角支持全屏；图表可悬停查看，图例可切换系列。功能导航仅显示预览提示，不操作业务数据。

本预览使用 `previewData.ts` 的固定演示数据，无需登录和后端。所有文件都在本目录及独立 HTML 入口中，不修改正式 App、路由、页面和接口，也不参考原有 `profile-preview.html`。

以 1440×900 设计，同时适配 1366×768 和 1920×1080。一屏包含核心指标、场景专属图表、口径治理、数据台账、建模覆盖、事件处置、活动趋势和成员概况。数据规模按内容分组去重，台账按物理文件展示；灾害编目与运行事件分开标注。

等待设计确认后，再考虑真实接口、权限与正式首页接入。

已有接口支持范围详见 [BACKEND_SUPPORT.md](./BACKEND_SUPPORT.md)。电参量、地质因子、端口显示和成员范围遵循当前实现。管理员总数因当前用户接口不提供而移除，底部只展示场景用户的注册、启用和停用数量。

2026-10-16 新增滑坡分类画像设计探索：地质页中央使用“组成物质 → 亚类”的分类谱系，配合“类型 × 规模”交叉矩阵。点击分类节点可联动左侧诱因、规模结构。独立演示模型位于 `landslideDesign.ts`，不混入既有接口类型。分类名称参考自然资源部门资料，分类标注、样本量及联合分布均尚未完成真实数据核验，也不表示现有后端已支持这些联合统计。

滑坡页直达离线文件：`frontend/scenario-screen-preview-geological-standalone.html`。导出命令：`node src/previews/scenario-screen/export-standalone.mjs scenario-screen-preview.html geological`。该文件默认打开滑坡页，也可切换其他场景。

土质亚类（残积土、黄土、填土）及岩质亚类（顺层、切层）的名称参考：[大同市规划和自然资源局公开资料](https://zrzy.dt.gov.cn/dtsghhzrzyjzz/sjdt/202306/010709e6a08f43378b2e4c5c8bd99582/files/16ac25bee2bd40a9902cce7a7ef4ebfc.pdf)。两级分类依据在图中单独标明，不将规模或诱因混为类型。
