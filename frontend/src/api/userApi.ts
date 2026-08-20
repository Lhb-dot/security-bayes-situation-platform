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

export const login = async (username: string, password: string): Promise<UserAccount> => {
  const payload = await unwrapData(
    await request.post('/api/v1/auth/login', { username, password }),
  ) as AuthPayload;
  setCsrfToken(payload.csrf_token ?? null);
  return unwrapUser(payload);
};

export const getMe = async (): Promise<UserAccount> =>
  unwrapUser(await unwrapData(await request.get('/api/v1/auth/me')));

export const logout = async (): Promise<void> => {
  try {
    await unwrapData(await request.post('/api/v1/auth/logout'));
  } finally {
    setCsrfToken(null);
  }
};

export const getUserList = async (params?: {
  page?: number;
  page_size?: number;
  keyword?: string;
  role?: UserRole;
}): Promise<UserListResult> => {
  const data = await unwrapData(
    await request.get('/api/v1/users', {
      params: {
        page: params?.page ?? 1,
        page_size: params?.page_size ?? 200,
        keyword: params?.keyword,
        role: params?.role,
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
