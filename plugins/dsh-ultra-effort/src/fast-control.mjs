/** One controller per chat, shared by mounted seats. Only confirmed Host values are displayed. */
export function createFastControl({ sessionId, settings, fetchCapability, timeoutMs = 8000 }) {
  let state = { enabled: false, phase: 'loading', reason: 'loading', writable: false, idle: false };
  let descriptor, capability, epoch = 0, disposed = false, pending;
  const listeners = new Set();
  const publish = patch => {
    if (disposed) return;
    state = { ...state, ...patch };
    for (const listener of listeners) listener();
  };
  const failure = code => Object.assign(new Error(code), { code });
  const bounded = promise => {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(failure('timeout')), timeoutMs);
    })]).finally(() => clearTimeout(timer));
  };
  const unwrap = result => {
    if (result?.ok === true) return result.value;
    if (result?.ok === false) throw failure(result.error?.code ?? 'protocol');
    throw failure('protocol');
  };
  const accept = row => {
    if (row?.ns !== capability.namespace || !Number.isSafeInteger(row.revision) || row.applies !== 'live'
      || !row.value?.fastSessions || typeof row.value.fastSessions !== 'object' || Array.isArray(row.value.fastSessions)) throw failure('protocol');
    const value = Object.hasOwn(row.value.fastSessions, sessionId) ? row.value.fastSessions[sessionId] : false;
    if (typeof value !== 'boolean') throw failure('protocol');
    descriptor = { ns: row.ns, revision: row.revision };
    return value;
  };
  async function refresh(notice) {
    if (disposed || (pending && !pending.unknown)) return;
    const run = ++epoch;
    publish({ phase: pending ? 'unknown' : 'loading', reason: pending ? 'unknown' : 'loading' });
    try {
      const cap = await bounded(Promise.resolve().then(fetchCapability));
      if (disposed || run !== epoch) return;
      if (cap?.protocol !== 1 || cap.ready !== true || typeof cap.namespace !== 'string'
        || !cap.namespace || cap.boundary !== 'next-turn' || typeof cap.writable !== 'boolean' || typeof cap.idle !== 'boolean') throw failure('protocol');
      capability = cap;
      const view = unwrap(await bounded(Promise.resolve().then(() => settings().describe())));
      if (disposed || run !== epoch) return;
      if (typeof view?.writable !== 'boolean' || !Array.isArray(view.namespaces)) throw failure('protocol');
      const enabled = accept(view.namespaces.find(row => row.ns === cap.namespace));
      const writable = cap.writable && view.writable;
      const unknown = pending && !pending.settled;
      publish({ enabled, writable, idle: cap.idle, phase: unknown ? 'unknown' : 'ready',
        reason: unknown ? 'unknown' : !writable ? 'readonly' : !cap.idle ? 'running' : notice ?? (enabled ? 'on' : 'off') });
    } catch (error) {
      if (disposed || run !== epoch) return;
      publish({ phase: pending && !pending.settled ? 'unknown' : 'unavailable', writable: false,
        reason: pending && !pending.settled ? 'unknown' : error.code === 'protocol' ? 'protocol' : 'unavailable' });
    }
  }
  async function toggle(locked = false) {
    if (disposed || pending || locked || state.phase !== 'ready' || !state.writable || !state.idle) return;
    const run = ++epoch;
    const attempt = { settled: false, unknown: false };
    pending = attempt;
    const value = !state.enabled;
    publish({ phase: 'saving', reason: 'saving' });
    const request = Promise.resolve().then(() => settings().mutate(descriptor.ns,
      [{ op: 'set', path: ['fastSessions', sessionId], value }], descriptor.revision));
    const settled = () => {
      attempt.settled = true;
      if (attempt.unknown && !disposed) { pending = undefined; void refresh(); }
    };
    request.then(settled, settled);
    try {
      const row = unwrap(await bounded(request));
      if (disposed || run !== epoch) return;
      const enabled = accept(row);
      publish({ enabled, phase: 'ready', reason: enabled ? 'on' : 'off' });
    } catch (error) {
      if (disposed || run !== epoch) return;
      if (error.code === 'settings/rejected' || error.code === 'gateway/bad-request') {
        publish({ phase: 'ready', reason: 'rejected' });
      } else {
        attempt.unknown = true;
        if (attempt.settled) pending = undefined;
        publish({ phase: 'unknown', reason: 'unknown' });
        await refresh(error.code === 'settings/conflict' ? 'conflict' : undefined);
      }
    } finally {
      if (attempt.settled && pending === attempt) pending = undefined;
    }
  }
  return {
    getSnapshot: () => state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    refresh, toggle,
    dispose() { disposed = true; epoch++; listeners.clear(); },
  };
}
