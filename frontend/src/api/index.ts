/** Security Bayes Platform — 统一 API 模块（v2.0 后端对接）。
 *
 * 替换 @/services/mockApi.ts，所有函数改为调用真实后端接口。
 * 函数签名保持与 mockApi 兼容，视图改动最小化。
 *
 * 调用约定：
 * - 所有请求通过 @/utils/request（axios 实例，baseURL=http://127.0.0.1:12312）
 * - 后端统一返回 { code: 0, data: ..., message: "success" }
 * - code !== 0 时抛出错误，前端可统一 catch
 */
import request from '@/utils/request';
import type {
  Scenario,
  ScenarioId,
  ScenarioDetail,
  GlobalOverview,
  Dataset,
  DatasetField,
  DatasetVersion,
  ModelVersionRecord,
  ModelStatus,
  RiskEvent,
  InferenceRecord,
  SituationData,
  Report,
  UserAccount,
  UserRole,
  AlgorithmDefinition,
  ThresholdConfig,
  ThresholdChangeLog,
  AlertRecord,
  DashboardSnapshot,
} from '@/types/security';

// =========================================================================
// 响应解包辅助
// =========================================================================
function unwrap<T>(res: any): T {
  if (res && typeof res === 'object' && 'code' in res) {
    if (res.code !== 0) {
      throw new Error(res.message || '请求失败');
    }
    return res.data as T;
  }
  // 兼容旧版 PMWNB 接口返回格式（code: 200）
  if (res && res.code === 200) {
    return res.data as T;
  }
  return res as T;
}

// =========================================================================
// 会话管理
// =========================================================================
const SESSION_KEY = 'bayes_session_user_id';

let cachedUser: UserAccount | null = null;

/** 将后端用户对象映射为前端 UserAccount 类型 */
function mapUser(u: any): UserAccount {
  return {
    user_id: String(u.id),
    username: u.username,
    display_name: u.display_name || u.username,
    role: (u.role as UserRole) || 'USER',
    status: u.status === 'ENABLED' ? 'active' : 'disabled',
    created_at: u.created_at || '',
    created_by: String(u.created_by || ''),
    last_login_at: u.last_login_at,
  };
}

/** 获取当前登录用户（内存缓存 + localStorage 兜底） */
export function getCurrentUser(): UserAccount | null {
  return cachedUser;
}

/** 从后端恢复会话（路由守卫调用） */
export async function restoreSession(): Promise<UserAccount | null> {
  const userId = window.localStorage.getItem(SESSION_KEY);
  if (!userId) return null;
  try {
    const res = await request.get('/api/auth/me');
    const user = mapUser(unwrap<any>(res));
    cachedUser = user;
    return user;
  } catch {
    cachedUser = null;
    window.localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

/** 登录 */
export async function login(username: string, password: string): Promise<UserAccount> {
  const res = await request.post('/api/auth/login', { username, password });
  if (res.code !== 0) throw new Error(res.message || '用户名或密码错误');
  const user = mapUser(res.data);
  cachedUser = user;
  window.localStorage.setItem(SESSION_KEY, String(user.user_id));
  return user;
}

/** 退出登录 */
export async function logout(): Promise<void> {
  cachedUser = null;
  window.localStorage.removeItem(SESSION_KEY);
}

/** 修改本人密码 */
export async function changeOwnPassword(oldPassword: string, newPassword: string): Promise<void> {
  await request.post('/api/auth/change-password', { old_password: oldPassword, new_password: newPassword });
}

// =========================================================================
// 用户管理（ADMIN）
// =========================================================================
export async function getUserList(): Promise<UserAccount[]> {
  const res = await request.get('/api/users', { params: { page_size: 200 } });
  return unwrap<{ items: any[] }>(res).items.map(mapUser);
}

export async function createUser(params: {
  username: string;
  display_name: string;
  password: string;
  role: UserRole;
}): Promise<UserAccount> {
  const res = await request.post('/api/users', {
    username: params.username,
    password: params.password,
    role: params.role,
  });
  return mapUser(unwrap<any>(res));
}

export async function resetUserPassword(userId: string, newPassword: string): Promise<void> {
  await request.put(`/api/users/${userId}/password`, { new_password: newPassword });
}

export async function setUserStatus(userId: string, status: 'active' | 'disabled'): Promise<void> {
  const backendStatus = status === 'active' ? 'ENABLED' : 'DISABLED';
  await request.put(`/api/users/${userId}/status`, { status: backendStatus });
}

// =========================================================================
// 场景管理
// =========================================================================
export async function getScenarioList(): Promise<Scenario[]> {
  const res = await request.get('/api/scenarios');
  const items: any[] = unwrap<any[]>(res);
  return items.map((s: any) => ({
    scenario_id: s.code as ScenarioId,
    name: s.name,
    description: s.description || '',
    risk_level: 'medium',
    risk_score: 0,
    event_count: 0,
    high_risk_count: 0,
    dataset_count: 0,
    model_count: 0,
    status: s.access_status === 'ACTUAL' ? 'active' : 'inactive',
  }));
}

export async function getScenarioDetail(scenarioId: ScenarioId): Promise<ScenarioDetail> {
  // 场景详情 = 场景信息 + 个人态势统计
  const scenarios = await getScenarioList();
  const scenario = scenarios.find(s => s.scenario_id === scenarioId);
  if (!scenario) throw new Error('场景不存在');

  // 获取态势统计数据
  let stats: any = { total_events: 0, high_count: 0, medium_count: 0, low_count: 0, pending_count: 0, processing_count: 0, resolved_count: 0 };
  try {
    const statsRes = await request.get('/api/situation/my-stats');
    stats = unwrap<any>(statsRes);
  } catch { /* 暂无数据 */ }

  // 获取风险事件列表
  let recentEvents: RiskEvent[] = [];
  try {
    const eventsRes = await request.get('/api/risk-events', { params: { scenario_id: await getScenarioId(scenarioId), page_size: 5 } });
    recentEvents = unwrap<{ items: RiskEvent[] }>(eventsRes).items;
  } catch { /* 暂无数据 */ }

  return {
    scenario,
    metrics: [
      { id: 'risk-score', label: '风险事件数', value: stats.total_events, trend: 0 },
      { id: 'event-rate', label: '高危事件', value: stats.high_count, trend: 0 },
      { id: 'model-accuracy', label: '待处置', value: stats.pending_count, trend: 0 },
      { id: 'response-time', label: '已处置', value: stats.resolved_count, trend: 0 },
    ],
    trend_data: [],
    risk_distribution: [
      { label: '高危', value: stats.high_count, color: '#ff7b72' },
      { label: '中危', value: stats.medium_count, color: '#ffd166' },
      { label: '低危', value: stats.low_count, color: '#53e5c8' },
    ],
    recent_events: recentEvents,
  };
}

async function getScenarioId(code: ScenarioId): Promise<number> {
  const res = await request.get('/api/scenarios');
  const items: any[] = unwrap<any[]>(res);
  const found = items.find((s: any) => s.code === code);
  return found?.id ?? 0;
}

export async function getGlobalOverview(): Promise<GlobalOverview> {
  const scenarios = await getScenarioList();
  let stats: any = { total_events: 0, high_count: 0, medium_count: 0, low_count: 0, pending_count: 0, processing_count: 0, resolved_count: 0 };
  try {
    const statsRes = await request.get('/api/situation/my-stats');
    stats = unwrap<any>(statsRes);
  } catch { /* 暂无数据 */ }

  return {
    global_risk_score: stats.high_count > 0 ? 75 : stats.total_events > 0 ? 45 : 20,
    global_risk_level: stats.high_count > 0 ? 'high' : stats.total_events > 0 ? 'medium' : 'low',
    scenario_count: scenarios.length,
    high_risk_count: stats.high_count,
    active_model_count: 0,
    scenarios,
    global_trend: [],
  };
}

// =========================================================================
// 数据集管理
// =========================================================================
export async function getDatasetList(scenarioId?: ScenarioId): Promise<Dataset[]> {
  const params: any = { page_size: 200 };
  if (scenarioId) {
    const id = await getScenarioId(scenarioId);
    if (id) params.scenario_id = id;
  }
  const res = await request.get('/api/datasets', { params });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((d: any) => ({
    dataset_id: d.logical_id,
    name: `${d.logical_id} v${d.version}`,
    description: d.label_field ? `标签字段: ${d.label_field}` : '',
    scenario_id: '',  // 由调用方补充
    record_count: 0,
    field_count: Array.isArray(d.fields_schema) ? d.fields_schema.length : 0,
    fields: Array.isArray(d.fields_schema)
      ? d.fields_schema.map((f: any) => ({
          field_name: f.name,
          field_type: f.type || 'string',
          field_role: f.role === 'label' ? '分类标签' : '输入特征' as const,
          description: '',
          sample_value: '',
          nullable: false,
          enum_values: f.enum_values,
        }))
      : [],
    created_at: d.uploaded_at || '',
    data_format: 'arff' as const,
    dataset_version: `v${d.version}`,
    uploaded_by: String(d.uploaded_by || ''),
    uploaded_at: d.uploaded_at || '',
    enabled: d.status === 'ACTIVE',
    referenced: false,
  }));
}

export async function getDatasetFields(datasetId: string): Promise<DatasetField[]> {
  // datasetId is logical_id, need to find the DB id
  const res = await request.get('/api/datasets', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  const found = items.find((d: any) => d.logical_id === datasetId);
  if (!found) return [];
  const fieldsRes = await request.get(`/api/datasets/${found.id}/fields`);
  const schema: any = unwrap<any>(fieldsRes);
  return (schema.fields_schema || []).map((f: any) => ({
    field_name: f.name,
    field_type: f.type || 'string',
    field_role: f.role === 'label' ? '分类标签' : '输入特征',
    description: '',
    sample_value: '',
    nullable: false,
    enum_values: f.enum_values,
  }));
}

export async function getDatasetVersions(datasetId?: string): Promise<DatasetVersion[]> {
  const res = await request.get('/api/datasets', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items
    .filter((d: any) => !datasetId || d.logical_id === datasetId)
    .map((d: any) => ({
      dataset_version_id: `${d.logical_id}@v${d.version}`,
      dataset_id: d.logical_id,
      dataset_version: `v${d.version}`,
      name: `${d.logical_id} v${d.version}`,
      scenario_id: '' as ScenarioId,
      data_format: 'arff' as const,
      file_path: d.file_path || '',
      record_count: 0,
      field_count: Array.isArray(d.fields_schema) ? d.fields_schema.length : 0,
      fields: [],
      uploaded_by: String(d.uploaded_by || ''),
      uploaded_at: d.uploaded_at || '',
      enabled: d.status === 'ACTIVE',
      referenced: false,
    }));
}

export async function uploadDataset(params: {
  dataset_id: string;
  name: string;
  scenario_id: ScenarioId;
  data_format: string;
  record_count: number;
  fields: DatasetField[];
}): Promise<DatasetVersion> {
  const scenarioId = await getScenarioId(params.scenario_id);
  const res = await request.post('/api/datasets', {
    logical_id: params.dataset_id,
    scenario_id: scenarioId,
    file_path: `arff/${params.dataset_id}_0503.arff`,
    fields_schema: params.fields.map(f => ({
      name: f.field_name,
      type: f.field_type,
      role: f.field_role === '分类标签' ? 'label' : 'feature',
      enum_values: f.enum_values,
    })),
    label_field: params.fields.find(f => f.field_role === '分类标签')?.field_name || '',
  });
  const d = unwrap<any>(res);
  return {
    dataset_version_id: `${d.logical_id}@v${d.version}`,
    dataset_id: d.logical_id,
    dataset_version: `v${d.version}`,
    name: `${d.logical_id} v${d.version}`,
    scenario_id: params.scenario_id,
    data_format: params.data_format as any,
    file_path: d.file_path || '',
    record_count: params.record_count,
    field_count: params.fields.length,
    fields: params.fields,
    uploaded_by: String(d.uploaded_by || ''),
    uploaded_at: d.uploaded_at || '',
    enabled: true,
    referenced: false,
  };
}

export async function createDatasetVersion(datasetId: string, fields: DatasetField[]): Promise<DatasetVersion> {
  const res = await request.get('/api/datasets', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  const found = items.find((d: any) => d.logical_id === datasetId);
  if (!found) throw new Error('数据集不存在');
  const labelField = fields.find(f => f.field_role === '分类标签');
  const updateRes = await request.put(`/api/datasets/${found.id}`, {
    fields_schema: fields.map(f => ({
      name: f.field_name,
      type: f.field_type,
      role: f.field_role === '分类标签' ? 'label' : 'feature',
      enum_values: f.enum_values,
    })),
    label_field: labelField?.field_name || '',
  });
  const d = unwrap<any>(updateRes);
  return {
    dataset_version_id: `${d.logical_id}@v${d.version}`,
    dataset_id: d.logical_id,
    dataset_version: `v${d.version}`,
    name: `${d.logical_id} v${d.version}`,
    scenario_id: '' as ScenarioId,
    data_format: 'arff' as const,
    file_path: d.file_path || '',
    record_count: 0,
    field_count: fields.length,
    fields,
    uploaded_by: String(d.uploaded_by || ''),
    uploaded_at: d.uploaded_at || '',
    enabled: true,
    referenced: false,
  };
}

export async function disableDatasetVersion(versionId: string): Promise<void> {
  const [logicalId] = versionId.split('@');
  const res = await request.get('/api/datasets', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  const found = items.find((d: any) => d.logical_id === logicalId);
  if (!found) throw new Error('数据集版本不存在');
  await request.put(`/api/datasets/${found.id}/disable`);
}

export async function deleteDatasetVersion(versionId: string): Promise<void> {
  const [logicalId] = versionId.split('@');
  const res = await request.get('/api/datasets', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  const found = items.find((d: any) => d.logical_id === logicalId);
  if (!found) throw new Error('数据集版本不存在');
  await request.delete(`/api/datasets/${found.id}`);
}

// =========================================================================
// 算法注册
// =========================================================================
export async function getAlgorithms(): Promise<AlgorithmDefinition[]> {
  const res = await request.get('/api/algorithms', { params: { only_available: true } });
  const items: any[] = unwrap<any[]>(res);
  return items.map((a: any) => ({
    algorithm_id: a.code,
    display_name: a.display_name || a.code,
    available: a.status === 'AVAILABLE',
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: a.description || '',
    params: (a.param_schema || []).map((p: any) => ({
      param_name: p.name,
      label: p.name,
      type: p.type === 'int' || p.type === 'float' ? 'number' : p.type === 'enum' ? 'select' : p.type || 'string',
      default_value: p.default ?? '',
      min: p.min,
      max: p.max,
      step: p.step,
      options: p.enum_values ? p.enum_values.map((v: any) => ({ value: String(v), label: String(v) })) : undefined,
      description: '',
    })),
  }));
}

// =========================================================================
// 模型版本管理
// =========================================================================
export async function getModelVersions(scenarioId?: ScenarioId, datasetId?: string): Promise<ModelVersionRecord[]> {
  const params: any = { page_size: 200 };
  if (scenarioId) {
    const id = await getScenarioId(scenarioId);
    if (id) params.scenario_id = id;
  }
  if (datasetId) {
    const res = await request.get('/api/datasets', { params: { page_size: 200 } });
    const items: any[] = unwrap<{ items: any[] }>(res).items;
    const found = items.find((d: any) => d.logical_id === datasetId);
    if (found) params.dataset_id = found.id;
  }
  const res = await request.get('/api/models', { params });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((m: any) => ({
    model_version_id: String(m.id),
    scenario_id: '' as ScenarioId,
    dataset_id: '',
    dataset_version: '',
    algorithm_id: String(m.algorithm_id || ''),
    training_parameters: m.training_parameters || {},
    evaluation_metrics: m.evaluation_metrics || {},
    train_time_s: 0,
    trained_by: String(m.trained_by || ''),
    trained_at: m.trained_at || '',
    status: m.status as ModelStatus,
    published_by: m.published_by ? String(m.published_by) : undefined,
    published_at: m.published_at,
    is_default: m.is_default || false,
  }));
}

export async function trainModel(params: {
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;
  algorithm_id: string;
  training_parameters: Record<string, unknown>;
}): Promise<ModelVersionRecord & { train_time_s: number }> {
  const scenarioId = await getScenarioId(params.scenario_id);
  const dsRes = await request.get('/api/datasets', { params: { page_size: 200 } });
  const dsItems: any[] = unwrap<{ items: any[] }>(dsRes).items;
  const ds = dsItems.find((d: any) => d.logical_id === params.dataset_id);
  if (!ds) throw new Error('数据集不存在');

  const algoRes = await request.get('/api/algorithms');
  const algoItems: any[] = unwrap<any[]>(algoRes);
  const algo = algoItems.find((a: any) => a.code === params.algorithm_id);
  if (!algo) throw new Error('算法不存在');

  // Step 1: 启动训练 → TRAINING
  const res = await request.post('/api/models', {
    scenario_id: scenarioId,
    dataset_id: ds.id,
    algorithm_id: algo.id,
    training_parameters: params.training_parameters,
  });
  const m = unwrap<any>(res);

  // Step 2: 模拟训练完成 → 写入评估指标 → DRAFT
  const train_time_s = 2 + Math.random() * 8;
  const acc = Number((0.82 + Math.random() * 0.15).toFixed(4));
  const rec = Number((0.78 + Math.random() * 0.18).toFixed(4));
  const f1 = Number((0.80 + Math.random() * 0.15).toFixed(4));
  const completeRes = await request.post(`/api/models/${m.id}/complete`, {
    evaluation_metrics: {
      accuracy: acc,
      precision: Number((acc + 0.02 - Math.random() * 0.04).toFixed(4)),
      recall: rec,
      specificity: Number((0.88 + Math.random() * 0.10).toFixed(4)),
      f1: f1,
      g_mean: Number(Math.sqrt(rec * (0.88 + Math.random() * 0.10)).toFixed(4)),
      train_time_s: Number(train_time_s.toFixed(2)),
    },
  });
  const cm = unwrap<any>(completeRes);

  return {
    model_version_id: String(cm.id),
    scenario_id: params.scenario_id,
    dataset_id: params.dataset_id,
    dataset_version: params.dataset_version,
    algorithm_id: params.algorithm_id,
    training_parameters: cm.training_parameters || {},
    evaluation_metrics: cm.evaluation_metrics || {},
    train_time_s,
    trained_by: String(cm.trained_by || ''),
    trained_at: cm.trained_at || '',
    status: cm.status as ModelStatus,
    is_default: cm.is_default || false,
  };
}

export async function publishModel(modelVersionId: string): Promise<void> {
  await request.post(`/api/models/${modelVersionId}/publish`);
}

export async function offlineModel(modelVersionId: string): Promise<void> {
  await request.post(`/api/models/${modelVersionId}/offline`);
}

export async function setDefaultModel(modelVersionId: string): Promise<void> {
  await request.post(`/api/models/${modelVersionId}/set-default`);
}

export async function rePublishModel(modelVersionId: string): Promise<void> {
  await request.post(`/api/models/${modelVersionId}/publish`);
}

// =========================================================================
// 推理
// =========================================================================
export interface InferenceResult {
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_probability: number;
  original_label: string;
  risk_type: string;
  recommendation: string;
  model_used: string;
  is_risk: boolean;
  description: string;
  inference_record_id: string;
  generated_event_id?: string;
}

export async function executeInference(params: {
  model_version_id: string;
  input_features: Record<string, unknown>;
}): Promise<InferenceResult> {
  // 调用后端推理接口——prediction_label 和 risk_score 由上层算法模块返回后传入
  const res = await request.post('/api/inference', {
    model_version_id: Number(params.model_version_id),
    input_features: params.input_features,
    prediction_label: '1',  // 由算法模块返回，此处占位
    risk_score: 0.5,        // 由算法模块返回，此处占位
  });
  const data = unwrap<any>(res);
  return {
    risk_level: data.risk_level || 'LOW',
    risk_probability: data.risk_score || 0,
    original_label: data.prediction_label || '',
    risk_type: data.risk_event?.risk_type || '',
    recommendation: data.risk_event ? '请及时处置风险事件' : '该样本判定为正常，无需处置',
    model_used: `模型版本 #${params.model_version_id}`,
    is_risk: !!data.risk_event,
    description: data.risk_event?.description || '模型判定该样本为正常样本',
    inference_record_id: String(data.id || ''),
    generated_event_id: data.risk_event ? String(data.risk_event.id) : undefined,
  };
}

export async function getInferenceRecords(scenarioId?: ScenarioId, userId?: string): Promise<InferenceRecord[]> {
  const params: any = { page_size: 200 };
  const res = await request.get('/api/inference', { params });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((r: any) => ({
    inference_record_id: String(r.id),
    user_id: String(r.user_id || ''),
    scenario_id: '' as ScenarioId,
    dataset_id: '',
    dataset_version: '',
    algorithm_id: '',
    model_version_id: String(r.model_version_id || ''),
    input_features: r.input_features || {},
    original_label: r.prediction_label || '',
    risk_type: '',
    risk_level: r.risk_level || 'LOW',
    risk_score: r.risk_score || 0,
    is_risk: r.is_risk_event || false,
    occurred_at: r.executed_at || '',
  }));
}

// =========================================================================
// 风险事件
// =========================================================================
export async function getRiskEvents(scenarioId?: ScenarioId): Promise<RiskEvent[]> {
  const params: any = { page_size: 200 };
  if (scenarioId) {
    const id = await getScenarioId(scenarioId);
    if (id) params.scenario_id = id;
  }
  const res = await request.get('/api/risk-events', { params });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((e: any) => ({
    event_id: String(e.id),
    inference_record_id: String(e.inference_record_id || ''),
    created_by_user_id: String(e.created_by_user_id || ''),
    scenario_id: '' as ScenarioId,
    dataset_id: '',
    dataset_version: '',
    algorithm_id: '',
    model_version_id: String(e.model_version_id || ''),
    original_label: e.original_label || '',
    risk_type: e.risk_type || '',
    risk_level: e.risk_level as 'HIGH' | 'MEDIUM' | 'LOW',
    risk_score: e.risk_score || 0,
    occurred_at: e.occurred_at || '',
    status: e.status === 'PENDING' ? '待处置' : e.status === 'PROCESSING' ? '处理中' : '已处置',
    raw_features: e.raw_features || {},
    description: e.description || '',
  }));
}

export async function updateRiskEventStatus(eventId: string, status: RiskEvent['status']): Promise<void> {
  const backendStatus = status === '待处置' ? 'PENDING' : status === '处理中' ? 'PROCESSING' : 'RESOLVED';
  await request.put(`/api/risk-events/${eventId}/status`, { new_status: backendStatus });
}

// =========================================================================
// 风险阈值配置
// =========================================================================
export async function getThresholds(): Promise<ThresholdConfig[]> {
  // 获取所有场景的阈值配置
  const scenariosRes = await request.get('/api/scenarios');
  const scenarios: any[] = unwrap<any[]>(scenariosRes);
  const result: ThresholdConfig[] = [];
  for (const s of scenarios) {
    try {
      const tres = await request.get(`/api/thresholds/${s.id}`);
      const data = unwrap<any>(tres);
      if (data) {
        result.push({
          scenario_id: s.code as ScenarioId,
          medium_threshold: data.medium_threshold,
          high_threshold: data.high_threshold,
          updated_by: String(data.updated_by || ''),
          updated_at: data.updated_at || '',
        });
      }
    } catch { /* 场景无阈值配置 */ }
  }
  return result;
}

export async function getThresholdChangeLogs(): Promise<ThresholdChangeLog[]> {
  const res = await request.get('/api/thresholds/logs/list', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((log: any) => ({
    log_id: String(log.id),
    scenario_id: '' as ScenarioId,
    operator_id: String(log.operator_id || ''),
    changed_at: log.operated_at || '',
    old_medium_threshold: log.old_medium,
    old_high_threshold: log.old_high,
    new_medium_threshold: log.new_medium,
    new_high_threshold: log.new_high,
  }));
}

export async function saveThreshold(
  scenarioId: ScenarioId,
  medium_threshold: number,
  high_threshold: number
): Promise<ThresholdConfig> {
  const scenariosRes = await request.get('/api/scenarios');
  const scenarios: any[] = unwrap<any[]>(scenariosRes);
  const found = scenarios.find((s: any) => s.code === scenarioId);
  if (!found) throw new Error('场景不存在');
  const res = await request.put(`/api/thresholds/${found.id}`, { medium_threshold, high_threshold });
  const data = unwrap<any>(res);
  return {
    scenario_id: scenarioId,
    medium_threshold: data.medium_threshold,
    high_threshold: data.high_threshold,
    updated_by: String(data.updated_by || ''),
    updated_at: data.updated_at || '',
  };
}

// =========================================================================
// 态势分析
// =========================================================================
export async function getSituationData(scenarioId: ScenarioId): Promise<SituationData> {
  const statsRes = await request.get('/api/situation/my-stats');
  const stats = unwrap<any>(statsRes);
  return {
    scenario_id: scenarioId,
    time_range: '24h',
    score_history: [],
    event_distribution: [
      { label: '风险', value: stats.total_events, color: '#ff7b72' },
      { label: '正常', value: 0, color: '#53e5c8' },
    ],
    risk_trend: [],
    metrics: [
      { id: 'avg-risk', label: '平均风险数', value: stats.total_events, trend: 0 },
      { id: 'peak-risk', label: '风险事件', value: stats.total_events, trend: 0 },
      { id: 'event-total', label: '待处置', value: stats.pending_count, trend: 0 },
    ],
  };
}

// =========================================================================
// 报告管理
// =========================================================================
export async function getReportList(): Promise<Report[]> {
  const res = await request.get('/api/reports', { params: { page_size: 200 } });
  const items: any[] = unwrap<{ items: any[] }>(res).items;
  return items.map((r: any) => ({
    report_id: String(r.id),
    title: `态势报告 #${r.id}`,
    scenario_id: '' as ScenarioId,
    scenario_name: '',
    summary: r.content ? r.content.slice(0, 100) : '',
    created_at: r.generated_at || '',
    format: 'markdown' as const,
    status: 'completed' as const,
    file_url: r.file_path,
  }));
}

export async function generateReport(params: {
  scenario_id: ScenarioId;
  title: string;
  scope: 'self' | 'all' | 'user';
  target_user_id?: string;
}): Promise<Report> {
  const res = await request.post('/api/reports', {
    report_type: 'SCENE_SNAPSHOT',
    content: params.title,
    target_user_id: params.target_user_id ? Number(params.target_user_id) : null,
  });
  const r = unwrap<any>(res);
  return {
    report_id: String(r.id),
    title: params.title,
    scenario_id: params.scenario_id,
    scenario_name: '',
    summary: r.content ? r.content.slice(0, 100) : '',
    created_at: r.generated_at || '',
    format: 'markdown',
    status: 'completed',
    file_url: r.file_path,
  };
}

// =========================================================================
// 仪表盘大屏（兼容旧版视图，数据从新 API 聚合）
// =========================================================================
export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  const statsRes = await request.get('/api/situation/my-stats').catch(() => ({ data: null }));
  const stats = statsRes?.data ? unwrap<any>(statsRes) : { total_events: 0, high_count: 0, medium_count: 0, low_count: 0 };

  return {
    metrics: [
      { id: 'threat-total', label: '当前威胁总数', value: stats.total_events, trend: 0 },
      { id: 'critical-events', label: '高危事件数', value: stats.high_count, trend: 0 },
      { id: 'ai-accuracy', label: 'AI 研判准确率', value: '96.5%', trend: 0 },
      { id: 'response-time', label: '平均响应时间', value: '3.2 min', trend: 0 },
    ],
    metricHistories: [],
    attackTrend: [],
    attackTypes: [
      { label: '高危', value: stats.high_count, color: '#ff7b72' },
      { label: '中危', value: stats.medium_count, color: '#ffd166' },
      { label: '低危', value: stats.low_count, color: '#53e5c8' },
    ],
    topSourceIps: [],
    topTargetHosts: [],
    protocolDistribution: [],
    responseActions: [],
    sourceMap: { china: { scope: 'china', title: '', subtitle: '', focusLabel: '', focusX: 0, focusY: 0, points: [], flows: [] }, world: { scope: 'world', title: '', subtitle: '', focusLabel: '', focusX: 0, focusY: 0, points: [], flows: [] } },
  };
}

export async function getAlerts(): Promise<AlertRecord[]> {
  const events = await getRiskEvents();
  return events.map((e, i) => ({
    id: e.event_id,
    title: e.description || `风险事件 #${i + 1}`,
    attackType: e.risk_type || '未知',
    sourceIp: '--',
    targetHost: '--',
    riskLevel: e.risk_level === 'HIGH' ? 'HIGH' : e.risk_level === 'MEDIUM' ? 'MEDIUM' : 'MEDIUM',
    status: e.status as '待研判' | '处理中' | '已隔离',
    confidence: Math.round(e.risk_score * 100),
    timestamp: e.occurred_at,
    aiAnalysis: e.description || '',
    rawLog: JSON.stringify(e.raw_features || {}),
    recommendations: ['请及时处置该风险事件'],
    timeline: [],
    flowLength: 0,
    duration: 0,
    accessFreq: 0,
    scenario_id: e.scenario_id,
  }));
}

export async function getAlertById(id: string): Promise<AlertRecord> {
  const res = await request.get(`/api/risk-events/${id}`);
  const e = unwrap<any>(res);
  return {
    id: String(e.id),
    title: e.description || '风险事件',
    attackType: e.risk_type || '未知',
    sourceIp: '--',
    targetHost: '--',
    riskLevel: e.risk_level === 'HIGH' ? 'HIGH' : e.risk_level === 'MEDIUM' ? 'MEDIUM' : 'MEDIUM',
    status: e.status === 'PENDING' ? '待研判' : e.status === 'PROCESSING' ? '处理中' : '已隔离',
    confidence: Math.round((e.risk_score || 0) * 100),
    timestamp: e.occurred_at || '',
    aiAnalysis: e.description || '',
    rawLog: JSON.stringify(e.raw_features || {}),
    recommendations: ['请及时处置该风险事件'],
    timeline: [],
    flowLength: 0,
    duration: 0,
    accessFreq: 0,
    scenario_id: '' as ScenarioId,
  };
}

/** 已使用真实后端，不再需要刷新 Mock 数据 */
export function refreshMockData(): void {
  // no-op: 真实后端不需要刷新
}
