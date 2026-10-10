import request, { setCsrfToken, unwrapData } from '@/utils/request';
import type { UserAccount, UserRole } from '@/types/security';

interface ApiUser {
  id: number;
  username: string;
  role: UserRole;
  status: 'ENABLED' | 'DISABLED';
  scenario_id: number | null;
  scenario_code?: string | null;
  created_at: string;
  updated_at: string;
}

interface AuthPayload {
  user: ApiUser;
  expires_in?: number;
  csrf_token?: string;
}

export interface UserListResult {
  items: UserAccount[];
  total: number;
  page: number;
  page_size: number;
}

export const SESSION_QUERY_TIMEOUT_MS = 10_000;
export const USER_LIST_QUERY_TIMEOUT_MS = 15_000;

export interface AuthRequestContext {
  signal: AbortSignal;
  isCurrent: () => boolean;
}

const toUserAccount = (user: ApiUser): UserAccount => ({
  id: user.id,
  user_id: String(user.id),
  username: user.username,
  display_name: user.username,
  role: user.role,
  status: user.status === 'ENABLED' ? 'active' : 'disabled',
  created_at: user.created_at,
  created_by: '',
  scenario_id: user.scenario_id,
  scenario_code: (user.scenario_code as UserAccount['scenario_code']) ?? null,
  scenario_ids: user.scenario_code
    ? [user.scenario_code as NonNullable<UserAccount['scenario_code']>]
    : [],
});

const unwrapUser = (payload: AuthPayload | ApiUser): UserAccount =>
  toUserAccount('user' in payload ? payload.user : payload);

export const login = async (username: string, password: string, context?: AuthRequestContext): Promise<UserAccount> => {
  const payload = await unwrapData(
    await request.post('/api/v1/auth/login', { username, password }, { signal: context?.signal }),
  ) as AuthPayload;
  if (context?.isCurrent() ?? true) setCsrfToken(payload.csrf_token ?? null);
  return unwrapUser(payload);
};

export const getMe = async (options?: { signal?: AbortSignal }): Promise<UserAccount> =>
  unwrapUser(await unwrapData(await request.get('/api/v1/auth/me', {
    signal: options?.signal,
    timeout: SESSION_QUERY_TIMEOUT_MS,
    timeoutErrorMessage: '会话恢复超时，请检查网络后重新登录或刷新重试',
  })));

export const logout = async (context?: AuthRequestContext): Promise<void> => {
  try {
    await unwrapData(await request.post('/api/v1/auth/logout', undefined, { signal: context?.signal }));
  } finally {
    if (context?.isCurrent() ?? true) setCsrfToken(null);
  }
};

export interface UserListParams {
  page?: number;
  page_size?: number;
  keyword?: string;
  role?: UserRole;
  status?: 'ENABLED' | 'DISABLED';
  scenario_id?: number;
}

export const getUserList = async (params?: UserListParams): Promise<UserListResult> => {
  const data = await unwrapData<{
    items?: ApiUser[];
    total?: number;
    page?: number;
    page_size?: number;
  }>(
    await request.get('/api/v1/users', {
      timeout: USER_LIST_QUERY_TIMEOUT_MS,
      timeoutErrorMessage: '用户列表加载超时，请稍后重试',
      params: {
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 200,
        keyword: params?.keyword,
        role: params?.role,
        status: params?.status,
        scenario_id: params?.scenario_id,
      },
    }),
  );
  return {
    items: (data.items ?? []).map((user: ApiUser) => toUserAccount(user)),
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 200,
  };
};

export const createUser = async (params: {
  username: string;
  password: string;
  role: UserRole;
  scenario_id?: number | null;
}): Promise<UserAccount> =>
  unwrapUser(await unwrapData(await request.post('/api/v1/users', params)));

export const updateUserScenario = async (
  userId: string | number,
  scenarioId: number,
): Promise<UserAccount> =>
  unwrapUser(
    await unwrapData(
      await request.put(`/api/v1/users/${userId}/scenario`, {
        scenario_id: scenarioId,
      }),
    ),
  );

export const changePassword = async (
  userId: string | number,
  params: { old_password: string; new_password: string },
): Promise<void> => {
  await unwrapData(await request.put(`/api/v1/users/${userId}/password`, params));
};

export const resetPassword = async (
  userId: string | number,
  newPassword: string,
): Promise<void> => {
  await unwrapData(
    await request.put(`/api/v1/users/${userId}/reset-password`, {
      new_password: newPassword,
    }),
  );
};

export const setUserStatus = async (
  userId: string | number,
  status: 'active' | 'disabled',
): Promise<void> => {
  await unwrapData(
    await request.put(`/api/v1/users/${userId}/status`, {
      status: status === 'active' ? 'ENABLED' : 'DISABLED',
    }),
  );
};
