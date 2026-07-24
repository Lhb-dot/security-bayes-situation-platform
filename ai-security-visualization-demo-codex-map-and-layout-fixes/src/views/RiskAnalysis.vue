<template>
  <div class="container" style="padding-top: 0px">
    <h2>贝叶斯AI风险模型训练与预测</h2>

    <!-- 新增：全局风险阈值配置（配置管理组核心功能） -->
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
          <option value="naive_bayes">朴素贝叶斯</option>
          <option value="bayesian_network">贝叶斯网络</option>
        </select>

        <span>离散方式：</span>
        <select v-model="trainParams.discrete_method">
          <option value="equal_width">等宽离散</option>
          <option value="equal_freq">等频离散</option>
        </select>

        <button @click="handleTrain">一键训练</button>
      </div>
      <!-- 训练出来的准确率结果，新增召回率展示 -->
      <div v-if="trainResult" class="result">
        <h4>训练完成指标</h4>
        <p>准确率：{{ trainResult.accuracy }}</p>
        <p>F1分数：{{ trainResult.f1 }}</p>
        <p>召回率：{{ trainResult.recall }}</p>
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
            <span>训练时间：{{ record.train_time }}</span>
            <span>数据集：{{ record.dataset_name }}</span>
            <span>算法：{{ record.algo_type }}</span>
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
const thresholdHigh = ref(0.75);
const thresholdMid = ref(0.45);
const thresholdLow = ref(0.2);
const datasetList = ref([]);
const selectDataset = ref('');
const trainParams = ref({
  dataset_name: '',
  algo_type: 'bayesian_network',
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

// 所有函数全部放在onMount外面
const handleDatasetChange = () => {
  trainParams.value.dataset_name = selectDataset.value;
  trainFinished.value = false;
  inferResult.value = null;
};

const handleTrain = async () => {
  try {
    if (!selectDataset.value) {
      ElMessage.warning('请先选择数据集！');
      return;
    }
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
</style>
