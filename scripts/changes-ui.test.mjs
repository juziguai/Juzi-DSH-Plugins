import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import vm from 'node:vm';

const anchor = process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes; }); return { promise, resolve }; };

function createHeadlessClient({ subagentIds = new Set(), files = [] } = {}) {
  let cursor = 0, currentInstance = null;
  const React = {
    createElement(type, props, ...children) {
      return { type, props: { ...(props ?? {}), children: children.flat(Infinity).filter(child => child !== null && child !== undefined && child !== false) } };
    },
    useState(initial) {
      const inst = currentInstance, idx = cursor++;
      if (!(idx in inst.states)) inst.states[idx] = typeof initial === 'function' ? initial() : initial;
      const set = next => { inst.states[idx] = typeof next === 'function' ? next(inst.states[idx]) : next; };
      return [inst.states[idx], set];
    },
    useRef(initial) {
      const inst = currentInstance, idx = cursor++;
      if (!(idx in inst.refs)) inst.refs[idx] = { current: initial };
      return inst.refs[idx];
    },
    useId() {
      const inst = currentInstance, idx = cursor++;
      if (!(idx in inst.ids)) inst.ids[idx] = `id-${idx}-`;
      return inst.ids[idx];
    },
    useEffect(fn, deps) {
      const inst = currentInstance, idx = cursor++;
      const prev = inst.effects[idx];
      const changed = !prev || !deps || deps.some((dep, i) => !Object.is(dep, prev.deps[i]));
      if (changed) inst.pendingEffects.push({ idx, fn, deps });
    },
    useLayoutEffect(fn, deps) { React.useEffect(fn, deps); },
  };
  let plugin;
  const registered = new Map(), timers = [], fetches = [], openedResources = [], openedTabs = [], listListeners = new Set();
  const list = {
    getSnapshot: () => ({ byId: {} }),
    subscribe(fn) { listListeners.add(fn); return () => listListeners.delete(fn); },
  };
  const fetch = async (url, options) => {
    const u = new URL(url, 'http://fixture.invalid/');
    const action = u.pathname.split('.').at(-1), sessionId = u.searchParams.get('sessionId');
    fetches.push({ action, sessionId, signal: options?.signal });
    if (action === 'list') return { ok: true, json: async () => ({ turns: [{ turn: 1, status: 'finished' }], maxTurns: 30 }) };
    return {
      ok: true,
      json: async () => ({ turn: 1, status: 'finished', revision: 1, total: files.length, added: files.length, deleted: 0, officialSeq: null, files }),
    };
  };
  vm.runInNewContext(readFileSync(new URL('../plugins/dsh-changes/lib/client.js', import.meta.url), 'utf8'), {
    window: { __ModuleLoader__: { load: ({ factory }) => { plugin = factory(() => React); } } },
    document: { createElement: () => ({ textContent: '', remove() {} }), head: { appendChild() {} }, addEventListener() {}, removeEventListener() {} },
    fetch, AbortController, URLSearchParams,
    setTimeout(fn) { timers.push(fn); return timers.length; },
    clearTimeout() {},
  });
  plugin.apply({
    effect() {},
    on() {},
    sessions: {
      list,
      binding: () => undefined,
      subagentAddress: sessionId => subagentIds.has(sessionId) ? { parentSessionId: 'main-session', childSessionId: sessionId, mode: 'subagent' } : undefined,
    },
    sidebarRight: { openTab: kind => openedTabs.push(kind) },
    sidebarRightTabs: { register: () => () => {} },
    slots: {
      inject(_name, fn) { fn(); },
      register(spec, component) { registered.set(spec.name, component); return () => registered.delete(spec.name); },
    },
  });

  function expand(node, instances, keyPrefix = 'r') {
    if (!node || typeof node !== 'object') return node;
    if (Array.isArray(node)) return node.map((item, i) => expand(item, instances, `${keyPrefix}.${i}`));
    if (typeof node.type === 'function') {
      const id = `${keyPrefix}:${node.type.name || 'anon'}:${node.props?.key ?? ''}`;
      let inst = instances.get(id);
      if (!inst) { inst = { states: [], refs: [], ids: [], effects: [], pendingEffects: [] }; instances.set(id, inst); }
      const prevInstance = currentInstance, prevCursor = cursor;
      currentInstance = inst; cursor = 0;
      const rendered = node.type(node.props);
      currentInstance = prevInstance; cursor = prevCursor;
      return expand(rendered, instances, id);
    }
    return { ...node, props: { ...node.props, children: expand(node.props.children, instances, keyPrefix) } };
  }
  async function flush(instances) {
    for (const inst of instances.values()) {
      while (inst.pendingEffects.length) {
        const effect = inst.pendingEffects.shift();
        inst.effects[effect.idx]?.cleanup?.();
        const cleanup = effect.fn();
        inst.effects[effect.idx] = { deps: effect.deps, cleanup };
      }
    }
    while (timers.length) {
      const fn = timers.shift();
      await fn();
    }
    for (let i = 0; i < 6; i++) await Promise.resolve();
  }
  function findAll(node, predicate, out = []) {
    if (!node || typeof node !== 'object') return out;
    if (Array.isArray(node)) { for (const child of node) findAll(child, predicate, out); return out; }
    if (predicate(node)) out.push(node);
    findAll(node.props?.children, predicate, out);
    return out;
  }
  function textOf(node) {
    if (node === null || node === undefined || typeof node === 'boolean') return '';
    if (typeof node === 'string' || typeof node === 'number') return String(node);
    if (Array.isArray(node)) return node.map(textOf).join('');
    return textOf(node.props?.children);
  }
  const tab = { visible: true, actions: { bindCommands: () => () => {}, openResource: uri => openedResources.push(uri) } };
  async function renderTab(props) {
    const instances = new Map();
    const Body = registered.get('sidebar.right.pane.tab');
    let tree = expand(React.createElement(Body, { useTabInfo: () => ({ tab }), ...props }), instances);
    await flush(instances);
    tree = expand(React.createElement(Body, { useTabInfo: () => ({ tab }), ...props }), instances);
    return {
      tree,
      text: () => textOf(tree),
      findAll: predicate => findAll(tree, predicate),
      unmount() {
        for (const inst of instances.values()) {
          for (const effect of inst.effects) effect?.cleanup?.();
        }
      },
    };
  }
  function renderHeader(props) {
    const instances = new Map();
    const Header = registered.get('conversation.session.header.utilities');
    return expand(React.createElement(Header, props), instances);
  }
  return { renderTab, renderHeader, fetches, openedResources, openedTabs, listListeners };
}

test('Changes UI: Windows drive-letter colons are preserved literal in file resource URIs while encoding segments and stripping leading ./', async () => {
  const client = createHeadlessClient({
    files: [
      { id: 'win-abs', path: 'D:\\outside dir\\note #1.txt', display: 'D:\\outside dir\\note #1.txt', status: 'modified', added: 2, deleted: 1 },
      { id: 'rel-dot', path: './src/sub:name/index.ts', display: 'src/sub:name/index.ts', status: 'added', added: 5, deleted: 0 },
      { id: 'posix-abs', path: '/etc/hosts', display: '/etc/hosts', status: 'modified', added: 1, deleted: 0 },
    ],
  });
  const view = await client.renderTab({ sessionId: 'session:main' });
  try {
    const openButtons = view.findAll(node => node.type === 'button' && String(node.props?.['aria-label'] ?? '').startsWith('打开 '));
    assert.equal(openButtons.length, 3);
    for (const button of openButtons) button.props.onClick();
    assert.deepEqual(client.openedResources, [
      'dsh-resource://file/session/session:main/D:/outside%20dir/note%20%231.txt',
      'dsh-resource://file/session/session:main/src/sub%3Aname/index.ts',
      'dsh-resource://file/session/session:main//etc/hosts',
    ]);
    assert.doesNotMatch(client.openedResources[0], /D%3A/i);
  } finally {
    view.unmount();
  }
});

test('Changes UI: hides header button on subagent sessions and renders friendly hint without polling Host routes', async () => {
  const client = createHeadlessClient({ subagentIds: new Set(['subagent-by-service']) });

  // 1) Header button renders on main session and opens tab
  const mainHeader = client.renderHeader({ sessionId: 'main-session', useSession: selector => selector({ subagent: null }) });
  assert.equal(mainHeader?.type, 'button');
  mainHeader.props.onClick();
  assert.deepEqual(client.openedTabs, ['juzi-changes']);

  // 2) Header button hides when ctx.sessions.subagentAddress(sessionId) is defined
  assert.equal(client.renderHeader({ sessionId: 'subagent-by-service' }), null);

  // 3) Header button hides when props.useSession reports s.subagent != null
  assert.equal(client.renderHeader({
    sessionId: 'subagent-by-hook',
    useSession: selector => selector({ subagent: { address: { parentSessionId: 'main-session', childSessionId: 'subagent-by-hook' } } }),
  }), null);

  // 4) Rightbar Page shows friendly subagent hint and performs zero fetch/subscription I/O
  const byService = await client.renderTab({ sessionId: 'subagent-by-service' });
  try {
    assert.match(byService.text(), /子代理会话不单独记录轮次，文件变更汇总在主会话对应轮次中查看。/);
    assert.doesNotMatch(byService.text(), /等待新一轮任务/);
    assert.equal(client.fetches.length, 0);
    assert.equal(client.listListeners.size, 0);
    const select = byService.findAll(node => node.type === 'select')[0];
    const refreshButton = byService.findAll(node => node.type === 'button' && node.props?.['aria-label'] === '刷新变更')[0];
    assert.equal(select.props.disabled, true);
    assert.equal(refreshButton.props.disabled, true);
  } finally {
    byService.unmount();
  }

  const byHook = await client.renderTab({
    sessionId: 'subagent-by-hook',
    useSession: selector => selector({ subagent: { address: { parentSessionId: 'main-session', childSessionId: 'subagent-by-hook' } } }),
  });
  try {
    assert.match(byHook.text(), /子代理会话不单独记录轮次，文件变更汇总在主会话对应轮次中查看。/);
    assert.equal(client.fetches.length, 0);
  } finally {
    byHook.unmount();
  }
});

async function browser(t) {
  const require = createRequire(pathToFileURL(resolve(anchor)));
  const R = require('react'), { JSDOM, VirtualConsole } = require('jsdom');
  const errors = [], vc = new VirtualConsole();
  vc.on('jsdomError', error => { if (error.type !== 'css parsing') errors.push(error); });
  const dom = new JSDOM('<html><head></head><body><main id="app"></main></body></html>', { pretendToBeVisual: true, virtualConsole: vc });
  const prior = { window: globalThis.window, document: globalThis.document, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  const { createRoot } = require('react-dom/client');
  const effects = [], registered = new Map(), channels = new Map(), bindings = new Map(), fixtures = new Map(), timers = new Map(), calls = [], openedResources = [];
  const subagents = new Set();
  let module, now = 0, serial = 0;
  const observable = getSnapshot => {
    const listeners = new Set();
    return { getSnapshot, listeners, subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }, emit() { for (const fn of [...listeners]) fn(); } };
  };
  const catalog = { byId: {} }, list = observable(() => catalog);
  const session = id => {
    const f = { rows: [{ turn: 1, status: 'finished' }], revision: 1, officialSeq: null, change: { kind: 'replace', entries: [] }, files: null };
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
    const files = f.files ?? [{ id: `f-${turn}`, path: `file-${turn}.txt`, display: `file-${turn}.txt`, status: 'modified', added: 1, deleted: 1 }];
    const data = action === 'list' ? { turns: f.rows.map(row => ({ ...row })), maxTurns: 30 } : {
      turn, status: f.rows.find(row => row.turn === turn)?.status, revision: f.revision, total: files.length, added: 1, deleted: 1,
      officialSeq: f.officialSeq, files,
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
    sessions: { list, binding: id => bindings.get(id), subagentAddress: id => subagents.has(id) ? { parentSessionId: 'A', childSessionId: id, mode: 'subagent' } : undefined },
    sidebarRight: { openTab() {} }, sidebarRightTabs: { register: () => () => {} },
    slots: { inject(_name, fn) { const off = fn(); if (off) effects.push(off); }, register(spec, component) { registered.set(spec.name, component); return () => registered.delete(spec.name); } },
  });
  const root = createRoot(document.getElementById('app'));
  const tab = { visible: true, actions: { bindCommands: () => () => {}, openResource(uri) { openedResources.push(uri); } } };
  const render = async (id = 'A', visible = true, extraProps = {}) => {
    tab.visible = visible;
    await R.act(async () => root.render(R.createElement(registered.get('sidebar.right.pane.tab'), { sessionId: id, useTabInfo: () => ({ tab }), ...extraProps })));
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
  return { render, tick, act, refresh, event, a, b, catalog, list, bindings, calls, timers, channels, subagents, openedResources, registered, R,
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

test('Changes UI JSDOM: Windows drive URI opening and subagent session view', { skip: !anchor }, async t => {
  const h = await browser(t);
  h.a.f.files = [{ id: 'w1', path: 'D:\\work\\a b.ts', display: 'D:\\work\\a b.ts', status: 'modified', added: 1, deleted: 0 }];
  await h.render('A'); await h.tick(0);
  await h.act(() => document.querySelector('[aria-label="打开 D:\\\\work\\\\a b.ts"]')?.click());
  assert.deepEqual(h.openedResources, ['dsh-resource://file/session/A/D:/work/a%20b.ts']);
  const priorCalls = h.calls.length;
  h.subagents.add('SUB');
  await h.render('SUB'); await h.tick(10_000);
  assert.equal(h.calls.length, priorCalls);
  assert.match(h.text(), /子代理会话不单独记录轮次，文件变更汇总在主会话对应轮次中查看。/);
});
