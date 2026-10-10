// @vitest-environment jsdom
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  downloadReportExportFile, getReportExportJob, getReportGenerateJob,
  listReportExportJobs, listReportGenerateJobs,
} from '@/api/reportApi';
import type { ReportExportJob, ReportGenerateJob } from '@/api/reportApi';
import type { Report } from '@/types/security';
import { ElNotification } from 'element-plus';
import { useReportJobStore } from './reportJobStore';

const account = vi.hoisted(() => ({ id: 'a' as string | null }));
vi.mock('./jobHelpers', () => ({ currentUid: () => account.id }));
vi.mock('@/utils/jobSeen', () => ({ readSeenIds: () => new Set(), markSeenIds: () => new Set() }));
vi.mock('element-plus', () => ({ ElNotification: vi.fn() }));
vi.mock('@/api/reportApi', () => ({
  EXPORT_EXT: { markdown: 'md', html: 'html', pdf: 'pdf' },
  downloadReportExportFile: vi.fn(), getReportExportJob: vi.fn(), getReportGenerateJob: vi.fn(),
  listReportExportJobs: vi.fn(), listReportGenerateJobs: vi.fn(),
}));
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};
const generate = vi.mocked(getReportGenerateJob);
const exported = vi.mocked(getReportExportJob);
const download = vi.mocked(downloadReportExportFile);
const generates = vi.mocked(listReportGenerateJobs);
const exports = vi.mocked(listReportExportJobs);
const generateView = (status: ReportGenerateJob['status'] = 'RUNNING'): ReportGenerateJob => ({
  job_id: 'generate', title: '报告', status, report_id: status === 'DONE' ? '5' : null,
  error: null, ready: status === 'DONE', created_at: Date.now() / 1000,
});
const exportView = (status: ReportExportJob['status'] = 'RUNNING'): ReportExportJob => ({
  job_id: 'export', report_id: 5, format: 'pdf', status, filename: 'file.pdf',
  error: null, ready: status === 'DONE', created_at: Date.now() / 1000,
});
const report: Report = {
  report_id: '5', title: 'a/b', scenario_id: 'network_security',
  scenario_name: '网络安全态势', format: 'pdf', generated_by: 'a', created_at: '', status: 'completed',
};
let store: ReturnType<typeof useReportJobStore>;
let click: ReturnType<typeof vi.spyOn>;
const createUrl = vi.fn(() => 'blob:test');
const revokeUrl = vi.fn();
beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  account.id = 'a';
  setActivePinia(createPinia());
  store = useReportJobStore();
  generate.mockResolvedValue(generateView());
  exported.mockResolvedValue(exportView());
  generates.mockResolvedValue([]);
  exports.mockResolvedValue([]);
  download.mockResolvedValue(new Blob(['report']));
  createUrl.mockReturnValue('blob:test');
  vi.stubGlobal('URL', { createObjectURL: createUrl, revokeObjectURL: revokeUrl });
  click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => { store.reset(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('report polling integration', () => {
  it('keeps generation completion, refresh counter and notification exactly once', async () => {
    generate.mockResolvedValue(generateView('DONE'));
    store.trackGenerate('generate', '报告');
    await store._tick();
    await vi.advanceTimersByTimeAsync(3000);
    expect(store.finishedJobs[0]?.reportId).toBe('5');
    expect(store.completedTick).toBe(1);
    expect(ElNotification).toHaveBeenCalledTimes(1);
    expect(generate).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('downloads once after automatic idle stop, preserving filename and Blob cleanup', async () => {
    const file = deferred<Blob>();
    exported.mockResolvedValue(exportView('DONE'));
    download.mockReturnValue(file.promise);
    store.trackExport('export', report);
    await store._tick();
    expect(vi.getTimerCount()).toBe(0);
    expect(click).not.toHaveBeenCalled();
    const blob = new Blob(['pdf']);
    file.resolve(blob);
    await vi.advanceTimersByTimeAsync(0);
    expect(download).toHaveBeenCalledTimes(1);
    expect(createUrl).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledTimes(1);
    const anchor = click.mock.instances[0] as HTMLAnchorElement;
    expect(anchor.download).toBe('a_b.pdf');
    expect(revokeUrl).toHaveBeenCalledWith('blob:test');
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ title: '报告已下载' }));
    expect(store.completedTick).toBe(0);
    await vi.advanceTimersByTimeAsync(3000);
    expect(download).toHaveBeenCalledTimes(1);
  });

  it.each(['generate', 'export'])('does not notify or download an old %s response after reset', async (kind) => {
    const oldGenerate = deferred<ReportGenerateJob>();
    const oldExport = deferred<ReportExportJob>();
    const fresh = deferred<ReportGenerateJob>();
    if (kind === 'generate') {
      generate.mockReturnValueOnce(oldGenerate.promise).mockReturnValue(fresh.promise);
      store.trackGenerate('old', '旧报告');
    } else {
      exported.mockReturnValue(oldExport.promise);
      generate.mockReturnValue(fresh.promise);
      store.trackExport('old', report);
    }
    await vi.advanceTimersByTimeAsync(0);
    const tick = store._tick();
    account.id = 'b';
    store.reset();
    store.trackGenerate('new', '新报告');
    await vi.advanceTimersByTimeAsync(0);
    if (kind === 'generate') oldGenerate.resolve(generateView('DONE'));
    else oldExport.resolve(exportView('DONE'));
    await tick;
    await vi.advanceTimersByTimeAsync(2000);
    expect(ElNotification).not.toHaveBeenCalled();
    expect(download).not.toHaveBeenCalled();
    expect(store.jobs.map((job) => job.jobId)).toEqual(['new']);
    expect(generate).toHaveBeenCalledTimes(kind === 'generate' ? 2 : 1);
    fresh.resolve(generateView('DONE'));
    await store._tick();
    expect(store.completedTick).toBe(1);
  });

  it.each(['logout-success', 'logout-failure', 'reset-success'])('suppresses a late file outcome (%s)', async (outcome) => {
    const file = deferred<Blob>();
    exported.mockResolvedValue(exportView('DONE'));
    download.mockReturnValue(file.promise);
    store.trackExport('export', report);
    await store._tick();
    if (outcome.startsWith('logout')) account.id = null;
    else store.reset();
    if (outcome.endsWith('failure')) file.reject(new Error('old download failure'));
    else file.resolve(new Blob(['pdf']));
    await vi.advanceTimersByTimeAsync(0);
    expect(click).not.toHaveBeenCalled();
    expect(createUrl).not.toHaveBeenCalled();
    expect(ElNotification).not.toHaveBeenCalled();
  });

  it('keeps download errors visible for the current session', async () => {
    exported.mockResolvedValue(exportView('DONE'));
    download.mockRejectedValue(new Error('download failed'));
    store.trackExport('export', report);
    await store._tick();
    await vi.advanceTimersByTimeAsync(0);
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ title: '报告下载失败', duration: 0 }));
  });

  it('ignores both old restoration lists when a newer restoration completes first', async () => {
    const oldGenerates = deferred<ReportGenerateJob[]>();
    const oldExports = deferred<ReportExportJob[]>();
    generates.mockReturnValueOnce(oldGenerates.promise).mockResolvedValueOnce([generateView('DONE')]);
    exports.mockReturnValueOnce(oldExports.promise).mockResolvedValueOnce([exportView('DONE')]);
    const old = store.resumePending();
    await store.resumePending();
    oldGenerates.resolve([{ ...generateView(), job_id: 'old-generate' }]);
    oldExports.resolve([{ ...exportView(), job_id: 'old-export' }]);
    await old;
    await store._tick();
    expect(store.jobs.map((job) => job.jobId)).toEqual(['generate', 'export']);
    expect(download).not.toHaveBeenCalled();
    expect(ElNotification).not.toHaveBeenCalled();
  });

  it('recovers from a query failure and retains the 20 minute warning timeout', async () => {
    generate.mockRejectedValueOnce(new Error('offline'));
    store.trackGenerate('generate', '报告');
    await store._tick();
    expect(store.runningJobs[0]?.error).toBe('offline');
    expect(ElNotification).not.toHaveBeenCalled();
    generate.mockResolvedValue({ ...generateView('FAILED'), error: 'bad data' });
    await vi.advanceTimersByTimeAsync(1000);
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'error', duration: 0 }));
    store.reset();
    vi.mocked(ElNotification).mockClear();
    generate.mockClear();
    store._track({
      jobId: 'timeout', kind: 'generate', title: '报告', status: 'RUNNING', error: null,
      reportId: null, filename: null, startedAt: Date.now() - 20 * 60 * 1000,
    });
    await store._tick();
    expect(store.jobs).toEqual([]);
    expect(generate).not.toHaveBeenCalled();
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'warning' }));
  });
});
