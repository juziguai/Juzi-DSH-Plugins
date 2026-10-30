import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import vm from 'node:vm';

const anchor = process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; };

async function browser(t) {
  const require = createRequire(pathToFileURL(resolve(anchor)));
  const R = require('react'), { JSDOM, VirtualConsole } = require('jsdom');
  const errors = [], vc = new VirtualConsole();
  vc.on('jsdomError', error => { if (error.type !== 'css parsing') errors.push(error); });
  const dom = new JSDOM('<html><head></head><body><main id="app"></main></body></html>', { pretendToBeVisual: true, virtualConsole: vc });
  const prior = { window: globalThis.window, document: globalThis.document, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const { createRoot } = require('react-dom/client');
  const effects = [], registered = new Map(), channels = new Map(), bindings = new Map(), fixtures = new Map(), timers = new Map(), calls = [];
  let module, now = 0, serial = 0;
  const observable = getSnapshot => {
    const listeners = new Set();
    return { getSnapshot, listeners, subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }, emit() { for (const fn of [...listeners]) fn(); } };
  };
  const catalog = { byId: {} }, list = observable(() => catalog);
  const session = id => {
    const f = { rows: [{ turn: 1, status: 'finished' }], revision: 1, officialSeq: null, change: { kind: 'replace', entries: [] } };
    const source = observable(() => ({ change: f.change, get entries() { throw Error('Do not scan complete history'); } }));
    fixtures.set(id, f); bindings.set(id, { eventSource: source }); catalog.byId[id] = { running: false };
    return { f, source };
  };
  const a = session('A'), b = session('B');
  const fetch = async (url, options) => {
    const u = new URL(url, 'http://fixture.invalid/'), action = u.pathname.split('.').at(-1), id = u.searchParams.get('sessionId');
    calls.push({ action, id, turn: u.searchParams.get('turn'), forced: u.searchParams.get('refresh') === '1', signal: options.signal });
    const f = fixtures.get(id);
    if (f.fail) { f.fail = false; return { ok: false, json: async () => ({ error: 'fixture read failed' }) }; }
    const turn = Number(u.searchParams.get('turn'));
    const data = action === 'list' ? { turns: f.rows.map(row => ({ ...row })), maxTurns: 30 } : {
      turn, status: f.rows.find(row => row.turn === turn)?.status, revision: f.revision, total: 1, added: 1, deleted: 1,
      officialSeq: f.officialSeq, files: [{ id: `f-${turn}`, path: `file-${turn}.txt`, display: `file-${turn}.txt`, status: 'modified', added: 1, deleted: 1 }],
    };
    if (action === 'turn' && f.block) { const gate = f.block; f.block = undefined; await gate.promise; }
    return { ok: true, json: async () => data };
  };
  dom.window.__ModuleLoader__ = { load: ({ factory }) => { module = factory(() => R); } };
  vm.runInNewContext(readFileSync(new URL('../plugins/dsh-changes/lib/client.js', import.meta.url), 'utf8'), {
    window: dom.window, document: dom.window.document, fetch, AbortController, URLSearchParams,
    setTimeout(fn, delay) { const id = ++serial; timers.set(id, { at: now + delay, fn }); return id; },
    clearTimeout(id) { timers.delete(id); },
  });
  module.apply({
    effect(fn) { const off = fn(); if (off) effects.push(off); },
    on(name, fn) { const set = channels.get(name) ?? new Set(); channels.set(name, set); set.add(fn); const off = () => set.delete(fn); effects.push(off); return off; },
    sessions: { list, binding: id => bindings.get(id) }, sidebarRight: { openTab() {} }, sidebarRightTabs: { register: () => () => {} },
    slots: { inject(_name, fn) { const off = fn(); if (off) effects.push(off); }, register(spec, component) { registered.set(spec.name, component); return () => registered.delete(spec.name); } },
  });
  const root = createRoot(document.getElementById('app'));
  const tab = { visible: true, actions: { bindCommands: () => () => {}, openResource() {} } };
  const render = async (id = 'A', visible = true) => {
    tab.visible = visible;
    await R.act(async () => root.render(R.createElement(registered.get('sidebar.right.pane.tab'), { sessionId: id, useTabInfo: () => ({ tab }) })));
  };
  const tick = async amount => {
    const end = now + amount;
    await R.act(async () => {
      for (let count = 0; count < 1000; count++) {
        const next = [...timers.entries()].filter(([, timer]) => timer.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) { now = end; break; }
        timers.delete(next[0]); now = next[1].at; next[1].fn();
        for (let i = 0; i < 12; i++) await Promise.resolve();
        assert.notEqual(count, 999, 'refresh scheduler did not settle');
      }
    });
  };
  const event = (id, type, kind = 'append') => {
    const f = fixtures.get(id); f.change = { kind, entries: [{ type: type === 'assistant/live-chunk' ? 'transient' : 'event', event: { type } }] };
    bindings.get(id).eventSource.emit();
  };
  const act = fn => R.act(async () => { fn(); });
  const refresh = () => act(() => document.querySelector('[aria-label="刷新变更"]').click());
  t.after(async () => {
    await R.act(async () => root.unmount());
    assert.equal(list.listeners.size, 0);
    for (const binding of bindings.values()) assert.equal(binding.eventSource.listeners.size, 0);
    assert.equal(timers.size, 0);
    for (const off of effects.reverse()) off();
    assert.deepEqual(errors, []);
    dom.window.close(); Object.assign(globalThis, prior);
  });
  return { render, tick, act, refresh, event, a, b, catalog, list, bindings, calls, timers, channels,
    text: () => document.querySelector('.jc-page').textContent };
}

test('Changes UI: idle stops I/O, active turns keep live updates, and durable deltas coalesce without scanning tokens/history', { skip: !anchor }, async t => {
  const h = await browser(t); await h.render(); await h.tick(0);
  assert.equal(h.calls.length, 2); await h.tick(10_000); assert.equal(h.calls.length, 2);
  await h.act(() => { for (let i = 0; i < 1000; i++) h.event('A', 'assistant/live-chunk'); h.event('A', 'assistant/message', 'prepend'); h.list.emit(); });
  await h.tick(0); assert.equal(h.calls.length, 2);
  await h.act(() => { h.catalog.byId.A.running = true; h.list.emit(); }); await h.tick(0);
  assert.equal(h.calls.length, 4);
  h.a.f.rows.unshift({ turn: 2, status: 'running' }); await h.tick(1000);
  assert.match(h.text(), /file-2\.txt/); assert.equal(h.calls.length, 6);
  await h.act(() => { h.a.f.rows[0].status = 'finished'; h.catalog.byId.A.running = false; h.list.emit(); h.event('A', 'turn/end'); h.event('A', 'workspace/changes'); });
  await h.tick(0); assert.equal(h.calls.length, 8); await h.tick(10_000); assert.equal(h.calls.length, 8);
  await h.act(() => { const select = document.querySelector('select'); select.value = '1'; select.dispatchEvent(new window.Event('change', { bubbles: true })); });
  await h.tick(0); assert.match(h.text(), /第 1 轮 · 已结束/); assert.match(h.text(), /file-1\.txt/);
  await h.refresh(); await h.tick(0); assert.equal(h.calls.at(-1).forced, true);
  h.a.f.fail = true; await h.refresh(); await h.tick(0); assert.match(h.text(), /fixture read failed/);
  const failedCount = h.calls.length; await h.tick(10_000); assert.equal(h.calls.length, failedCount);
  await h.refresh(); await h.tick(0); assert.doesNotMatch(h.text(), /fixture read failed/);
});

test('Changes UI: in-flight invalidation rereads once; hide, session/generation replacement and late replies release subscriptions and cannot repaint', { skip: !anchor }, async t => {
  const h = await browser(t); const gate = deferred(); h.a.f.block = gate;
  await h.render(); await h.tick(0); assert.equal(h.calls.length, 2);
  await h.act(() => { h.a.f.officialSeq = 42; h.event('A', 'tool/result'); h.event('A', 'workspace/changes'); });
  await h.tick(0); assert.equal(h.calls.length, 2, 'no concurrent refresh');
  await h.act(() => gate.resolve()); await h.tick(0);
  assert.equal(h.calls.length, 4); assert.match(h.text(), /官方轮次对比/);
  const late = deferred(); h.a.f.block = late; await h.refresh(); await h.tick(0);
  const old = h.calls.at(-1); await h.render('A', false);
  assert.equal(old.signal.aborted, true); assert.equal(h.list.listeners.size, 0); assert.equal(h.a.source.listeners.size, 0);
  await h.render('B'); await h.tick(0); await h.act(() => late.resolve()); await h.tick(0);
  assert.equal(h.a.source.listeners.size, 0); assert.equal(h.b.source.listeners.size, 1);
  assert.doesNotMatch(h.text(), /官方轮次对比/);
  const previous = h.b.source; h.bindings.set('B', { eventSource: h.a.source });
  await h.act(() => h.list.emit()); await h.tick(0);
  assert.equal(previous.listeners.size, 0); assert.equal(h.a.source.listeners.size, 1);
  h.b.f.rows = [];
  await h.act(() => { for (const fn of h.channels.get('connection/reset')) fn(); }); await h.tick(0);
  assert.doesNotMatch(h.text(), /file-1\.txt/);
  const idle = h.calls.length; await h.tick(10_000); assert.equal(h.calls.length, idle);
  await h.render('B', false); assert.equal(h.a.source.listeners.size, 0);
});
