import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const anchor = process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
test('real React DOM: confirmed lightning, Max/reset isolation, chat switch, 0.2.2 Portal/Teamwork/Badge/Recovery, missing Host and early-return cleanup', { skip: !anchor }, async () => {
  const require = createRequire(pathToFileURL(resolve(anchor)));
  const React = require('react'), ReactDOM = require('react-dom'), { createRoot } = require('react-dom/client'), { JSDOM, VirtualConsole } = require('jsdom');
  const jsdomErrors = [], virtualConsole = new VirtualConsole();
  // jsdom cannot parse all current Chrome CSS. This suite covers interaction; Chrome covers styles.
  virtualConsole.on('jsdomError', error => { if (error.type !== 'css parsing') jsdomErrors.push(error); });
  const dom = new JSDOM('<!doctype html><html><head></head><body><main id="app"></main></body></html>', { pretendToBeVisual: true, virtualConsole });
  const prior = { window: globalThis.window, document: globalThis.document, act: globalThis.IS_REACT_ACT_ENVIRONMENT, fetch: globalThis.fetch, consoleError: console.error };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true });
  window.matchMedia = () => ({ matches: true });
  let module, Component, registration, revision = 0, preferences = {}, release, unavailable = false;
  let reads = 0, loadCalls = 0, optionVersion = 0;
  const resetListeners = new Set(), slotListeners = new Set();
  const effects = [], writes = [], selections = [], optionEntries = [];
  const dicts = new Map();
  window.__ModuleLoader__ = { load: ({ factory }) => { module = factory(id => {
    if (id === 'react') return React;
    if (id === 'react-dom') return ReactDOM;
    throw new Error(`unexpected module: ${id}`);
  }); } };
  vm.runInThisContext(readFileSync(new URL('../plugins/dsh-ultra-effort/lib/client.js', import.meta.url), 'utf8'));
  const row = () => ({ ns: 'ui-ultra-effort', applies: 'live', revision, value: { fastSessions: { ...preferences } } });
  globalThis.fetch = async () => {
    reads++;
    if (unavailable) throw new Error('offline');
    return Response.json({ protocol: 1, namespace: 'ui-ultra-effort', ready: true, writable: true, idle: true, boundary: 'next-turn' });
  };
  const state = { groups: [{ id: 'deepseek-official', name: 'DeepSeek', models: [{ id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash',
    reasoning: { defaultEffort: 'high', efforts: [{ id: 'high', name: 'High' }, { id: 'max', name: 'Max' }] } }] }],
    failures: [],
    current: { provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'max' }, status: 'ready', error: null };
  const settingsApi = {
    describe: async () => ({ ok: true, value: { writable: true, namespaces: [row()] } }),
    mutate: async (ns, ops, rev) => { writes.push({ ns, ops, rev }); await new Promise(resolve => { release = resolve; });
      preferences[ops[0].path[1]] = ops[0].value; revision++; return { ok: true, value: row() }; },
  };
  const localeSnapshot = { id: 'zh', revision: 1 };
  const locale = {
    register: (ns, table) => { dicts.set(ns, table); return () => dicts.delete(ns); },
    subscribe: () => () => {},
    getSnapshot: () => localeSnapshot,
    resolveText: v => typeof v === 'string' ? v : (v?.zh ?? v?.en ?? ''),
    bind: ns => key => dicts.get(ns)?.zh?.[key] ?? key,
  };
  module.apply({ effect(fn) { const undo = fn(); if (undo) effects.push(undo); }, locale,
    on(name, fn) { assert.equal(name, 'connection/reset'); resetListeners.add(fn); return () => resetListeners.delete(fn); },
    sessions: { subagentAddress: id => id === 'child' ? {} : undefined },
    // Cordis forbids dotted service access without inject. Optional services use get().
    remote: { get settings() { throw new Error('cannot get property "remote.settings" without inject'); } },
    get(key) { assert.equal(key, 'remote.settings'); return settingsApi; },
    modelDirectories: { directoryFor: id => {
      if (id === 'unready') throw new Error('directory not ready');
      return { store: { getSnapshot: () => state, subscribe: () => () => {} }, load: async () => { loadCalls++; },
        select: async value => { selections.push(value); return { ok: true }; } };
    } },
    slots: {
      inject: (_, fn) => fn(),
      register(opts, component) { registration = opts; Component = component; },
      subscribe: (slot, fn) => { if (slot === 'conversation.input.model.options') { slotListeners.add(fn); return () => slotListeners.delete(fn); } return () => {}; },
      getVersion: () => optionVersion,
      entriesOfSlot: slot => slot === 'conversation.input.model.options' ? optionEntries : [],
    },
  });
  assert.equal(registration.children, undefined);
  const root = createRoot(document.getElementById('app'));
  const render = (sessionId, locked = false, running = false, extra = {}) => React.act(async () => root.render(React.createElement(Component, {
    sessionId, locked, useSession: selector => selector({ running }), useProjection: sel => sel({ ok: 'proj' }), ...extra,
  })));
  const click = selector => React.act(async () => document.querySelector(selector).click());
  const bolt = () => document.querySelector('button.ue-bolt');
  try {
    await render('A'); assert.equal(reads, 1);
    await click('.ue-trigger'); assert.equal(reads, 2);
    // 0.2.2 Portal & drag exclusion contract: drop renders under document.body, outside #app.
    const portalDrop = document.body.querySelector(':scope > .sk5-root.sk5-portal > .sk5-drop');
    assert.ok(portalDrop, 'panel is portaled directly to document.body');
    assert.equal(portalDrop.hasAttribute('data-window-drag-exclude'), true);
    assert.equal(document.getElementById('app').querySelector('.sk5-drop'), null);

    // Portaled tooltip clicks must NOT close the menu, while outside mousedown closes it.
    const tooltip = document.createElement('div');
    tooltip.setAttribute('role', 'tooltip');
    const tipChild = document.createElement('span');
    tooltip.appendChild(tipChild);
    document.body.appendChild(tooltip);
    await React.act(async () => { tipChild.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true })); });
    assert.ok(document.querySelector('.sk5-drop'), 'clicking inside [role="tooltip"] keeps menu open');
    tooltip.remove();

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

    // 0.2.2 Teamwork option in conversation.input.model.options + ErrorBoundary isolation.
    dicts.set('ui-agent-team', { zh: { 'team.title': '智能体团队' }, en: { 'team.title': 'Agent Team' } });
    const teamSnapshot = { active: true };
    const teamStore = { subscribe: () => () => {}, getSnapshot: () => teamSnapshot };
    const suppressError = event => { if (event.error?.message === 'broken-third-party-option') event.preventDefault(); };
    window.addEventListener('error', suppressError);
    console.error = () => {};
    optionEntries.push(
      { options: { id: 'broken', order: 5 }, component: () => { throw new Error('broken-third-party-option'); } },
      {
        locale: 'ui-agent-team',
        options: { id: 'teamwork', order: 10 },
        inject: sid => ({ sid, hooks: { team: teamStore } }),
        component: p => React.createElement('div', { className: 'teamwork-row' },
          React.createElement('span', { className: 'teamwork-label' }, `${p.t('team.title')}:${p.sid}:${p.useTeam(s => s.active)}:${p.useProjection(x => x.ok)}`),
          React.createElement('button', { type: 'button', className: 'teamwork-err', onClick: () => p.reportFailure('团队模式切换失败') }, 'err'),
          React.createElement('button', { type: 'button', className: 'teamwork-close', onClick: () => p.dismiss() }, 'close'),
        ),
      },
    );
    optionVersion++;
    await render('A');
    window.removeEventListener('error', suppressError);
    console.error = prior.consoleError;
    assert.equal(document.querySelector('.sk5-portal .ue-options .teamwork-label')?.textContent, '智能体团队:A:true:proj');
    await click('.teamwork-err');
    assert.match(document.querySelector('.sk5-portal .sk5-err').textContent, /团队模式切换失败/);
    await click('.teamwork-close');
    assert.equal(document.querySelector('.sk5-drop'), null, 'dismiss() from option closes portaled menu');

    // 0.2.2 catalog model.badge, current === null recovery, and state.failures retry.
    state.groups = [
      { id: 'deepseek-official', name: 'DeepSeek', models: [{ id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash', badge: { text: { zh: '最新', en: 'Latest' }, tone: 'success' } }] },
      { id: 'deepseek-account', name: 'Account', models: [{ id: 'deepseek-chat', name: 'DeepSeek-Chat' }] },
    ];
    state.current = null;
    state.failures = [{ id: 'deepseek-account', name: 'Account', message: '网络超时' }];
    await render('A');
    assert.equal(document.querySelector('.ue-trigger').disabled, false);
    await click('.ue-trigger');
    assert.ok(document.querySelector('.sk5-portal [role="listbox"]'), 'opens directly to model list when current === null');
    const groupTitles = [...document.querySelectorAll('.sk5-portal .ue-groupName')].map(n => n.textContent);
    assert.deepEqual(groupTitles, ['DeepSeek 账号', 'DeepSeek']);
    const badgeEl = document.querySelector('.sk5-portal .ue-ver-badge');
    assert.equal(badgeEl.getAttribute('data-tone'), 'success');
    assert.equal(badgeEl.textContent, '最新');
    assert.match(document.querySelector('.sk5-portal .ue-failureText').textContent, /DeepSeek 账号 加载失败：网络超时/);
    const loadsBeforeRetry = loadCalls;
    await click('.ue-failureRetry');
    assert.equal(loadCalls, loadsBeforeRetry + 1);
    await click('.sk5-portal .ue-row');
    assert.deepEqual(selections.at(-1), { provider: 'deepseek-account', model: 'deepseek-chat' });

    // Restore Max state for early-return & re-mount assertions.
    optionEntries.length = 0; optionVersion++;
    state.failures = [];
    state.groups = [{ id: 'deepseek-official', name: 'DeepSeek', models: [{ id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash',
      reasoning: { defaultEffort: 'high', efforts: [{ id: 'high', name: 'High' }, { id: 'max', name: 'Max' }] } }] }];
    state.current = { provider: 'deepseek-official', model: 'deepseek-flash', reasoningEffort: 'max' };
    await render('child'); assert.equal(document.getElementById('app').textContent, ''); assert.equal(document.querySelector('.sk5-portal'), null);
    await render('unready'); assert.equal(document.getElementById('app').textContent, ''); assert.equal(document.querySelector('.sk5-portal'), null);
    await render('A'); await click('.ue-trigger'); assert(document.querySelector('.ue-trackMax'));
    await React.act(async () => { document.body.dispatchEvent(new window.MouseEvent('mousedown', { bubbles: true })); });
    assert.equal(document.querySelector('.sk5-drop'), null, 'outside mousedown closes portaled menu');
    assert.deepEqual(jsdomErrors, []);
  } finally {
    console.error = prior.consoleError;
    await React.act(async () => root.unmount());
    assert.equal(resetListeners.size, 0);
    for (const undo of effects.reverse()) await undo();
    assert.equal(document.querySelectorAll('style[data-plugin]').length, 0);
    dom.window.close();
    Object.assign(globalThis, { window: prior.window, document: prior.document, IS_REACT_ACT_ENVIRONMENT: prior.act, fetch: prior.fetch });
  }
});
