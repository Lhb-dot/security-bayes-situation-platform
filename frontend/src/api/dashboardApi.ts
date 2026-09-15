import request, { unwrapData } from '@/utils/request';
import { resolveScenarioId } from '@/api/scenarioApi';

export interface DashboardOverview {
  totals: Record<string, number>;
  scenarios: Array<Record<string, any>>;
}

export interface ScenarioProfile {
  scenario_id: number;
  scenario_code: string;
  scenario_name: string;
  dataset_count: number;
  sample_count: number;
  risk_type: string | null;
  datasets: Array<Record<string, any>>;
  [key: string]: any;
}

export interface ScenarioWorkspace {
  scenario_id: number;
  risk_type: string | null;
  summary: Record<string, any>;
  recent_events: Array<Record<string, any>>;
  [key: string]: any;
}

export const getAdminDashboard = async (): Promise<DashboardOverview> =>
  unwrapData(await request.get('/api/v1/dashboard/admin/overview'));

export const getScenarioProfile = async (scenarioId: number | string): Promise<ScenarioProfile> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/profile`));
};

export const getScenarioWorkspace = async (scenarioId: number | string): Promise<ScenarioWorkspace> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/workspace`));
};
