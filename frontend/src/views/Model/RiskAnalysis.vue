<script setup lang="ts">
/**
 * RiskAnalysis - 模型训练（数据库化版）
 *
 * 需求 6.3.1（管理员闭环）：选择场景 → 数据集版本 → 算法 → 配置训练参数 → 启动训练
 * 需求 6.6：算法代码注册（A2WNB/MAWNB/EMAWNB/CAVWNB/PMWNB）+ 动态参数配置表单
 *   - 场景 / 数据集 / 算法 全部从 /api/v1 数据库渲染，不再使用 mock
 *   - 训练参数表单由算法注册的 param_schema 动态生成（需求 6.6.3）
 * 需求 6.7.2：训练成功生成 DRAFT 模型版本（待管理员在模型中心审核发布）
 * 需求 6.5.2：仅管理员可训练；场景用户只能使用已发布模型执行推理
 *
 * 训练执行策略（后端 /api/v1/model-versions/train-async）：提交后立刻返回 TRAINING 版本，
 * 真实训练由服务端 training_runner 在后台线程调 Java/Weka 执行。轮询与完成通知都放在
 * trainingJobStore（不是本组件），所以离开页面训练照跑、完成时全局弹通知、刷新后靠
 * resumePending 接回来 —— 页面只负责提交，**不展示训练结果**。
 * 页面参数来自 algorithm.param_schema，并随训练请求传入服务。
 *
 * 训练是异步长任务，页面**不显示已用秒数**：秒表跳动给不出可用信息（耗时长短由样本量决定，
 * 不在前端掌控），提交后按钮变「训练中」，完成 / 失败由全局通知给出。store 里仍按真实时间差
 * 维护 elapsed（顶栏任务面板在用），本页不读它。
 *
 * **本页没有结果面板**：训练动辄数分钟，用户基本不会守在这一页；完成后从顶栏任务铃铛
 * （消息中心）进模型中心看结果，所以这里既不回填 evaluation_metrics、也不提供跳转按钮。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { AlgorithmParamDef } from '@/types/security';
import { useUserStore } from '@/stores/userStore';
import { useTrainingJobStore } from '@/stores/trainingJobStore';
import { getScenarios, getDatasets, getAlgorithms, trainModelAsync } from '@/api/trainingApi';
import { ElMessage } from 'element-plus';

const router = useRouter();
const userStore = useUserStore();

// ===================== 权限 =====================
// 直接读 store getter，不再在 onMounted 里拷一份 ref 快照：快照只有在
// 「main.ts 先 await bootstrap() 再装路由」这条隐式顺序成立时才对，
// 顺序一旦变化（或组件在别处被提前挂载）就会把管理员误判成场景用户。
const currentUser = computed(() => userStore.currentUser);
const isManagement = computed(() => userStore.isManagement);

// ===================== 场景（数据库） =====================
interface DbScenario {
  id: number;
  code: string;
  name: string;
  access_status: string;
}
const scenarios = ref<DbScenario[]>([]);
const scenarioOptions = computed(() =>
  scenarios.value.filter((s) => s.access_status === 'ACTUAL')
);
const selectedScenario = ref<number | ''>('');

// ===================== 数据集（数据库） =====================
interface DbDataset {
  id: number;
  logical_id: string;
  name: string;
  version: number;
  status: string;
  file_path: string;
  fields_schema: unknown[];
}
const datasetList = ref<DbDataset[]>([]);
const selectedDatasetId = ref<number | ''>('');
const loadingDatasets = ref(false);

// ===================== 算法（数据库 + param_schema 动态表单） =====================
interface AlgoOption {
  id: number;
  display_name: string;
  available: boolean;
  params: AlgorithmParamDef[];
}
const algorithms = ref<AlgoOption[]>([]);
const selectedAlgoId = ref<number | ''>('');

/** 后端 param_schema（name/type/enum/options）→ 前端 AlgorithmParamDef 渲染模型 */
const mapBackendParams = (schema: unknown[]): AlgorithmParamDef[] => {
  if (!Array.isArray(schema)) return [];
  return schema.map((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>;
    let type: AlgorithmParamDef['type'];
    switch (item.type) {
      // 后端 validate_params_schema 认的数值型是 int|integer|float|number
      // （见 backend/app/utils/common.py），此前只列了 int/float，
      // 注册成 integer/number 的算法会被当成字符串渲染成文本框
      case 'int':
      case 'integer':
      case 'float':
      case 'number':
        type = 'number';
        break;
      case 'bool':
        type = 'boolean';
        break;
      case 'enum':
        type = 'select';
        break;
      default:
        type = 'string';
    }
    return {
      param_name: String(item.name ?? ''),
      label: String(item.label ?? item.name ?? ''),
      type,
      default_value: (item.default as AlgorithmParamDef['default_value']) ?? '',
      min: item.min as number | undefined,
      max: item.max as number | undefined,
      step: item.step as number | undefined,
      options: Array.isArray(item.options)
        ? (item.options as { value: string; label: string }[])
        : Array.isArray(item.enum_values)
          ? (item.enum_values as string[]).map((v) => ({ value: v, label: v }))
          : undefined,
      description: String(item.description ?? ''),
      requires_numeric_features: Boolean(item.requires_numeric_features),
    };
  });
};

/** 当前算法定义 */
const currentAlgo = computed(() => algorithms.value.find((a) => a.id === selectedAlgoId.value));

/** 数据集字段结构里的数值型 type 取值（与后端 NUMERIC_FIELD_TYPES 对齐） */
const NUMERIC_FIELD_TYPES = ['numeric', 'real', 'float', 'double', 'int', 'integer', 'number'];

/** 当前所选数据集是否含数值特征：决定离散化参数是否适用 */
const datasetHasNumericFeatures = computed(() => {
  const ds = datasetList.value.find((d) => d.id === selectedDatasetId.value);
  if (!ds || !Array.isArray(ds.fields_schema)) return false;
  return ds.fields_schema.some((raw) => {
    const f = (raw ?? {}) as Record<string, unknown>;
    return f.role === 'feature' && NUMERIC_FIELD_TYPES.includes(String(f.type ?? '').toLowerCase());
  });
});

/** 训练参数表单实际展示的参数：不适用于当前数据集的参数不出现 */
const visibleParams = computed(() => {
  const params = currentAlgo.value?.params ?? [];
  if (datasetHasNumericFeatures.value) return params;
  return params.filter((p) => !p.requires_numeric_features);
});

/** 训练参数表单（动态生成，默认值来自算法 param_schema，需求 6.6.3） */
const paramForm = ref<Record<string, number | string | boolean>>({});

const algoNameById = (id: number) => algorithms.value.find((a) => a.id === id)?.display_name ?? String(id);
const scenarioNameById = (id: number) => scenarios.value.find((s) => s.id === id)?.name ?? String(id);

// ===== 训练状态（数据源在 store：离开页面后台照样跑，完成时全局通知） =====
// 页面只取「在跑 / 不在跑」这一位信息 —— 秒数不显示（见文件头注释），所以不读 activeJob.elapsed。
const trainingJobStore = useTrainingJobStore();
const activeJob = computed(() => trainingJobStore.activeJob);
const training = computed(() => Boolean(activeJob.value));

/** 提交训练后返回的模型版本行（trainingApi 为 JS 模块无类型，本页只用到 id） */
interface ModelVersionRow {
  id: number;
}

// ===================== 场景切换 → 加载数据集 =====================
/** 竞态令牌：连着切两个场景时只认最后一次请求的结果。否则先发出的旧场景请求
 *  后返回，会把旧场景的数据集盖在新场景上，训练就成了「B 场景 + A 场景数据集」 */
let datasetToken = 0;

watch(selectedScenario, async (scenario) => {
  const token = ++datasetToken;
  selectedDatasetId.value = '';
  if (!scenario) {
    datasetList.value = [];
    // 作废在途请求（它的 finally 不会再动这个标志），避免遮罩一直转
    loadingDatasets.value = false;
    return;
  }
  loadingDatasets.value = true;
  try {
    const list = await getDatasets(scenario);
    if (token !== datasetToken) return; // 期间又切了场景，这批数据已过期
    datasetList.value = list;
    // 下拉框不留「请选择」占位项：有数据集就直接落到第一条，选中的那个就是真实值。
    selectedDatasetId.value = list.length ? list[0].id : '';
  } catch {
    if (token !== datasetToken) return;
    datasetList.value = [];
  } finally {
    // 只有最新那次请求负责收尾，过期的请求不能把加载态关掉
    if (token === datasetToken) loadingDatasets.value = false;
  }
});

// ===================== 算法/数据集切换 → 重建参数表单 =====================
const resetParamForm = () => {
  paramForm.value = {};
  for (const p of visibleParams.value) {
    paramForm.value[p.param_name] = p.default_value;
  }
};

watch(selectedAlgoId, resetParamForm);

// 数据集切换会改变参数的适用性（离散化参数对纯离散数据集不适用），表单需一并重建。
watch(datasetHasNumericFeatures, resetParamForm);

// ===================== 模型训练 =====================
/** 通知文案里的任务名：场景 · 算法 */
const trainJobTitle = computed(() => {
  const scenario = selectedScenario.value ? scenarioNameById(Number(selectedScenario.value)) : '';
  const algo = selectedAlgoId.value ? algoNameById(Number(selectedAlgoId.value)) : '';
  return [scenario, algo].filter(Boolean).join(' · ') || '模型训练';
});

const handleTrain = async () => {
  if (!selectedScenario.value) {
    ElMessage.warning('请先选择业务场景');
    return;
  }
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择数据集版本');
    return;
  }
  if (!selectedAlgoId.value) {
    ElMessage.warning('请选择训练算法');
    return;
  }

  try {
    // 只提交表单上真实展示的参数，避免把不适用于当前数据集的参数带进训练请求。
    const training_parameters: Record<string, number | string | boolean> = {};
    for (const p of visibleParams.value) {
      if (p.param_name in paramForm.value) training_parameters[p.param_name] = paramForm.value[p.param_name];
    }
    const submitted: ModelVersionRow = await trainModelAsync({
      scenario_id: selectedScenario.value,
      dataset_id: selectedDatasetId.value,
      algorithm_id: selectedAlgoId.value,
      training_parameters,
    });
    // 提交即返回：训练交给服务端后台线程，页面只留一条「训练中」，完成时全局弹通知。
    // 用户离开本页不会中断训练，也不会在页面上留下结果 —— 结果统一在模型中心看。
    trainingJobStore.track(submitted.id, trainJobTitle.value);
    ElMessage.success('训练已开始，完成后会通知你');
  } catch (err) {
    const e = err as { response?: { data?: { message?: string } }; message?: string };
    ElMessage.error(e.response?.data?.message || e.message || '模型训练失败');
  }
};

/** /api/v1/algorithms 返回的算法行（trainingApi 为 JS 模块无类型，此处显式声明） */
interface ApiAlgorithmRow {
  id: number;
  code: string;
  display_name: string;
  description?: string | null;
  status: string;
  param_schema?: unknown[];
}

onMounted(async () => {
  try {
    scenarios.value = await getScenarios();
    algorithms.value = ((await getAlgorithms()) as ApiAlgorithmRow[]).map((a) => ({
      id: a.id,
      display_name: a.display_name,
      available: a.status === 'AVAILABLE',
      params: mapBackendParams(a.param_schema ?? []),
    }));
  } catch (err) {
    const e = err as { response?: { data?: { message?: string } }; message?: string };
    ElMessage.warning(`加载算法/场景数据失败：${e.response?.data?.message || e.message || '请稍后重试'}`);
  }
  // 默认选中第一个 ACTUAL 场景与第一个可用算法
  if (scenarioOptions.value.length) {
    selectedScenario.value = scenarioOptions.value[0].id;
  }
  selectedAlgoId.value = algorithms.value.find((a) => a.available)?.id ?? '';
});
</script>

<template>
  <div class="risk-analysis-page">
    <div class="page-inner">
      <!-- ==================== 页面头部 ==================== -->
      <div class="page-header">
        <div>
          <p class="eyebrow">Model Training</p>
          <h2>模型训练</h2>
          <p class="page-header__desc">基于数据集训练贝叶斯分类模型</p>
        </div>
      </div>

      <!-- 兜底：/risk 的路由 meta.roles 与本文件的 isManagement 判的是同一对角色
           （SUPER_ADMIN / SCENARIO_ADMIN），守卫会先把非管理角色挡在门外，
           所以这块实际不会渲染。保留是因为守卫一旦放宽，直接露出训练表单会误导用户
           —— 提交必然被后端 403 拒掉。 -->
      <section v-if="!isManagement" class="card permission-tip">
        <div class="permission-tip__icon">🔒</div>
        <h3>仅管理员可进行模型训练</h3>
        <p>场景用户可在「风险研判」页面选择管理员已发布模型执行单条样本推理。</p>
        <button class="train-btn train-btn--ghost" @click="router.push('/inference')">前往风险研判</button>
      </section>

      <!-- ==================== 训练配置 ==================== -->
      <section v-else class="card train-card">
        <header class="train-card__head">
          <p class="eyebrow">Configuration</p>
          <h3>训练配置</h3>
        </header>

        <!-- 业务场景（数据库注册）：系统管理员可选全部；场景管理员的场景由账号绑定，不显示 -->
        <div
          v-if="currentUser?.role !== 'SCENARIO_ADMIN' && scenarioOptions.length"
          class="train-section"
        >
          <span class="section-label">业务场景</span>
          <div class="scenario-tabs">
            <button
              v-for="sc in scenarioOptions"
              :key="sc.id"
              class="scenario-tab"
              :class="{ 'is-active': selectedScenario === sc.id }"
              @click="selectedScenario = sc.id"
            >
              {{ sc.name }}
            </button>
          </div>
        </div>

        <!-- 数据集 + 算法 -->
        <div class="train-section train-section--pair">
          <div class="form-group">
            <span class="section-label">数据集</span>
            <div class="field">
              <select
                v-model="selectedDatasetId"
                class="form-select"
                :disabled="!selectedScenario || loadingDatasets"
              >
                <option v-if="loadingDatasets" value="" disabled>加载中…</option>
                <option v-else-if="!datasetList.length" value="" disabled>暂无数据集</option>
                <option v-for="ds in datasetList" :key="ds.id" :value="ds.id">
                  {{ ds.name }}（v{{ ds.version }} · {{ ds.fields_schema?.length ?? 0 }} 字段）{{ ds.status === 'ACTIVE' ? '' : '【已停用】' }}
                </option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <span class="section-label">算法</span>
            <div class="field">
              <select v-model="selectedAlgoId" class="form-select" :disabled="!algorithms.length">
                <option v-if="!algorithms.length" value="" disabled>暂无算法</option>
                <option
                  v-for="a in algorithms"
                  :key="a.id"
                  :value="a.id"
                  :disabled="!a.available"
                >
                  {{ a.display_name }}
                </option>
              </select>
            </div>
          </div>
        </div>

        <!-- 训练参数（需求 6.6.3 由 param_schema 动态生成；无适用参数时整节隐藏） -->
        <div v-if="visibleParams.length" class="train-section">
          <span class="section-label">训练参数</span>
          <div class="param-grid">
            <div v-for="p in visibleParams" :key="p.param_name" class="param-item">
              <div class="param-item__head">
                <span class="param-item__label">{{ p.label }}</span>
                <span
                  v-if="p.type === 'number' && (p.min !== undefined || p.max !== undefined)"
                  class="param-item__range"
                >{{ p.min }} – {{ p.max }}</span>
              </div>
              <div v-if="p.type === 'select'" class="field">
                <select v-model="paramForm[p.param_name]" class="form-select">
                  <option v-for="o in p.options" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
              </div>
              <input
                v-else-if="p.type === 'number'"
                v-model.number="paramForm[p.param_name]"
                type="number"
                class="form-input"
                :min="p.min"
                :max="p.max"
                :step="p.step ?? 'any'"
              />
              <input v-else v-model="paramForm[p.param_name]" type="text" class="form-input" />
            </div>
          </div>
        </div>

        <!-- 训练按钮：异步提交，点击后只表示「已开始」，不显示已用秒数 -->
        <div class="train-actions">
          <button
            class="train-btn train-btn--primary"
            :class="{ 'is-running': training }"
            :disabled="training || !selectedDatasetId || !selectedAlgoId"
            @click="handleTrain"
          >
            <span v-if="training" class="btn-spinner"></span>
            {{ training ? '训练中' : '开始训练' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.risk-analysis-page {
  position: relative;
  z-index: 1;
}

/* ==================== 页头 ==================== */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.page-header__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

/* ==================== 权限提示 ==================== */
.permission-tip {
  display: grid;
  place-items: center;
  gap: 12px;
  padding: 64px 20px;
  text-align: center;
}

.permission-tip__icon {
  font-size: 2.4rem;
}

.permission-tip h3 {
  margin: 0;
  font-size: 1.15rem;
  color: #e8f1ff;
}

.permission-tip p {
  margin: 0;
  color: rgba(200, 222, 255, 0.55);
  font-size: 0.92rem;
}

/* 内容区容器：限宽只在超宽屏才生效（1600px）。
   1440 及以下不触发 —— 页头与卡片都铺满，左右边距就等于 .app-shell 的 padding，
   和其它页面完全一致（页头位置不变）；超宽屏才居中收窄，且页头与卡片始终共用同一条左边缘。 */
.page-inner {
  max-width: 1600px;
  margin: 0 auto;
}

/* ==================== 配置卡 ====================
   内部按「场景 / 数据集·算法 / 参数 / 按钮」分节，节与节之间用细线分隔 ——
   横向空间被用起来，纵向也有层次。宽度由 .page-inner 决定。 */
.train-card {
  display: flex;
  flex-direction: column;
  padding: 26px 28px;
}

.train-card__head h3 {
  margin: 0;
  font-size: 1.12rem;
  font-weight: 600;
  color: #e8f1ff;
}

.train-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 22px;
  padding-top: 22px;
  border-top: 1px solid rgba(125, 201, 255, 0.12);
}

/* 数据集 + 算法并排：两个字段同类、都短，各占一半，省掉一整行高度 */
.train-section--pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px;
}

.section-label {
  font-size: 0.78rem;
  letter-spacing: 0.05em;
  color: rgba(180, 200, 235, 0.6);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 场景 chips：每个 chip 自带圆角，不套外层胶囊 —— 场景多于一行时换行也自然 */
.scenario-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scenario-tab {
  border: 1px solid rgba(125, 201, 255, 0.16);
  background: rgba(10, 21, 38, 0.6);
  color: rgba(200, 222, 255, 0.7);
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 0.84rem;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.scenario-tab:hover {
  border-color: rgba(125, 201, 255, 0.38);
  background: rgba(91, 166, 255, 0.1);
  color: #dceaff;
}

.scenario-tab.is-active {
  border-color: rgba(125, 201, 255, 0.5);
  background: linear-gradient(180deg, rgba(91, 166, 255, 0.26), rgba(91, 166, 255, 0.12));
  color: #fff;
  font-weight: 500;
  box-shadow: 0 6px 18px rgba(28, 82, 160, 0.26);
}

/* 下拉 / 输入同一套 token，高度两边都显式钉住 —— 原生 select 的内容盒由 UA 决定，
   同 padding 字号下 input 会高出 4px。箭头自绘：appearance:auto 的系统箭头
   在深色主题下与整体不搭。 */
.field {
  position: relative;
  display: block;
}

.form-select,
.form-input {
  width: 100%;
  height: 40px;
  box-sizing: border-box;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.18);
  background: rgba(6, 14, 26, 0.7);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
  color-scheme: dark;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.form-select {
  appearance: none;
  -webkit-appearance: none;
  padding-right: 38px;
  cursor: pointer;
}

.field::after {
  content: '';
  position: absolute;
  right: 16px;
  top: 50%;
  width: 7px;
  height: 7px;
  border-right: 1.6px solid rgba(160, 200, 255, 0.6);
  border-bottom: 1.6px solid rgba(160, 200, 255, 0.6);
  transform: translateY(-72%) rotate(45deg);
  pointer-events: none;
}

.form-select:focus,
.form-input:focus {
  border-color: rgba(125, 201, 255, 0.5);
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.14);
}

.form-select:disabled,
.form-input:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.form-select option {
  background: #0b1628;
  color: #e8f1ff;
}

/* 训练参数：弹性换行，每张卡 200–300px —— 参数少时不会被拉成一张巨宽的卡，
   参数多（CAVWNB 5 项）时一行放得下，不会堆成很高的单列。 */
.param-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.param-item {
  flex: 1 1 200px;
  max-width: 300px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.028);
  border: 1px solid rgba(125, 201, 255, 0.09);
}

.param-item__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.param-item__label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #d3e5ff;
}

.param-item__range {
  font-size: 0.72rem;
  color: rgba(160, 200, 255, 0.45);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* ==================== 按钮 ==================== */
.train-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 22px;
  padding-top: 22px;
  border-top: 1px solid rgba(125, 201, 255, 0.12);
}

/* 卡片宽了之后通栏按钮会拉成一条 1200px 的横带，这里改成右对齐的定宽主按钮 */
.train-actions .train-btn--primary {
  width: auto;
  min-width: 180px;
  padding: 0 34px;
}

.train-btn {
  width: 100%;
  height: 44px;
  border: 1px solid transparent;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.train-btn--primary {
  color: #04121f;
  background: linear-gradient(135deg, #7dc9ff, #4f8ff0);
  box-shadow: 0 12px 28px rgba(45, 108, 200, 0.26);
}

.train-btn--primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 16px 34px rgba(45, 108, 200, 0.34);
}

/* 训练中仍保持蓝底 —— 灰化的 disabled 看着像「不可用」，而这里是「正在跑」 */
.train-btn--primary.is-running {
  color: #04121f;
  background: linear-gradient(135deg, #7dc9ff, #4f8ff0);
  box-shadow: 0 10px 24px rgba(45, 108, 200, 0.22);
  cursor: default;
}

.train-btn--primary:disabled:not(.is-running) {
  color: rgba(200, 222, 255, 0.38);
  background: rgba(125, 201, 255, 0.12);
  border-color: rgba(125, 201, 255, 0.14);
  box-shadow: none;
  cursor: not-allowed;
}

.train-btn--ghost {
  width: auto;
  height: 40px;
  padding: 0 22px;
  color: #9ad6ff;
  background: rgba(91, 166, 255, 0.1);
  border-color: rgba(125, 201, 255, 0.24);
}

.train-btn--ghost:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(125, 201, 255, 0.4);
}

/* ==================== 加载动画 ==================== */
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(4, 18, 31, 0.25);
  border-top-color: #04121f;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==================== 响应式 ==================== */
@media (max-width: 900px) {
  .train-section--pair {
    grid-template-columns: 1fr;
  }
}
</style>
