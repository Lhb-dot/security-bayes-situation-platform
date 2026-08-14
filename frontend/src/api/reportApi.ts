/**
 * reportApi.ts — 报告接口（与后端 /api/v1/reports 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8.5）：普通用户仅本人数据；管理员可全平台或指定用户。
 */
import request, { unwrapData } from '@/utils/request';
import type { Report } from '@/types/security';

/** 报告列表（GET /reports，普通用户：本人生成或定向给自己的报告） */
export const getReportList = async (params?: {
  target_user_id?: string;
  page?: number;
  page_size?: number;
}): Promise<Report[]> => {
  const data = await unwrapData(await request.get('/api/v1/reports', { params }));
  return data.items ?? [];
};

/** 报告详情（GET /reports/{report_id}） */
export const getReportDetail = async (reportId: string): Promise<Report> =>
  unwrapData(await request.get(`/api/v1/reports/${reportId}`));

/** 生成态势报告（POST /reports，普通用户仅本人数据） */
export const generateReport = async (params: {
  report_type: string;
  content: string;
  target_user_id?: string;
  file_path?: string;
}): Promise<Report> => unwrapData(await request.post('/api/v1/reports', params));

/** 删除报告（DELETE /reports/{report_id}，生成者本人或管理员） */
export const removeReport = async (reportId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/reports/${reportId}`));
