/**
 * datasetApi.ts — 数据集接口（与后端 /api/v1/datasets 对齐）
 *
 * 将数据库返回结构映射为前端 Dataset / DatasetField / DataPreview 契约，
 * 供数据集中心、详情页、字段预览与数据预览使用。
 */
import request, { unwrapData } from '@/utils/request';
import type {
  DataPreview,
  Dataset,
  DatasetField,
  DatasetVersion,
  ScenarioId,
} from '@/types/security';

/** 后端 dataset 行（含 Service 补充展示字段） */
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
  uploaded_at: string;
  status: string;
  name?: string;
  field_count?: number;
  data_format?: string;
  record_count?: number;
  referenced?: boolean;
  enabled?: boolean;
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

const SCENARIO_CODE_BY_ID: Record<number, ScenarioId> = {
  1: 'network_security',
  2: 'power_system',
  3: 'flightdeck_operation',
  4: 'geological_risk',
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
    scenarioIdByCodeCache = {
      network_security: 1,
      power_system: 2,
      flightdeck_operation: 3,
      geological_risk: 4,
    };
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

/** 后端 fields_schema → 前端 DatasetField */
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

/** 前端字段 → 后端 fields_schema */
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
  return {
    dataset_id: String(item.id),
    name: item.name || item.logical_id,
    description: item.scenario_name
      ? `${item.scenario_name} · ${item.logical_id}`
      : `${item.logical_id}（v${item.version}）`,
    scenario_id: scenarioId,
    record_count: item.record_count ?? 0,
    field_count: item.field_count ?? fields.length,
    fields,
    created_at: formatUploadedAt(item.uploaded_at),
    data_format: inferFormat(item.file_path, item.data_format),
    dataset_version: `v${item.version}`,
    uploaded_by: String(item.uploaded_by ?? ''),
    uploaded_at: formatUploadedAt(item.uploaded_at),
    enabled: item.enabled ?? item.status === 'ACTIVE',
    referenced: Boolean(item.referenced),
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
    uploaded_at: base.uploaded_at,
    enabled: base.enabled,
    referenced: base.referenced,
  };
};


const isNumericId = (value: string | number): boolean => /^\d+$/.test(String(value));

/** 将 numeric id / logical_id 解析为后端主键 id */
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

/** 数据集列表（默认返回每个 logical_id 的最新版本） */
export const getDatasetList = async (params?: {
  scenario_id?: ScenarioId;
  page?: number;
  page_size?: number;
  all_versions?: boolean;
}): Promise<Dataset[]> => {
  await ensureScenarioMaps();
  const scenarioNumeric =
    params?.scenario_id != null ? scenarioIdByCodeCache?.[params.scenario_id] : undefined;
  const data = await unwrapData(
    await request.get('/api/v1/datasets', {
      params: {
        scenario_id: scenarioNumeric,
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 200,
      },
    })
  );
  const items = (data.items ?? []) as ApiDataset[];
  const selected = params?.all_versions ? items : latestByLogicalId(items);
  return selected.map(mapApiDataset);
};

/** 原始列表（含全部版本，供版本管理） */
export const getDatasetRawList = async (params?: {
  scenario_id?: ScenarioId;
  page_size?: number;
}): Promise<ApiDataset[]> => {
  await ensureScenarioMaps();
  const scenarioNumeric =
    params?.scenario_id != null ? scenarioIdByCodeCache?.[params.scenario_id] : undefined;
  const data = await unwrapData(
    await request.get('/api/v1/datasets', {
      params: {
        scenario_id: scenarioNumeric,
        page: 1,
        page_size: params?.page_size ?? 200,
      },
    })
  );
  return (data.items ?? []) as ApiDataset[];
};

/** 数据集详情（GET /datasets/{dataset_id}，含字段结构） */
export const getDatasetDetail = async (datasetId: string | number): Promise<Dataset> => {
  await ensureScenarioMaps();
  const pk = await resolveDatasetPk(datasetId);
  const item = (await unwrapData(
    await request.get(`/api/v1/datasets/${pk}`)
  )) as ApiDataset;
  return mapApiDataset(item);
};

/** 字段预览（兼容旧调用名 getDatasetFields） */
export const getDatasetFields = async (
  datasetId: string | number,
  _datasetVersion?: string
): Promise<DatasetField[]> => {
  const pk = await resolveDatasetPk(datasetId);
  const data = await unwrapData(
    await request.get(`/api/v1/datasets/${pk}/fields-schema`)
  );
  return mapFields(data.fields_schema as ApiField[] | undefined, data.label_field);
};

export const getDatasetFieldsSchema = getDatasetFields;

/** 数据内容预览（真实 ARFF 分页） */
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

/** 版本列表：同一 logical_id 下全部版本 */
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

/** 上传数据集（POST /datasets） */
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
  visibility?: string;
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
      scenario_id: scenarioId,
      file_path: params.file_path,
      fields_schema: fieldsSchema,
      label_field: labelField,
      visibility: params.visibility,
    })
  )) as ApiDataset;
  return mapApiDataset(item);
};

/** 创建数据集版本（PUT /datasets/{dataset_id}） */
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

/** 停用数据集版本 */
export const disableDataset = async (datasetId: string | number): Promise<void> => {
  const pk = await resolveDatasetPk(datasetId);
  await unwrapData(await request.post(`/api/v1/datasets/${pk}/disable`));
};

export const disableDatasetVersion = async (versionId: string | number): Promise<void> =>
  disableDataset(versionId);

/** 删除数据集版本 */
export const removeDataset = async (datasetId: string | number): Promise<void> => {
  const pk = await resolveDatasetPk(datasetId);
  await unwrapData(await request.delete(`/api/v1/datasets/${pk}`));
};

export const deleteDatasetVersion = async (versionId: string | number): Promise<void> =>
  removeDataset(versionId);
