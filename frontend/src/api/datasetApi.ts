// 数据集接口（后端 /api/v1/datasets）。数据库行在这里映射成前端 Dataset / DatasetField /
// DataPreview 三套契约，数据集中心、详情页、字段预览、数据预览都消费这一层。
import request, { getCsrfToken, unwrapData } from '@/utils/request';
import { SCENARIO_CODE_BY_ID } from '@/api/scenarioApi';
import type {
  DataPreview,
  Dataset,
  DatasetField,
  DatasetVersion,
  ScenarioId,
} from '@/types/security';

// 后端 dataset 行（含 Service 补充展示字段）
interface ApiDataset {
  id: number;
  logical_id: string;
  version: number;
  scenario_id: number;
  scenario_code?: ScenarioId | string | null;
  scenario_name?: string | null;
  file_path: string;
  fields_schema?: ApiField[];
  label_field: string;
  visibility?: string;
  uploaded_by: number | string;
  uploader_name?: string | null;
  uploaded_at: string;
  status: string;
  name?: string;
  file_name?: string;
  field_count?: number;
  data_format?: string;
  record_count?: number;
  referenced?: boolean;
  enabled?: boolean;
  change_type?: string | null;
  change_type_label?: string | null;
  is_breaking?: boolean;
  base_version_id?: number | null;
}

interface ApiField {
  name: string;
  type?: string;
  role?: string;
  enum_values?: string[];
  sample_values?: string[];
  description?: string;
}

interface ApiPreview {
  dataset_id: number;
  logical_id: string;
  version: number;
  label_field: string;
  fields_schema?: ApiField[];
  rows: Array<Record<string, string | number | null>>;
  page: number;
  page_size: number;
  total: number;
}

interface ApiScenario {
  id: number;
  code: ScenarioId | string;
  name: string;
  access_status?: string;
}

// Invert the id -> code table. Keep one copy, otherwise the two maps drift apart.
const invertScenarioCodeMap = (
  byId: Record<number, ScenarioId>
): Partial<Record<ScenarioId, number>> => {
  const byCode: Partial<Record<ScenarioId, number>> = {};
  for (const [id, code] of Object.entries(byId)) byCode[code] = Number(id);
  return byCode;
};

let scenarioCodeByIdCache: Record<number, ScenarioId> | null = null;
let scenarioIdByCodeCache: Partial<Record<ScenarioId, number>> | null = null;

const ensureScenarioMaps = async (): Promise<void> => {
  if (scenarioCodeByIdCache && scenarioIdByCodeCache) return;
  try {
    const list = (await unwrapData(await request.get('/api/v1/scenarios'))) as ApiScenario[];
    const byId: Record<number, ScenarioId> = { ...SCENARIO_CODE_BY_ID };
    const byCode: Partial<Record<ScenarioId, number>> = {};
    for (const s of list ?? []) {
      const code = s.code as ScenarioId;
      byId[s.id] = code;
      byCode[code] = s.id;
    }
    scenarioCodeByIdCache = byId;
    scenarioIdByCodeCache = byCode;
  } catch {
    scenarioCodeByIdCache = { ...SCENARIO_CODE_BY_ID };
    scenarioIdByCodeCache = invertScenarioCodeMap(SCENARIO_CODE_BY_ID);
  }
};

const resolveScenarioCode = (item: ApiDataset): ScenarioId => {
  if (item.scenario_code && typeof item.scenario_code === 'string') {
    return item.scenario_code as ScenarioId;
  }
  return (
    scenarioCodeByIdCache?.[item.scenario_id] ??
    SCENARIO_CODE_BY_ID[item.scenario_id] ??
    'network_security'
  );
};

const mapFieldType = (type?: string): string => {
  const t = (type || 'string').toLowerCase();
  if (t === 'numeric' || t === 'real' || t === 'float' || t === 'double') return 'float';
  if (t === 'integer' || t === 'int') return 'int';
  if (t === 'enum') return 'enum';
  if (t === 'bool' || t === 'boolean') return 'bool';
  return t;
};

// 后端 fields_schema -> 前端 DatasetField
export const mapApiField = (field: ApiField, labelField?: string): DatasetField => {
  const isLabel =
    field.role === 'label' || (!!labelField && field.name === labelField);
  const samples = field.sample_values ?? [];
  return {
    field_name: field.name,
    field_type: mapFieldType(field.type),
    field_role: isLabel ? '分类标签' : '输入特征',
    description: field.description || '',
    sample_value: samples.length ? String(samples[0]) : '',
    nullable: !isLabel,
    enum_values: field.enum_values?.length ? field.enum_values.map(String) : undefined,
  };
};

const mapFields = (fields: ApiField[] | undefined, labelField?: string): DatasetField[] =>
  (fields ?? []).map((f) => mapApiField(f, labelField));

// 前端字段 -> 后端 fields_schema
export const toApiFields = (
  fields: Array<{
    field_name: string;
    field_type: string;
    field_role: '输入特征' | '分类标签';
    description?: string;
    enum_values?: string[];
  }>
): ApiField[] =>
  fields.map((f) => ({
    name: f.field_name,
    type: f.field_type === 'float' || f.field_type === 'int' ? 'numeric' : f.field_type,
    role: f.field_role === '分类标签' ? 'label' : 'feature',
    enum_values: f.enum_values ?? [],
    sample_values: [],
    description: f.description || '',
  }));

const inferFormat = (filePath: string, fallback?: string): Dataset['data_format'] => {
  const suffix = filePath.replace(/\\/g, '/').split('.').pop()?.toLowerCase();
  if (suffix === 'csv' || suffix === 'arff' || suffix === 'json') return suffix;
  if (fallback === 'csv' || fallback === 'arff' || fallback === 'json') return fallback;
  return 'arff';
};

const formatUploadedAt = (value: string): string => {
  if (!value) return '';
  return value.includes('T') ? value.replace('T', ' ').replace('Z', '').slice(0, 19) : value;
};

export const mapApiDataset = (item: ApiDataset): Dataset => {
  const fields = mapFields(item.fields_schema, item.label_field);
  const scenarioId = resolveScenarioCode(item);
  // 数据集名统一取后端下发的 name（= logical_id）
  const displayName = item.name || item.logical_id;
  // 原始文件名：优先用后端下发的 file_name，缺失时从 file_path 取 basename 兜底
  const fileName =
    item.file_name || item.file_path?.replace(/\\/g, '/').split('/').pop() || item.logical_id;
  return {
    dataset_id: String(item.id),
    name: displayName,
    file_name: fileName,
    description: item.scenario_name
      ? `${item.scenario_name} · ${displayName}`
      : `${displayName}（v${item.version}）`,
    scenario_id: scenarioId,
    record_count: item.record_count ?? 0,
    field_count: item.field_count ?? fields.length,
    fields,
    created_at: formatUploadedAt(item.uploaded_at),
    data_format: inferFormat(item.file_path, item.data_format),
    dataset_version: `v${item.version}`,
    uploaded_by: String(item.uploaded_by ?? ''),
    uploader_name: item.uploader_name ?? '',
    uploaded_at: formatUploadedAt(item.uploaded_at),
    enabled: item.enabled ?? item.status === 'ACTIVE',
    referenced: Boolean(item.referenced),
    change_type: item.change_type ?? null,
    change_type_label: item.change_type_label ?? null,
    is_breaking: Boolean(item.is_breaking),
    base_version_id: item.base_version_id ?? null,
  };
};

export const mapApiDatasetVersion = (item: ApiDataset): DatasetVersion => {
  const base = mapApiDataset(item);
  return {
    dataset_version_id: String(item.id),
    dataset_id: item.logical_id,
    dataset_version: base.dataset_version,
    name: base.name,
    scenario_id: base.scenario_id,
    data_format: base.data_format,
    file_path: item.file_path,
    record_count: base.record_count,
    field_count: base.field_count,
    fields: base.fields,
    uploaded_by: base.uploaded_by,
    uploader_name: base.uploader_name,
    uploaded_at: base.uploaded_at,
    enabled: base.enabled,
    referenced: base.referenced,
    change_type: base.change_type,
    change_type_label: base.change_type_label,
    is_breaking: base.is_breaking,
    base_version_id: base.base_version_id,
  };
};


const isNumericId = (value: string | number): boolean => /^\d+$/.test(String(value));

// 将 numeric id / logical_id 解析为后端主键 id
const resolveDatasetPk = async (datasetId: string | number): Promise<number> => {
  if (isNumericId(datasetId)) return Number(datasetId);
  const raw = await getDatasetRawList({ page_size: 200 });
  const matched = raw
    .filter((d) => d.logical_id === String(datasetId))
    .sort((a, b) => b.version - a.version);
  if (!matched.length) throw new Error(`数据集不存在: ${datasetId}`);
  return matched[0].id;
};

const latestByLogicalId = (items: ApiDataset[]): ApiDataset[] => {
  const map = new Map<string, ApiDataset>();
  for (const item of items) {
    const prev = map.get(item.logical_id);
    if (!prev || item.version > prev.version) {
      map.set(item.logical_id, item);
    }
  }
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
};

// 拉取数据集原始行（getDatasetList / getDatasetRawList 共用的取数与参数组装）
const fetchDatasetItems = async (params?: {
  scenario_id?: ScenarioId;
  page?: number;
  page_size?: number;
}): Promise<ApiDataset[]> => {
  await ensureScenarioMaps();
  const scenarioNumeric =
    params?.scenario_id != null ? scenarioIdByCodeCache?.[params.scenario_id] : undefined;
  const data = await unwrapData<{ items?: ApiDataset[] }>(
    await request.get('/api/v1/datasets', {
      params: {
        scenario_id: scenarioNumeric,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 200,
      },
    })
  );
  return (data.items ?? []) as ApiDataset[];
};

// 数据集列表（默认返回每个 logical_id 的最新版本）
export const getDatasetList = async (params?: {
  scenario_id?: ScenarioId;
  page?: number;
  page_size?: number;
  all_versions?: boolean;
}): Promise<Dataset[]> => {
  const items = await fetchDatasetItems(params);
  const selected = params?.all_versions ? items : latestByLogicalId(items);
  return selected.map(mapApiDataset);
};

// 原始列表（含全部版本，供版本管理）
export const getDatasetRawList = async (params?: {
  scenario_id?: ScenarioId;
  page_size?: number;
}): Promise<ApiDataset[]> =>
  fetchDatasetItems({ scenario_id: params?.scenario_id, page: 1, page_size: params?.page_size ?? 200 });

// 数据集详情（GET /datasets/{dataset_id}，含字段结构）
export const getDatasetDetail = async (datasetId: string | number): Promise<Dataset> => {
  await ensureScenarioMaps();
  const pk = await resolveDatasetPk(datasetId);
  const item = (await unwrapData(
    await request.get(`/api/v1/datasets/${pk}`)
  )) as ApiDataset;
  return mapApiDataset(item);
};

// 字段预览（兼容旧调用名 getDatasetFields）
export const getDatasetFields = async (
  datasetId: string | number,
  _datasetVersion?: string
): Promise<DatasetField[]> => {
  const pk = await resolveDatasetPk(datasetId);
  const data = await unwrapData<{ fields_schema?: ApiField[]; label_field?: string }>(
    await request.get(`/api/v1/datasets/${pk}/fields-schema`)
  );
  return mapFields(data.fields_schema as ApiField[] | undefined, data.label_field);
};

export const getDatasetFieldsSchema = getDatasetFields;

// 数据内容预览（真实 ARFF 分页）
export const getDatasetPreview = async (
  datasetId: string | number,
  params: { page: number; page_size: number }
): Promise<DataPreview> => {
  const pk = await resolveDatasetPk(datasetId);
  const data = (await unwrapData(
    await request.get(`/api/v1/datasets/${pk}/preview`, {
      params: {
        page: params.page,
        page_size: Math.min(50, Math.max(1, params.page_size)),
      },
    })
  )) as ApiPreview;
  return {
    total: data.total ?? 0,
    page: data.page ?? params.page,
    page_size: data.page_size ?? params.page_size,
    rows: (data.rows ?? []).map((row) => {
      const out: Record<string, string | number> = {};
      Object.entries(row || {}).forEach(([k, v]) => {
        out[k] = v == null ? '' : (v as string | number);
      });
      return out;
    }),
    label_field: data.label_field ?? '',
  };
};

// 版本列表：同一 logical_id 下全部版本
export const getDatasetVersions = async (datasetId?: string): Promise<DatasetVersion[]> => {
  await ensureScenarioMaps();
  const raw = await getDatasetRawList({ page_size: 200 });
  if (!datasetId) {
    return raw.map(mapApiDatasetVersion);
  }
  // datasetId 可能是 numeric id 或 logical_id
  const self = raw.find((d) => String(d.id) === String(datasetId) || d.logical_id === datasetId);
  const logicalId = self?.logical_id ?? datasetId;
  return raw
    .filter((d) => d.logical_id === logicalId)
    .sort((a, b) => b.version - a.version)
    .map(mapApiDatasetVersion);
};

// 上传数据集（POST /datasets）
export const uploadDataset = async (params: {
  dataset_id?: string;
  logical_id?: string;
  name?: string;
  scenario_id: ScenarioId | number;
  data_format?: Dataset['data_format'];
  record_count?: number;
  file_path: string;
  fields: Array<{
    field_name: string;
    field_type: string;
    field_role: '输入特征' | '分类标签';
    description?: string;
    enum_values?: string[];
  }>;
  fields_schema?: ApiField[];
  label_field?: string;
}): Promise<Dataset> => {
  await ensureScenarioMaps();
  const logicalId = (params.logical_id || params.dataset_id || '').trim();
  if (!logicalId) throw new Error('数据集编码不能为空');
  const scenarioId =
    typeof params.scenario_id === 'number'
      ? params.scenario_id
      : scenarioIdByCodeCache?.[params.scenario_id];
  if (!scenarioId) throw new Error('所属场景无效');
  const fieldsSchema = params.fields_schema ?? toApiFields(params.fields);
  const labelField =
    params.label_field ||
    params.fields.find((f) => f.field_role === '分类标签')?.field_name ||
    '';
  if (!labelField) throw new Error('必须指定分类标签字段');
  const item = (await unwrapData(
    await request.post('/api/v1/datasets', {
      logical_id: logicalId,
      name: params.name?.trim() || undefined,
      scenario_id: scenarioId,
      file_path: params.file_path,
      fields_schema: fieldsSchema,
      label_field: labelField,
    })
  )) as ApiDataset;
  return mapApiDataset(item);
};

// 上传数据集文件（multipart，后端自动识别 ARFF/CSV 并解析字段结构）
export const uploadDatasetFile = async (params: {
  file: File;
  logical_id: string;
  name?: string;
  scenario_id: number | string;
  label_field: string;
}): Promise<Dataset> => {
  await ensureScenarioMaps();
  // 后端 scenario_id 是数字 ID，这里把场景编码（如 power_system）转成数字
  const scenarioNumeric =
    typeof params.scenario_id === 'number'
      ? params.scenario_id
      : scenarioIdByCodeCache?.[params.scenario_id as ScenarioId];
  if (scenarioNumeric == null) throw new Error('所属场景无效');
  const form = new FormData();
  form.append('file', params.file);
  form.append('logical_id', params.logical_id);
  form.append('scenario_id', String(scenarioNumeric));
  form.append('label_field', params.label_field);
  if (params.name?.trim()) form.append('name', params.name.trim());
  const item = (await unwrapData(
    await request.post('/api/v1/datasets/upload', form)
  )) as ApiDataset;
  return mapApiDataset(item);
};

// 创建数据集版本（PUT /datasets/{dataset_id}）
export const createDatasetVersion = async (
  datasetId: string | number,
  fieldsOrParams?:
    | DatasetField[]
    | {
        file_path?: string;
        fields_schema?: ApiField[];
        fields?: DatasetField[];
        label_field?: string;
      }
): Promise<DatasetVersion> => {
  let payload: { file_path?: string; fields_schema?: ApiField[]; label_field?: string } = {};
  if (Array.isArray(fieldsOrParams)) {
    payload = {
      fields_schema: toApiFields(fieldsOrParams),
      label_field: fieldsOrParams.find((f) => f.field_role === '分类标签')?.field_name,
    };
  } else if (fieldsOrParams) {
    payload = {
      file_path: fieldsOrParams.file_path,
      fields_schema:
        fieldsOrParams.fields_schema ??
        (fieldsOrParams.fields ? toApiFields(fieldsOrParams.fields) : undefined),
      label_field:
        fieldsOrParams.label_field ||
        fieldsOrParams.fields?.find((f) => f.field_role === '分类标签')?.field_name,
    };
  }
  const pk = await resolveDatasetPk(datasetId);
  const item = (await unwrapData(
    await request.put(`/api/v1/datasets/${pk}`, payload)
  )) as ApiDataset;
  return mapApiDatasetVersion(item);
};

// 追加样本（POST /datasets/{id}/revisions/append，multipart 增量文件）。
// 增量文件的字段名和顺序必须跟当前数据集一致。是否新建版本由后端定：
// 没被模型引用就原地更新、版本号不变，被引用了才自动开一版。
export const appendDatasetRows = async (
  datasetId: string | number,
  file: File
): Promise<DatasetVersion> => {
  const pk = await resolveDatasetPk(datasetId);
  const form = new FormData();
  form.append('file', file);
  const item = (await unwrapData(
    await request.post(`/api/v1/datasets/${pk}/revisions/append`, form)
  )) as ApiDataset;
  return mapApiDatasetVersion(item);
};

// 数据集迭代记录（GET /datasets/{id}/revisions）：含原地更新，用于审计追溯。
export interface DatasetRevisionItem {
  id: number;
  dataset_id: number;
  change_type: string;
  change_type_label: string;
  is_breaking: boolean;
  mode: 'in_place' | 'new_version';
  result_dataset_id: number | null;
  reason: string | null;
  summary: string | null;
  created_at: string | null;
}

export const getDatasetRevisions = async (
  datasetId: string | number
): Promise<DatasetRevisionItem[]> => {
  const pk = await resolveDatasetPk(datasetId);
  const data = (await unwrapData(
    await request.get(`/api/v1/datasets/${pk}/revisions`)
  )) as { items?: DatasetRevisionItem[] };
  return data?.items ?? [];
};

// 停用数据集版本
export const disableDataset = async (datasetId: string | number): Promise<void> => {
  const pk = await resolveDatasetPk(datasetId);
  await unwrapData(await request.post(`/api/v1/datasets/${pk}/disable`));
};

export const disableDatasetVersion = async (versionId: string | number): Promise<void> =>
  disableDataset(versionId);

// 删除数据集版本
export const removeDataset = async (datasetId: string | number): Promise<void> => {
  const pk = await resolveDatasetPk(datasetId);
  await unwrapData(await request.delete(`/api/v1/datasets/${pk}`));
};

export const deleteDatasetVersion = async (versionId: string | number): Promise<void> =>
  removeDataset(versionId);


// 数据集 AI 解析结果（读缓存，不触发 AI）
export interface DatasetAnalysisResponse {
  dataset_id: number;
  name: string;
  available: boolean;
  source?: 'ai' | 'fallback' | 'cached' | null;
  markdown?: string | null;
  generated_at?: string | null;
}

// 读取已保存的数据集 AI 解析结果；没生成过时 available=false，页面显示空状态。
export const getDatasetAiAnalysis = async (
  datasetId: string | number,
): Promise<DatasetAnalysisResponse> => {
  const pk = await resolveDatasetPk(datasetId);
  return unwrapData(
    await request.get(`/api/v1/datasets/${pk}/ai-analysis`)
  ) as DatasetAnalysisResponse;
};

// 数据集 AI 解析（算法适配）流式回调
export interface DatasetAnalysisStreamHandlers {
  onStart?: (data: Record<string, unknown>) => void;
  // 推理型模型的思维链，只用于展示"正在生成"
  onReasoning?: (content: string) => void;
  onDelta?: (content: string) => void;
  onError?: (message: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
}

// 流式生成数据集算法适配解析（POST /datasets/{pk}/ai-analysis/stream）。
// 跟模型评价、推理解释共用一套 SSE：start -> (reasoning | delta)* -> done。
// 中途可能先来个 error 表示 AI 不可用、已经退回规则模板，后面正文和 done 照样会有。
export const streamDatasetAiAnalysis = async (
  datasetId: string | number,
  handlers: DatasetAnalysisStreamHandlers,
  signal?: AbortSignal,
): Promise<void> => {
  const pk = await resolveDatasetPk(datasetId);
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const csrf = getCsrfToken();
  const response = await fetch(`${baseUrl}/api/v1/datasets/${pk}/ai-analysis/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
    },
    signal,
  });
  if (!response.ok || !response.body) {
    let message = `AI 解析请求失败（${response.status}）`;
    try {
      const payload = (await response.json()) as { message?: string };
      if (payload?.message) message = String(payload.message);
    } catch {
      // 非 JSON 响应，保留默认文案
    }
    throw new Error(message);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const consume = (raw: string) => {
    buffer += raw;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? '';
    for (const block of blocks) {
      const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const dataText = block.match(/^data:\s*(.+)$/m)?.[1]?.trim();
      if (!event || !dataText) continue;
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(dataText) as Record<string, unknown>;
      } catch {
        continue;
      }
      if (event === 'start') handlers.onStart?.(data);
      else if (event === 'reasoning' && typeof data.content === 'string') handlers.onReasoning?.(data.content);
      else if (event === 'delta' && typeof data.content === 'string') handlers.onDelta?.(data.content);
      else if (event === 'error') handlers.onError?.(String(data.message ?? 'AI 解析失败'));
      else if (event === 'done') handlers.onDone?.(data);
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    consume(decoder.decode(value, { stream: true }));
  }
  consume(decoder.decode());
};
