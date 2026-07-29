<template>
  <div class="container" style="padding-top: 0px">
    <h2>贝叶斯AI风险模型训练与预测</h2>

    <!-- 新增：全局风险阈值配置 -->
    <div class="box config-box">
      <h3>0. 风险判定阈值配置</h3>
      <div class="threshold-form">
        <div class="form-item">
          <label>高风险阈值(0~1)</label>
          <input v-model.number="thresholdHigh" type="number" min="0" max="1" step="0.01" />
        </div>
        <div class="form-item">
          <label>中风险阈值(0~1)</label>
          <input v-model.number="thresholdMid" type="number" min="0" max="1" step="0.01" />
        </div>
        <div class="form-item">
          <label>低风险阈值(0~1)</label>
          <input v-model.number="thresholdLow" type="number" min="0" max="1" step="0.01" />
        </div>
        <button @click="saveThresholdConfig" style="margin-bottom: 9px">保存全局阈值</button>
      </div>
    </div>

    <!-- 0a. 选择场景（第一阶段P0需求：训练前必须绑定场景） -->
    <div class="box">
      <h3>0a. 选择业务场景</h3>
      <div class="scenario-selector-box">
        <span
          v-for="sc in scenarioOptions"
          :key="sc.value"
          class="scenario-tab"
          :class="{ 'scenario-tab--active': selectedScenarioForTraining === sc.value }"
          @click="selectedScenarioForTraining = sc.value"
        >
          {{ sc.label }}
        </span>
      </div>
      <p v-if="selectedScenarioForTraining" class="scenario-hint">
        当前已绑定场景：<strong>{{ scenarioLabel[selectedScenarioForTraining] }}</strong>
      </p>
    </div>

    <!-- 1. 选择数据集 -->
    <div class="box">
      <h3>1. 选择数据集</h3>
      <select v-model="selectDataset" @change="handleDatasetChange">
        <option v-for="item in datasetList" :key="item.dataset_name" :value="item.dataset_name">
          {{ item.description }}
        </option>
      </select>
    </div>

    <!-- 2. 模型训练区域 -->
    <div class="box">
      <h3>2. 开始训练模型</h3>
      <div>
        <span>算法：</span>
        <select v-model="trainParams.algo_type">
          <option value="PMWNB">PMWNB（矩阵加权贝叶斯）</option>
          <option value="naive_bayes">朴素贝叶斯</option>
          <option value="bayesian_network">贝叶斯网络</option>
        </select>

        <span>离散方式：</span>
        <select v-model="trainParams.discrete_method">
          <option value="equal_width">等宽离散</option>
          <option value="equal_freq">等频离散</option>
        </select>

        <button @click="handleTrain" :disabled="training">
          <span v-if="training" class="btn-spinner"></span>
          {{ training ? '训练中...' : '一键训练' }}
        </button>
      </div>
      <!-- 训练出来的准确率结果，新增召回率展示 -->
      <div v-if="training" class="result" style="text-align:center;">
        <p>⏳ 模型训练中，已训练 {{ trainingElapsed }} 秒...</p>
      </div>
      <div v-if="trainResult" class="result">
        <h4>训练完成指标</h4>
        <p>准确率（Accuracy）：{{ trainResult.accuracy }}</p>
        <p>召回率（Recall）：{{ trainResult.recall }}</p>
        <p>F1分数：{{ trainResult.f1 }}</p>
        <p>G-mean：{{ trainResult.g_mean ?? 'N/A' }}</p>
        <p>训练耗时：{{ trainResult.train_time_s }} 秒</p>
      </div>
    </div>

    <!-- 3. AI预测风险 -->
    <div class="box">
      <h3>3. 输入数据做风险预测</h3>
      <div style="margin: 10px 0; display: flex; align-items: center; gap: 8px">
        <span>流量长度(0~1)：</span>
        <input v-model.number="inputData.feature1" placeholder="0~1" />
      </div>
      <div style="margin: 10px 0; display: flex; align-items: center; gap: 8px">
        <span>连接时长(0~1)：</span>
        <input v-model.number="inputData.feature2" placeholder="0~1" />
      </div>
      <div style="margin: 10px 0; display: flex; align-items: center; gap: 8px">
        <span>访问频次(0~1)：</span>
        <input v-model.number="inputData.feature3" placeholder="0~1" />
      </div>
      <button @click="handleInfer">执行风险预测</button>

      <!-- 预测结果 -->
      <div v-show="inferResult" class="result">
        <h4>AI研判结果</h4>
        <p>风险等级：{{ inferResult?.risk_level }}</p>
        <p>风险概率：{{ inferResult?.risk_probability }}</p>
        <p>风险类型：{{ inferResult?.risk_type }}</p>
      </div>
    </div>

    <!-- 新增：历史训练实验记录（论文多组实验对比） -->
    <div class="box record-box">
      <h3>4. 历史训练实验记录</h3>
      <div class="record-list" v-if="expRecordList.length > 0">
        <div class="record-item" v-for="record in expRecordList" :key="record.id">
          <div class="record-info">
            <span>训练耗时：{{ record.train_time || record.train_time_s }}s</span>
            <span>数据集：{{ dsLabel[record.dataset_name] || record.dataset_name }}</span>
            <span>算法：{{ algoLabel[record.algo_type] || record.algo_type }}</span>
            <span>准确率：{{ record.accuracy }} | F1：{{ record.f1 }} | 召回率：{{ record.recall }}</span>
          </div>
          <div class="record-btns">
            <button @click="loadHistoryExp(record)">复现该实验</button>
            <button @click="deleteExpRecord(record.id)">删除记录</button>
          </div>
        </div>
      </div>
      <p v-else>暂无历史训练实验记录</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { getDatasetList, trainModel, riskInfer, saveThreshold, getExpRecords, delExpRecord } from '@/api/modelApi';

const route = useRoute();

// 监听路由
watch(
  () => route.query,
  (newQuery) => {
    if (newQuery.fl && newQuery.du && newQuery.af) {
      inputData.value.feature1 = Number(newQuery.fl);
      inputData.value.feature2 = Number(newQuery.du);
      inputData.value.feature3 = Number(newQuery.af);
      inferResult.value = null;
      ElMessage.success('已自动带入告警流量特征');
    }
  },
  { immediate: false }
);

const trainFinished = ref(false);
const training = ref(false);
const trainingElapsed = ref(0);
let trainingTimer = null;
const thresholdHigh = ref(0.75);
const thresholdMid = ref(0.45);
const thresholdLow = ref(0.2);
const datasetList = ref([]);
const selectDataset = ref('');
const selectedScenarioForTraining = ref('');
const scenarioOptions = [
  { value: 'network_security', label: '网络安全' },
  { value: 'power_system', label: '电力系统' },
  { value: 'flightdeck_operation', label: '航母甲板' },
];
const scenarioLabel = {
  network_security: '网络安全态势感知',
  power_system: '电力系统风险态势感知',
  flightdeck_operation: '航母甲板保障作业态势感知',
};
const trainParams = ref({
  dataset_name: '',
  algo_type: 'PMWNB',
  discrete_method: 'equal_width',
});
const trainResult = ref(null);
const inputData = ref({
  feature1: 0.62,
  feature2: 0.18,
  feature3: 0.87,
});
const inferResult = ref(null);
const expRecordList = ref([]);

// 中英文名称映射（供历史记录显示）
const dsLabel = {
  'net_attack_2024': '网络入侵流量数据集',
  'power_outage': '电力停电风险数据集',
  'carrier_deck': '航母舰面调度数据集',
};
const algoLabel = {
  'PMWNB': 'PMWNB矩阵加权贝叶斯',
  'naive_bayes': '朴素贝叶斯',
  'bayesian_network': '贝叶斯网络',
};

// 所有函数全部放在onMount外面
const handleDatasetChange = () => {
  trainParams.value.dataset_name = selectDataset.value;
  trainFinished.value = false;
  inferResult.value = null;
};

const handleTrain = async () => {
  if (!selectDataset.value) {
    ElMessage.warning('请先选择数据集！');
    return;
  }
  training.value = true;
  trainResult.value = null;
  trainingElapsed.value = 0;
  trainingTimer = setInterval(() => { trainingElapsed.value += 1; }, 1000);
  try {
    const res = await trainModel(trainParams.value);
    if (!res?.data) {
      ElMessage.warning('训练接口返回数据为空，请重试');
      return;
    }
    trainResult.value = res.data;
    trainFinished.value = true;
    const metrics = res.data;
    ElMessage.success(`训练完成！准确率：${metrics.accuracy}，耗时：${metrics.train_time_s}s`);
    const recordRes = await getExpRecords();
    expRecordList.value = recordRes.data;
  } catch (err) {
    ElMessage.error(
      err.response?.data?.detail ? JSON.stringify(err.response.data.detail) : '训练请求失败：' + err.message
    );
    console.error('完整训练报错信息：', err);
  } finally {
    clearInterval(trainingTimer);
    training.value = false;
  }
};

const handleInfer = async () => {
  if (!trainFinished.value) {
    ElMessage.warning('请先选择数据集并点击【一键训练】完成模型训练');
    return;
  }
  try {
    const f1 = inputData.value.feature1;
    const f2 = inputData.value.feature2;
    const f3 = inputData.value.feature3;
    const res = await riskInfer(f1, f2, f3);
    if (res?.data) {
      inferResult.value = res.data;
      ElMessage.success(`AI风险研判完成，等级：${res.data.risk_level}`);
    }
  } catch (err) {
    ElMessage.error('风险预测请求失败：' + err.message);
    console.error(err);
  }
};

const saveThresholdConfig = async () => {
  if (thresholdHigh.value <= thresholdMid.value || thresholdMid.value <= thresholdLow.value) {
    ElMessage.warning('阈值设置错误：高风险阈值 > 中风险阈值 > 低风险阈值');
    return;
  }
  await saveThreshold(thresholdHigh.value, thresholdMid.value, thresholdLow.value);
  ElMessage.success('全局风险阈值保存成功！');
};

const loadHistoryExp = (record) => {
  selectDataset.value = record.dataset_name;
  trainParams.value.dataset_name = record.dataset_name;
  trainParams.value.algo_type = record.algo_type;
  trainParams.value.discrete_method = record.discrete_method;
  ElMessage.success('已自动回填历史实验参数，点击【一键训练】即可复现本次实验！');
};

const deleteExpRecord = async (id) => {
  try {
    await delExpRecord(id);
    ElMessage.success('该实验记录已成功删除！');
    const recordRes = await getExpRecords();
    expRecordList.value = recordRes.data;
  } catch (err) {
    ElMessage.error(
      err.response?.data?.detail ? JSON.stringify(err.response.data.detail) : '删除记录失败：' + err.message
    );
    console.error('删除报错：', err);
  }
};

// onMount里面只放页面加载执行代码，不放函数
onMounted(async () => {
  const datasetRes = await getDatasetList();
  datasetList.value = datasetRes.data;
  const recordRes = await getExpRecords();
  expRecordList.value = recordRes.data;

  if (route.query.fl && route.query.du && route.query.af) {
    inputData.value.feature1 = Number(route.query.fl);
    inputData.value.feature2 = Number(route.query.du);
    inputData.value.feature3 = Number(route.query.af);
    inferResult.value = null;
    if (!trainFinished.value) {
      ElMessage.error('未完成模型训练，告警流量无法自动研判');
    } else {
      ElMessage.success('已自动带入当前告警流量特征，可直接执行贝叶斯风险预测');
    }
  }
});
</script>

<style scoped>
.container {
  width: 96%;
  margin: 0 auto;
}
.box {
  margin: 20px 0;
  padding: 15px;
  border: 1px solid #ccc;
  border-radius: 6px;
}
.result {
  margin-top: 10px;
  background: rgba(0, 30, 60, 0.4);
  padding: 12px;
  border-radius: 4px;
  color: #ffffff;
  border: 1px solid #407acc;
}
.result h4 {
  margin-top: 0;
  color: #74b9ff;
}
input,
select {
  margin: 8px;
  padding: 8px 10px;
  box-sizing: border-box;
}
button {
  padding: 8px 10px;
  background: #2377e8;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
/* 场景选择器样式 */
.scenario-selector-box {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.5);
  border: 1px solid rgba(125, 201, 255, 0.12);
  width: fit-content;
}
.scenario-tab {
  padding: 6px 16px;
  border-radius: 999px;
  color: rgba(220, 234, 255, 0.7);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
  user-select: none;
}
.scenario-tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}
.scenario-tab--active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}
.scenario-hint {
  margin: 8px 0 0;
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.6);
}
.scenario-hint strong {
  color: #9ad6ff;
}

/* 阈值表单样式 */
.threshold-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
/* 实验记录样式 */
.record-item {
  padding: 10px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  margin: 8px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.record-info {
  display: flex;
  gap: 16px;
}
.record-btns button {
  margin-left: 6px;
  background: #4080f0;
}
.record-btns button:last-child {
  background: #e64340;
}
/* 训练加载动画 */
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
