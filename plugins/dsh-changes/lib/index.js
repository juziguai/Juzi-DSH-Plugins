import { TurnRecord, configOf } from './recorder.js';
import { capabilityGit } from './git.js';
import { BlobStore } from './blob-store.js';

export const name = 'juzi-changes';
export const inject = ['subprocess', 'fs', 'connection'];
const eligible = session => session.header.cwd && session.header.origin !== 'subagent' && !(session.header.delegationDepth > 0);

/** Host runtime owns all records. Routes only accept Session/turn/file coordinates, never paths. */
export function apply(ctx, value) {
  const config = configOf(value);
  const lifetime = new AbortController();
  const git = capabilityGit(ctx.subprocess, lifetime.signal, config.timeoutMs);
  const budget = { used: 0, limit: config.maxStoredBytes };
  const store = new BlobStore(budget);
  const sessions = new Map(), actors = new WeakMap(), tasks = new Set();
  const warn = error => { if (!lifetime.signal.aborted) ctx.logger.warn(`changes: ${error.message}`); };
  const track = promise => {
    tasks.add(promise);
    promise.catch(warn).finally(() => tasks.delete(promise));
    return promise;
  };
  const enqueue = (state, task) => {
    state.pending = state.pending.then(task).catch(warn);
    return track(state.pending);
  };
  const start = (session, turn) => {
    if (!eligible(session) || !Number.isSafeInteger(turn) || turn < 1) return;
    let state = sessions.get(session.id);
    if (!state) { state = { turns: new Map(), pending: Promise.resolve(), disposed: false }; sessions.set(session.id, state); }
    const cwd = session.header.cwd;
    enqueue(state, async () => {
      if (state.disposed) return;
      state.released = false;
      if (state.current && !['finished', 'interrupted', 'error'].includes(state.current.status)) await state.current.finish('interrupted');
      const record = new TurnRecord({ sessionId: session.id, turn, cwd, git, config, budget, store, signal: lifetime.signal, onError: warn });
      state.current = record; state.turns.set(turn, record);
      await record.ready;
      while (state.turns.size > config.maxTurns) {
        const [oldTurn, previous] = state.turns.entries().next().value;
        state.turns.delete(oldTurn); await previous.dispose();
      }
    });
  };
  const forget = async id => {
    const state = sessions.get(id);
    if (!state) return;
    state.disposed = true; sessions.delete(id);
    await state.pending;
    await Promise.all([...state.turns.values()].map(record => record.dispose()));
  };
  ctx.on('session/event', (session, event) => {
    if (event.type === 'turn/start') start(session, event.data.turn);
    const state = sessions.get(session.id);
    if (!state) return;
    if (event.type === 'tool/result') enqueue(state, () => state.turns.get(event.data.turn)?.markDirty());
    if (event.type === 'turn/end') enqueue(state, () => state.turns.get(event.data.turn)?.finish());
    if (event.type === 'workspace/changes') enqueue(state, () => {
      const record = state.turns.get(event.data.turn);
      if (record && !state.released) record.officialSeq = event.seq;
    });
  });
  ctx.on('tools/pre-execute', async (exec, next) => {
    const state = sessions.get(exec.agent?.session.id);
    if (state) { await state.pending; if (state.current) actors.set(exec, state.current); }
    return next();
  });
  const capture = async (target, actor, next) => {
    const intent = await next();
    const record = actor && actors.get(actor);
    if (record) { try { await record.capture(ctx.fs.processPath(target)); } catch (error) { record.fail(error); } }
    return intent;
  };
  ctx.on('fs/write-intent', capture, { prepend: true });
  ctx.on('fs/edit-intent', capture, { prepend: true });
  ctx.on('session/disposed', session => {
    const state = sessions.get(session.id);
    if (state) enqueue(state, async () => {
      state.released = true;
      for (const record of state.turns.values()) record.officialSeq = undefined;
      if (state.current && !['finished', 'interrupted', 'error'].includes(state.current.status)) await state.current.finish('interrupted');
    });
  });

  const json = (data, status = 200) => Response.json(data, { status, headers: { 'cache-control': 'no-store' } });
  async function route(request, action) {
    const query = new URL(request.url).searchParams;
    const id = query.get('sessionId');
    if (!id || id.length > 200) return json({ error: '无效会话' }, 400);
    const state = sessions.get(id);
    if (!state) return action === 'list' ? json({ turns: [], maxTurns: config.maxTurns }) : json({ error: '本次运行没有该轮次记录' }, 404);
    await state.pending;
    if (state.disposed || lifetime.signal.aborted) return json({ error: '记录已释放' }, 404);
    request.signal.throwIfAborted();
    if (action === 'list') return json({ turns: [...state.turns.values()].reverse().map(record => ({ turn: record.turn, status: record.status,
      added: record.added, deleted: record.deleted, total: record.total, officialSeq: record.officialSeq ?? null })), maxTurns: config.maxTurns });
    const turn = Number(query.get('turn'));
    if (!Number.isSafeInteger(turn) || turn < 1) return json({ error: '无效轮次' }, 400);
    const record = state.turns.get(turn);
    if (!record) return json({ error: '该轮次未记录或已超过保留上限' }, 404);
    if (action === 'turn') {
      if (query.get('refresh') === '1') record.markDirty();
      return json({ ...await record.refresh(), officialSeq: record.officialSeq ?? null });
    }
    const revision = Number(query.get('revision')), file = query.get('file');
    if (!file || !Number.isSafeInteger(revision) || revision < 0) return json({ error: '无效文件坐标' }, 400);
    const diff = await record.diff(file, revision);
    if (diff?.kind === 'stale') return json({ error: '文件列表已更新，请重新选择文件' }, 409);
    return diff ? json(diff) : json({ error: '文件不在该轮次的快照中' }, 404);
  }
  for (const action of ['list', 'turn', 'diff']) ctx.connection.fetch.register({
    path: `/api/juzi.changes.${action}`, methods: ['GET'], requestBody: 'buffered',
    fetch: request => {
      const work = route(request, action).catch(error => {
        if (!request.signal.aborted) warn(error);
        return json({ error: '读取变更失败，可刷新重试' }, request.signal.aborted ? 499 : 500);
      });
      return track(work);
    },
  });
  ctx.effect(() => async () => {
    lifetime.abort();
    await Promise.all([...sessions.keys()].map(forget));
    await Promise.allSettled(tasks);
    await store.dispose();
  });
}
