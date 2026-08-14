/**
 * userApi.ts — 用户管理接口（与后端 /api/v1/users 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含权限/过滤逻辑。
 * 权限边界由后端强制（需求 6.5.2），前端不重复判断。
 */
import request, { unwrapData } from '@/utils/request';
import type { UserAccount, UserRole } from '@/types/security';

/** 查看本人信息（GET /users/me，登录用户） */
export const getMe = async (): Promise<UserAccount> =>
  unwrapData(await request.get('/api/v1/users/me'));

/** 用户列表（GET /users，仅管理员；支持分页与用户名模糊搜索） */
export const getUserList = async (params?: {
  page?: number;
  page_size?: number;
  keyword?: string;
}): Promise<UserAccount[]> => {
  const data = await unwrapData(await request.get('/api/v1/users', { params }));
  return data.items ?? [];
};

/** 创建用户（POST /users，仅管理员） */
export const createUser = async (params: {
  username: string;
  password: string;
  role: UserRole;
}): Promise<UserAccount> => unwrapData(await request.post('/api/v1/users', params));

/** 修改本人密码（PUT /users/{user_id}/password，需验证旧密码） */
export const changePassword = async (
  userId: string,
  params: { old_password: string; new_password: string }
): Promise<void> => unwrapData(await request.put(`/api/v1/users/${userId}/password`, params));

/** 重置用户密码（PUT /users/{user_id}/reset-password，仅管理员，无需旧密码） */
export const resetPassword = async (userId: string, newPassword: string): Promise<void> =>
  unwrapData(await request.put(`/api/v1/users/${userId}/reset-password`, { new_password: newPassword }));

/** 启用/禁用账号（PUT /users/{user_id}/status，仅管理员） */
export const setUserStatus = async (userId: string, status: 'active' | 'disabled'): Promise<void> =>
  unwrapData(await request.put(`/api/v1/users/${userId}/status`, { status }));

// TODO 后端未提供登录路由（无 /auth/login）：登录/退出继续走 mockApi，
// 由 Task 004 userStore 过渡，届时再补真实接口封装。
