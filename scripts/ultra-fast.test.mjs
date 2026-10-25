import test from 'node:test';
import assert from 'node:assert/strict';
import { createFastControl } from '../plugins/dsh-ultra-effort/src/fast-control.mjs';
import { createTurnState, fastEnabled } from '../plugins/dsh-ultra-effort/lib/fast-state.js';
import { FAST_POLICY } from '../plugins/dsh-ultra-effort/lib/fast-policy.js';

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const settle = () => new Promise(resolve => setTimeout(resolve, 10));
function backend() {
  let revision = 0, values = {}, writable = true, idle = true;
  const calls = [];
  const row = () => ({ ns: 'ui-ultra-effort', revision, applies: 'live', value: { fastSessions: { ...values } } });
  const api = {
    describe: async () => ({ ok: true, value: { writable, namespaces: [row()] } }),
    mutate: async (ns, ops, expected) => {
      calls.push({ ns, ops, expected });
      if (expected !== revision) return { ok: false, error: { code: 'settings/conflict' } };
      for (const op of ops) values[op.path[1]] = op.value;
      revision++;
      return { ok: true, value: row() };
    },
  };
  return { api, calls, row, change(value) { values = value; revision++; }, writable(value) { writable = value; }, idle(value) { idle = value; },
    control(sessionId, options = {}) { return createFastControl({ sessionId, settings: () => api, fetchCapability: async () => ({ protocol: 1,
      namespace: 'ui-ultra-effort', ready: true, writable, idle, boundary: 'next-turn' }), ...options }); } };
}

test('fast preference defaults off; turns freeze choices, isolate main/subagent, and clean up', () => {
  const config = { fastSessions: { A: true, child: true } }, turns = createTurnState(() => config.fastSessions);
  const a = { id: 'A', header: {} }, b = { id: 'B', header: {} }, child = { id: 'child', header: { origin: 'subagent' } };
  assert.equal(fastEnabled(config.fastSessions, '__proto__'), false);
  turns.start(a, 1); turns.start(b, 1); turns.start(child, 1);
  config.fastSessions.A = false;
  assert.equal(turns.get(a).enabled, true); assert.equal(turns.get(b).enabled, false); assert.equal(turns.get(child), undefined);
  turns.end(a, 2); assert(turns.get(a)); turns.end(a, 1); assert.equal(turns.get(a), undefined);
  turns.start(a, 2); assert.equal(turns.get(a).enabled, false);
  assert.equal(turns.get({ ...a }), undefined); turns.forget(a); turns.clear(); assert.equal(turns.get(b), undefined);
  assert.match(FAST_POLICY, /acceptance criteria/); assert.match(FAST_POLICY, /read-before-write/);
});

test('client waits for confirmed write, writes only this session at its revision, and keeps new chats off', async () => {
  const b = backend(), a = b.control('A'), other = b.control('B');
  await a.refresh(); await other.refresh();
  const wait = deferred(), mutate = b.api.mutate;
  b.api.mutate = (...args) => wait.promise.then(() => mutate(...args));
  const write = a.toggle(); await settle();
  assert.equal(a.getSnapshot().enabled, false); assert.equal(a.getSnapshot().phase, 'saving');
  await a.toggle(); assert.equal(b.calls.length, 0);
  wait.resolve(); await write;
  assert.equal(a.getSnapshot().enabled, true); assert.equal(other.getSnapshot().enabled, false);
  assert.deepEqual(b.calls, [{ ns: 'ui-ultra-effort', ops: [{ op: 'set', path: ['fastSessions', 'A'], value: true }], expected: 0 }]);
  await a.toggle(); assert.equal(a.getSnapshot().enabled, false); assert.equal(b.calls[1].ops[0].value, false);
  a.dispose(); other.dispose();
});

test('stale window rereads on conflict without overwriting another session', async () => {
  const b = backend(), a = b.control('A'), other = b.control('B');
  await a.refresh(); await other.refresh(); await other.toggle(); await a.toggle();
  assert.equal(a.getSnapshot().reason, 'conflict'); assert.equal(a.getSnapshot().enabled, false);
  assert.equal(b.row().value.fastSessions.B, true); assert.equal(b.calls.length, 2);
  await a.toggle(); assert.deepEqual(b.row().value.fastSessions, { A: true, B: true });
  a.dispose(); other.dispose();
});

test('unknown timeout blocks resubmission until the original write settles, then rereads its late commit', async () => {
  const b = backend(), a = b.control('A', { timeoutMs: 20 }), write = deferred();
  const mutate = b.api.mutate; b.api.mutate = (...args) => write.promise.then(() => mutate(...args));
  await a.refresh(); await a.toggle();
  assert.equal(a.getSnapshot().phase, 'unknown'); assert.equal(a.getSnapshot().enabled, false);
  await a.toggle(); assert.equal(b.calls.length, 0);
  write.resolve(); await settle();
  assert.equal(a.getSnapshot().phase, 'ready'); assert.equal(a.getSnapshot().enabled, true); assert.equal(b.calls.length, 1);
  a.dispose();
});

test('lost acknowledgement rereads persisted state; definite refusal keeps the confirmed value and allows retry', async () => {
  const b = backend(), a = b.control('A'); await a.refresh();
  const mutate = b.api.mutate;
  b.api.mutate = async (...args) => { await mutate(...args); throw new Error('transport disconnected'); };
  await a.toggle(); assert.equal(a.getSnapshot().enabled, true);
  b.api.mutate = async () => ({ ok: false, error: { code: 'settings/rejected' } });
  await a.toggle(); assert.equal(a.getSnapshot().enabled, true); assert.equal(a.getSnapshot().reason, 'rejected');
  b.api.mutate = mutate; await a.toggle(); assert.equal(a.getSnapshot().enabled, false);
  a.dispose();
});

test('read-only, running and locked controls refuse writes; missing or mismatched backends are observable', async () => {
  const b = backend(), a = b.control('A');
  b.writable(false); await a.refresh(); await a.toggle(); assert.equal(a.getSnapshot().reason, 'readonly');
  b.writable(true); b.idle(false); await a.refresh(); await a.toggle(); assert.equal(a.getSnapshot().reason, 'running');
  b.idle(true); await a.refresh(); await a.toggle(true); assert.equal(b.calls.length, 0);
  const missing = b.control('A', { fetchCapability: async () => { throw new Error('404'); } });
  await missing.refresh(); assert.equal(missing.getSnapshot().phase, 'unavailable');
  const mismatch = b.control('A', { fetchCapability: async () => ({ protocol: 2 }) });
  await mismatch.refresh(); assert.equal(mismatch.getSnapshot().reason, 'protocol');
  b.api.describe = async () => ({ namespaces: [b.row()] });
  await a.refresh(); assert.equal(a.getSnapshot().reason, 'protocol');
  for (const c of [a, missing, mismatch]) c.dispose();
});

test('disposed A cannot repaint B when A write resolves late; reconnect refreshes authoritative state', async () => {
  const b = backend(), a = b.control('A'), other = b.control('B'), gate = deferred(), mutate = b.api.mutate;
  await a.refresh(); await other.refresh(); b.api.mutate = (...args) => gate.promise.then(() => mutate(...args));
  const write = a.toggle(); await settle(); a.dispose(); gate.resolve(); await write;
  assert.equal(other.getSnapshot().enabled, false); b.change({ B: true }); await other.refresh();
  assert.equal(other.getSnapshot().enabled, true); other.dispose();
});
