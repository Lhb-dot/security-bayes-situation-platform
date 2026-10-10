// @vitest-environment jsdom
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '@/api/userApi';
import { useUserStore } from './userStore';
import { getCsrfToken, RequestError, setCsrfToken } from '@/utils/request';
import { deferred, user } from '@/test/queryFixtures';
import type { UserAccount } from '@/types/security';

vi.mock('@/api/userApi');
let pinia: ReturnType<typeof createPinia>;
let store: ReturnType<typeof useUserStore>;
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
beforeEach(() => {
  vi.resetAllMocks();
  window.sessionStorage.clear();
  pinia = createPinia();
  setActivePinia(pinia);
  store = useUserStore();
  vi.mocked(api.getMe).mockResolvedValue(user());
  vi.mocked(api.login).mockResolvedValue(user('new'));
  vi.mocked(api.logout).mockResolvedValue();
  vi.mocked(api.getUserList).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
});
afterEach(() => { store.expireSession(); disposePinia(pinia); });

describe('session restoration lifecycle', () => {
  it('shares concurrent bootstrap work and skips a completed initialization', async () => {
    const wait = deferred<UserAccount>();
    vi.mocked(api.getMe).mockReturnValueOnce(wait.promise);
    const first = store.bootstrap();
    const second = store.bootstrap();
    await flush();
    expect(api.getMe).toHaveBeenCalledOnce();
    expect(store.restoringSession).toBe(true);
    expect(store.initialized).toBe(false);
    wait.resolve(user());
    await Promise.all([first, second]);
    await store.bootstrap();
    expect(store.currentUser?.user_id).toBe('a');
    expect(store.initialized).toBe(true);
    expect(store.loading).toBe(false);
    expect(api.getMe).toHaveBeenCalledOnce();
  });

  it.each(['success', 'failure'])('ignores delayed restoration %s during a newer login', async (outcome) => {
    const old = deferred<UserAccount>();
    const fresh = deferred<UserAccount>();
    vi.mocked(api.getMe).mockReturnValueOnce(old.promise);
    vi.mocked(api.login).mockReturnValueOnce(fresh.promise);
    const restore = store.bootstrap();
    await flush();
    const signal = vi.mocked(api.getMe).mock.calls[0][0]?.signal;
    const login = store.login('new', 'password');
    await flush();
    expect(signal?.aborted).toBe(true);
    if (outcome === 'success') old.resolve(user('old'));
    else old.reject(new Error('old offline'));
    await restore;
    expect(store.currentUser).toBeNull();
    expect(store.authenticating).toBe(true);
    expect(store.bootstrapError).toBe('');
    fresh.resolve(user('new'));
    await login;
    expect(store.currentUser?.user_id).toBe('new');
    expect(store.loading).toBe(false);
  });

  it('cannot overwrite a completed new login with a previous getMe', async () => {
    const old = deferred<UserAccount>();
    vi.mocked(api.getMe).mockReturnValueOnce(old.promise);
    const restore = store.bootstrap();
    await flush();
    await store.login('new', 'password');
    old.resolve(user('old'));
    await restore;
    expect(store.currentUser?.user_id).toBe('new');
    expect(store.bootstrapError).toBe('');
  });

  it('ignores restoration after logout starts, including before logout completes', async () => {
    const old = deferred<UserAccount>();
    const exiting = deferred<void>();
    vi.mocked(api.getMe).mockReturnValueOnce(old.promise);
    vi.mocked(api.logout).mockReturnValueOnce(exiting.promise);
    const restore = store.bootstrap();
    await flush();
    const logout = store.logout();
    await flush();
    old.resolve(user());
    await restore;
    expect(store.currentUser).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.authenticating).toBe(true);
    exiting.resolve();
    await logout;
    expect(store.loading).toBe(false);
  });

  it('does not duplicate restoration while login is pending', async () => {
    const wait = deferred<UserAccount>();
    vi.mocked(api.login).mockReturnValueOnce(wait.promise);
    const login = store.login('new', 'password');
    const restore = store.bootstrap();
    await flush();
    expect(api.getMe).not.toHaveBeenCalled();
    wait.resolve(user('new'));
    await Promise.all([login, restore]);
    expect(store.currentUser?.user_id).toBe('new');
  });

  it.each([
    [new RequestError('expired', { status: 401 }), ''],
    [new RequestError('slow', { code: 'ECONNABORTED' }), '会话恢复超时'],
    [new RequestError('offline', { code: 'ERR_NETWORK' }), '暂时无法恢复会话'],
    [new RequestError('unavailable', { status: 503 }), '暂时无法恢复会话'],
  ])('finishes initialization after %s and distinguishes the recovery message', async (error, message) => {
    vi.mocked(api.getMe).mockRejectedValueOnce(error);
    await store.bootstrap();
    expect(store.currentUser).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.loading).toBe(false);
    if (message) expect(store.bootstrapError).toContain(message);
    else expect(store.bootstrapError).toBe('');
  });

  it('allows a shared read-only retry after a transient bootstrap failure', async () => {
    vi.mocked(api.getMe).mockRejectedValueOnce(new RequestError('offline', { code: 'ERR_NETWORK' }));
    await store.bootstrap();
    expect(store.bootstrapError).not.toBe('');
    await Promise.all([store.bootstrap(), store.bootstrap()]);
    expect(api.getMe).toHaveBeenCalledTimes(2);
    expect(store.currentUser?.user_id).toBe('a');
    expect(store.bootstrapError).toBe('');
  });

  it('keeps restoration requests independent between Pinia instances', async () => {
    const wait = deferred<UserAccount>();
    vi.mocked(api.getMe).mockReturnValueOnce(wait.promise).mockResolvedValueOnce(user('b'));
    const first = store.bootstrap();
    await flush();
    const otherPinia = createPinia();
    const other = useUserStore(otherPinia);
    await other.bootstrap();
    wait.resolve(user('a'));
    await first;
    expect(store.currentUser?.user_id).toBe('a');
    expect(other.currentUser?.user_id).toBe('b');
    disposePinia(otherPinia);
  });
});

describe('authentication and user list isolation', () => {
  it('discards an obsolete login and does not unlock a newer login', async () => {
    const old = deferred<UserAccount>();
    const fresh = deferred<UserAccount>();
    vi.mocked(api.login).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const first = store.login('old', 'password');
    const rejected = expect(first).rejects.toMatchObject({ kind: 'canceled' });
    await flush();
    const second = store.login('new', 'password');
    await flush();
    old.resolve(user('old'));
    await rejected;
    expect(store.authenticating).toBe(true);
    fresh.resolve(user('new'));
    await second;
    expect(store.currentUser?.user_id).toBe('new');
  });

  it('keeps the original login error and does not automatically retry', async () => {
    vi.mocked(api.login).mockRejectedValueOnce(new RequestError('密码错误', { status: 401 }));
    await expect(store.login('new', 'bad')).rejects.toThrow('密码错误');
    expect(api.login).toHaveBeenCalledOnce();
    expect(store.loading).toBe(false);
    expect(store.currentUser).toBeNull();
  });

  it('shares repeated logout and retains CSRF until its POST is sent', async () => {
    const wait = deferred<void>();
    vi.mocked(api.logout).mockReturnValueOnce(wait.promise);
    store.currentUser = user();
    setCsrfToken('existing-csrf');
    const first = store.logout();
    const second = store.logout();
    await flush();
    expect(api.logout).toHaveBeenCalledOnce();
    expect(getCsrfToken()).toBe('existing-csrf');
    expect(store.currentUser).toBeNull();
    wait.resolve();
    await Promise.all([first, second]);
    expect(store.loading).toBe(false);
  });

  it.each(['success', 'failure'])('discards old logout %s after a new login', async (outcome) => {
    const old = deferred<void>();
    vi.mocked(api.logout).mockReturnValueOnce(old.promise);
    const exiting = store.logout();
    await flush();
    await store.login('new', 'password');
    if (outcome === 'success') old.resolve();
    else old.reject(new Error('old logout failure'));
    await exiting;
    expect(store.currentUser?.user_id).toBe('new');
    expect(store.loading).toBe(false);
  });

  it('only writes the latest user page and keeps restoration loading independent', async () => {
    store.currentUser = user();
    const restoring = deferred<UserAccount>();
    const old = deferred<api.UserListResult>();
    const fresh = deferred<api.UserListResult>();
    vi.mocked(api.getMe).mockReturnValueOnce(restoring.promise);
    vi.mocked(api.getUserList).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const restore = store.bootstrap();
    const first = store.fetchUsers({ page: 1 });
    const second = store.fetchUsers({ page: 2 });
    fresh.resolve({ items: [user('b')], total: 2, page: 2, page_size: 1 });
    await second;
    expect(store.loading).toBe(true);
    old.resolve({ items: [user('a')], total: 1, page: 1, page_size: 1 });
    await first;
    expect(store.users[0].user_id).toBe('b');
    restoring.resolve(user());
    await restore;
    expect(store.loading).toBe(false);
  });

  it('clears and discards an old user list after expiring the session', async () => {
    const wait = deferred<api.UserListResult>();
    store.currentUser = user();
    vi.mocked(api.getUserList).mockReturnValueOnce(wait.promise);
    const query = store.fetchUsers();
    store.expireSession();
    wait.resolve({ items: [user()], total: 1, page: 1, page_size: 10 });
    await query;
    expect(store.users).toEqual([]);
    expect(store.usersTotal).toBe(0);
    expect(store.loading).toBe(false);
  });

  it('does not query the user list without a current account', async () => {
    await store.fetchUsers();
    expect(api.getUserList).not.toHaveBeenCalled();
    expect(store.loading).toBe(false);
  });

  it('ignores an obsolete list failure while the next page is still pending', async () => {
    store.currentUser = user();
    const old = deferred<api.UserListResult>();
    const fresh = deferred<api.UserListResult>();
    vi.mocked(api.getUserList).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const first = store.fetchUsers({ page: 1 });
    const second = store.fetchUsers({ page: 2 });
    old.reject(new Error('obsolete'));
    await first;
    expect(store.loadingUsers).toBe(true);
    fresh.resolve({ items: [user('b')], total: 1, page: 2, page_size: 1 });
    await second;
    expect(store.users[0].user_id).toBe('b');
    expect(store.loadingUsers).toBe(false);
  });

  it('preserves a current user list failure and releases its loading state', async () => {
    store.currentUser = user();
    vi.mocked(api.getUserList).mockRejectedValueOnce(new RequestError('用户列表加载超时', { code: 'ECONNABORTED' }));
    await expect(store.fetchUsers()).rejects.toThrow('用户列表加载超时');
    expect(store.loadingUsers).toBe(false);
    expect(api.getUserList).toHaveBeenCalledOnce();
  });
});
