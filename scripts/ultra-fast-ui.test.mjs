import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const anchor = process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
test('real React DOM: confirmed lightning, Max/reset isolation, chat switch, missing Host and early-return cleanup', { skip: !anchor }, async () => {
  const require = createRequire(pathToFileURL(resolve(anchor)));
  const React = require('react'), { createRoot } = require('react-dom/client'), { JSDOM, VirtualConsole } = require('jsdom');
  const jsdomErrors = [], virtualConsole = new VirtualConsole();
  // jsdom cannot parse all current Chrome CSS. This suite covers interaction; Chrome covers styles.
  virtualConsole.on('jsdomError', error => { if (error.type !== 'css parsing') jsdomErrors.push(error); });
  const dom = new JSDOM('<!doctype html><html><head></head><body><main id="app"></main></body></html>', { pretendToBeVisual: true, virtualConsole });
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT, fetch: globalThis.fetch };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  window.matchMedia = () => ({ matches: true });
  let module, Component, revision = 0, preferences = {}, release, unavailable = false;
  let reads = 0; const resetListeners = new Set();
  const effects = [], writes = [], selections = [];
  window.__ModuleLoader__ = { load: ({ factory }) => { module = factory(id => { assert.equal(id, 'react'); return React; }); } };
  vm.runInThisContext(readFileSync(new URL('../plugins/dsh-ultra-effort/lib/client.js', import.meta.url), 'utf8'));
  const row = () => ({ ns: 'ui-ultra-effort', applies: 'live', revision, value: { fastSessions: { ...preferences } } });
  globalThis.fetch = async () => {
    reads++;
    if (unavailable) throw new Error('offline');
    return Response.json({ protocol: 1, namespace: 'ui-ultra-effort', ready: true, writable: true, idle: true, boundary: 'next-turn' });
  };
  const state = { groups: [{ id: 'deepseek-official', name: 'DeepSeek', models: [{ id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash',
    reasoning: { defaultEffort: 'high', efforts: [{ id: 'high', name: 'High' }, { id: 'max', name: 'Max' }] } }] }],
    current: { provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'max' }, status: 'ready', error: null };
  const settingsApi = {
    describe: async () => ({ ok: true, value: { writable: true, namespaces: [row()] } }),
    mutate: async (ns, ops, rev) => { writes.push({ ns, ops, rev }); await new Promise(resolve => { release = resolve; });
      preferences[ops[0].path[1]] = ops[0].value; revision++; return { ok: true, value: row() }; },
  };
  module.apply({ effect(fn) { const undo = fn(); if (undo) effects.push(undo); }, locale: { register: () => () => {} },
    on(name, fn) { assert.equal(name, 'connection/reset'); resetListeners.add(fn); return () => resetListeners.delete(fn); },
    sessions: { subagentAddress: id => id === 'child' ? {} : undefined },
    // Cordis forbids dotted service access without inject. Optional services use get().
    remote: { get settings() { throw new Error('cannot get property "remote.settings" without inject'); } },
    get(key) { assert.equal(key, 'remote.settings'); return settingsApi; },
    modelDirectories: { directoryFor: id => {
      if (id === 'unready') throw new Error('directory not ready');
      return { store: { getSnapshot: () => state, subscribe: () => () => {} }, load: async () => {},
        select: async value => { selections.push(value); return { ok: true }; } };
    } }, slots: { inject: (_, fn) => fn(), register(_, component) { Component = component; } },
  });
  const root = createRoot(document.getElementById('app'));
  const render = (sessionId, locked = false, running = false) => React.act(async () => root.render(React.createElement(Component, {
    sessionId, locked, useSession: selector => selector({ running }),
  })));
  const click = selector => React.act(async () => document.querySelector(selector).click());
  const bolt = () => document.querySelector('button.ue-bolt');
  try {
    await render('A'); assert.equal(reads, 1);
    await click('.ue-trigger'); assert.equal(reads, 2);
    await React.act(async () => { for (const fn of resetListeners) fn(); });
    assert.equal(reads, 3, 'an open panel refreshes after reconnect');
    await click('.ue-trigger'); assert.equal(reads, 3, 'closing never refreshes');
    assert.equal(resetListeners.size, 0);
    await render('A', true); await render('A');
    await React.act(async () => { window.dispatchEvent(new window.Event('focus')); window.dispatchEvent(new window.Event('online')); });
    assert.equal(reads, 3, 'closed panels ignore lock/focus/online transitions');
    await click('.ue-trigger'); assert.equal(reads, 4);
    assert.equal(bolt().getAttribute('aria-pressed'), 'false'); assert.equal(bolt().getAttribute('aria-disabled'), 'false');
    await click('.ue-bolt'); assert.equal(bolt().getAttribute('aria-pressed'), 'false'); assert.equal(bolt().getAttribute('aria-busy'), 'true');
    await React.act(async () => release());
    assert.equal(bolt().getAttribute('aria-pressed'), 'true'); assert(document.querySelector('.ue-trackMax'));
    assert.equal(document.querySelectorAll('.ue-stream i').length, 14); assert.match(document.querySelector('.ue-triggerModel').textContent, /1017/);
    assert.equal(selections.length, 0);
    await click('.ue-reset'); assert.equal(selections[0].reasoningEffort, 'high'); assert.equal(writes.length, 1);
    assert.equal(bolt().getAttribute('aria-pressed'), 'true');
    await render('B'); assert.equal(bolt().getAttribute('aria-pressed'), 'false');
    await render('A'); assert.equal(bolt().getAttribute('aria-pressed'), 'true');
    await render('A', true); assert.equal(bolt().getAttribute('aria-disabled'), 'true'); await click('.ue-bolt'); assert.equal(writes.length, 1);
    await render('A', false, true); assert.equal(bolt().getAttribute('aria-disabled'), 'true');
    assert.equal(document.querySelector('.ue-trigger').disabled, false);
    await click('.ue-bolt'); assert.equal(writes.length, 1);
    assert.match(document.querySelector('.ue-fastStatus').textContent, /当前任务执行中/);
    unavailable = true; await render('A');
    assert.match(document.querySelector('.ue-fastStatus').textContent, /后台暂不可用/);
    assert.equal(document.querySelector('button.ue-model').disabled, false);
    unavailable = false; await click('.ue-fastStatus button'); assert.equal(bolt().getAttribute('aria-pressed'), 'true');
    unavailable = true; await React.act(async () => window.dispatchEvent(new window.Event('online')));
    assert.match(document.querySelector('.ue-fastStatus').textContent, /后台暂不可用/);
    unavailable = false; await React.act(async () => window.dispatchEvent(new window.Event('focus')));
    assert.equal(bolt().getAttribute('aria-pressed'), 'true');
    await render('child'); assert.equal(document.getElementById('app').textContent, '');
    await render('unready'); assert.equal(document.getElementById('app').textContent, '');
    await render('A'); assert(document.querySelector('.ue-trackMax'));
    assert.deepEqual(jsdomErrors, []);
  } finally {
    await React.act(async () => root.unmount());
    assert.equal(resetListeners.size, 0);
    for (const undo of effects.reverse()) await undo();
    assert.equal(document.querySelectorAll('style[data-plugin]').length, 0);
    dom.window.close();
    Object.assign(globalThis, { window: prior.window, document: prior.document, IS_REACT_ACT_ENVIRONMENT: prior.act, fetch: prior.fetch });
  }
});
