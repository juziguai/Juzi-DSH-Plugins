import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';
import { renderClient } from '../plugins/dsh-ultra-effort/build/client.mjs';
const SlotCore = process.env.DSH_SLOT_CORE_MODULE ? (await import(pathToFileURL(process.env.DSH_SLOT_CORE_MODULE))).SlotCore : null;

function harness(groups, current, legacy = false, opts = {}) {
  const states = []; let cursor = 0;
  const selections = [];
  let loadCalls = 0;
  const localeId = opts.localeId ?? 'zh';
  const dicts = new Map(Object.entries(opts.dicts ?? {}));
  const optionEntries = opts.optionEntries ?? [];
  const docListeners = {};
  const mockBody = { tagName: 'BODY' };
  const reactDom = {
    createPortal: (node, container) => ({ type: 'portal', props: { container }, children: [node] }),
  };
  const react = {
    createElement: (type, props, ...children) => typeof type === 'function' ? type({ ...(props ?? {}), children: children.flat(Infinity) }) : ({ type, props: props ?? {}, children: children.flat(Infinity) }),
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial; return [states[i], v => { states[i] = typeof v === 'function' ? v(states[i]) : v; }]; },
    useRef: current => ({ current }), useMemo: fn => fn(), useCallback: fn => fn,
    useEffect(fn) { if (opts.runEffects) fn(); }, useLayoutEffect() {}, useSyncExternalStore: (_, snapshot) => snapshot()
  };
  const scope = {
    window: {
      matchMedia: () => ({ matches: true }),
      addEventListener() {},
      removeEventListener() {},
      __ModuleLoader__: { load: ({ factory }) => { scope.result = factory(id => {
        if (id === 'react') return react;
        if (id === 'react-dom' && opts.withPortal) return reactDom;
        throw new Error(`missing ${id}`);
      }); } }
    },
    ...(opts.withPortal ? {
      document: {
        body: mockBody,
        addEventListener(type, fn) { docListeners[type] = fn; },
        removeEventListener(type) { delete docListeners[type]; },
      },
      AbortController,
      URLSearchParams,
      fetch: async () => ({ ok: false }),
    } : {}),
    setTimeout: opts.runEffects ? () => 0 : setTimeout,
    clearTimeout: opts.runEffects ? () => {} : clearTimeout
  };
  function load(name) {
    vm.runInNewContext(readFileSync(new URL(`../plugins/${name}/lib/client.js`, import.meta.url), 'utf8'), scope);
    return scope.result;
  }
  let component, registration;
  const core = SlotCore ? new SlotCore() : null;
  if (core) {
    core.register({ name: 'root', children: { 'conversation.input.model': { kind: 'single', scope: 'session' } } }, () => null);
    core.register({ name: 'conversation.input.model', children: {
      'conversation.input.model.label': { kind: 'single', scope: 'session', inline: true },
      'conversation.input.model.options': { kind: 'list', scope: 'session' },
    } }, () => null);
    core.register({ name: 'conversation.input.model.label' }, () => 'official');
  }
  const registrations = [];
  const slots = {
    inject: (key, fn) => { if (!core || core.specDynamic(key)) return fn(); return core.subscribeDeclaration(key, () => { if (core.specDynamic(key)) fn(); }); },
    register: (options, fn) => {
      registrations.push(options.name);
      if (options.name === 'conversation.input.model') { registration = options; component = fn; }
      return core?.register(options, fn);
    },
    subscribe: () => () => {},
    getVersion: () => optionEntries.length,
    entriesOfSlot: key => key === 'conversation.input.model.options' ? optionEntries : [],
  };
  const locale = {
    register: (ns, table) => { dicts.set(ns, table); return () => dicts.delete(ns); },
    subscribe: () => () => {},
    getSnapshot: () => ({ id: localeId, revision: 1 }),
    resolveText: value => typeof value === 'string' ? value : (value?.[localeId] ?? value?.en ?? value?.zh ?? ''),
    bind: ns => key => dicts.get(ns)?.[localeId]?.[key] ?? dicts.get(ns)?.en?.[key] ?? key,
  };
  if (legacy) load('dsh-model-version-badge').apply({ slots });
  load('dsh-ultra-effort').apply({ effect(fn, label) { if (label?.includes('dictionaries')) fn(); }, locale, sessions: { subagentAddress: () => undefined }, modelDirectories: { directoryFor: () => ({
    store: {
      subscribe: () => () => {},
      getSnapshot: () => ({ groups, current, failures: opts.failures ?? [], status: opts.status ?? 'ready', error: opts.error ?? null })
    },
    load: async () => { loadCalls++; },
    select: async selection => { selections.push(selection); return { ok: true }; }
  }) }, slots, get: () => undefined, on: () => () => {} });
  const boundT = locale.bind('ui-skin-switcher');
  // No renderSlot prop: merged Ultra must render its labels and options without a slot owner binding.
  const render = (extraProps = {}) => {
    cursor = 0;
    return component({
      sessionId: 'test',
      locked: false,
      t: boundT,
      useSession: selector => selector({ running: false }),
      ...(opts.sessionProps ?? {}),
      ...extraProps,
    });
  };
  return { render, registration, core, registrations, selections, docListeners, mockBody, get loadCalls() { return loadCalls; } };
}
function nodes(tree) { return tree && typeof tree === 'object' ? [tree, ...(tree.children ?? []).flatMap(nodes)] : []; }
function text(tree) { return typeof tree === 'string' ? tree : (tree?.children ?? []).map(text).join(''); }
function openPanel(h) {
  nodes(h.render()).find(n => n.props['aria-haspopup'] === 'dialog').props.onClick({ detail: 1 });
  return h.render();
}
function openModels(h) {
  const panel = openPanel(h);
  const btn = nodes(panel).find(n => n.props['aria-haspopup'] === 'listbox');
  if (btn && !btn.props['aria-expanded']) btn.props.onClick();
  return h.render();
}
const model = { id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash' };
const groups = [{ id: 'deepseek-official', name: 'DeepSeek', models: [model] }];
const current = { provider: groups[0].id, model: model.id };

test('standalone Ultra renders three label placements without label slots', () => {
  const h = harness(groups, current);
  assert.equal(h.registration.children, undefined);
  assert.deepEqual(h.registrations, ['conversation.input.model']);
  const tree = openModels(h);
  for (const cls of ['ue-triggerModel', 'ue-modelName', 'ue-rowName']) {
    const label = nodes(tree).find(n => n.props.className === cls);
    assert.match(text(label), /1017/);
    assert.equal(nodes(label).filter(n => n.props.title === 'DeepSeek-V4.1-Flash-1017').length, 1);
  }
});
test('badges preserve Pro and legacy aliases; unknown models and providers keep their names', () => {
  for (const [id, expected] of [['deepseek-v4-pro', '0813'], ['deepseek-v4-flash', '1017'], ['unknown', null]]) {
    const h = harness([{ ...groups[0], models: [{ id, name: id }] }], { ...current, model: id });
    const label = nodes(h.render()).find(n => n.props.className === 'ue-triggerModel');
    if (expected) assert.match(text(label), new RegExp(expected));
    else assert.equal(text(label), id);
  }
  assert.doesNotMatch(text(harness([{ ...groups[0], id: 'workbuddy' }], { ...current, provider: 'workbuddy' }).render()), /1017/);
});
test('0.2.2 catalog model.badge takes precedence with locale resolution and tones; missing badge falls back to static table', () => {
  const badged = { id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash', badge: { text: { zh: '预览', en: 'Preview' }, tone: 'warning' } };
  const zhTree = openModels(harness([{ ...groups[0], models: [badged] }], current, false, { localeId: 'zh' }));
  for (const cls of ['ue-triggerModel', 'ue-modelName', 'ue-rowName']) {
    const label = nodes(zhTree).find(n => n.props.className === cls);
    assert.match(text(label), /预览/);
    assert.doesNotMatch(text(label), /1017/);
    const pill = nodes(label).find(n => n.props.className === 'ue-ver-badge');
    assert.equal(pill.props['data-tone'], 'warning');
  }
  const enLabel = nodes(harness([{ ...groups[0], models: [badged] }], current, false, { localeId: 'en' }).render()).find(n => n.props.className === 'ue-triggerModel');
  assert.match(text(enLabel), /Preview/);

  const customBadged = { id: 'custom-m', name: 'Custom-1', badge: { text: 'Beta' } };
  const customLabel = nodes(harness([{ id: 'other', name: 'Other', models: [customBadged] }], { provider: 'other', model: 'custom-m' }).render()).find(n => n.props.className === 'ue-triggerModel');
  const customPill = nodes(customLabel).find(n => n.props.className === 'ue-ver-badge');
  assert.equal(text(customPill), 'Beta');
  assert.equal(customPill.props['data-tone'], 'neutral');
});
test('empty directory retains its fallback label', () => {
  const label = nodes(harness([], null).render()).find(n => n.props.className === 'ue-triggerModel');
  assert.ok(text(label).length > 0);
  assert.equal(nodes(label).length, 1);
});
test('current === null keeps trigger enabled, opens directly to ordered model list, renders failures and retries', async () => {
  const accModel = { id: 'deepseek-chat', name: 'DeepSeek-Chat' };
  const unordered = [
    { id: 'third-party', name: 'Custom', models: [{ id: 'm1', name: 'Model-1' }] },
    { id: 'deepseek-official', name: 'DeepSeek API', models: [model] },
    { id: 'deepseek-account', name: 'Account Raw', models: [accModel] },
  ];
  const failures = [{ id: 'deepseek-account', name: 'Account Raw', message: 'token expired' }];
  const h = harness(unordered, null, false, { failures, localeId: 'zh' });
  const initialTrigger = nodes(h.render()).find(n => n.props['aria-haspopup'] === 'dialog');
  assert.equal(initialTrigger.props.disabled, false);

  const opened = openPanel(h);
  const listbox = nodes(opened).find(n => n.props.role === 'listbox');
  assert.ok(listbox, 'panel opens straight to model list when current === null');
  const groupNames = nodes(listbox).filter(n => n.props.className === 'ue-groupName').map(text);
  assert.deepEqual(groupNames, ['DeepSeek 账号', 'DeepSeek', 'Custom']);

  const failureRow = nodes(listbox).find(n => n.props.className === 'ue-failure');
  assert.match(text(failureRow), /DeepSeek 账号 加载失败：token expired/);
  nodes(failureRow).find(n => n.props.className === 'ue-failureRetry').props.onClick();
  assert.equal(h.loadCalls, 1);

  nodes(listbox).find(n => n.props.role === 'option' && text(n).includes('DeepSeek-Chat')).props.onClick();
  await Promise.resolve();
  assert.deepEqual(JSON.parse(JSON.stringify(h.selections)), [{ provider: 'deepseek-account', model: 'deepseek-chat' }]);
});
test('ModelOptionsOutlet renders conversation.input.model.options entries with injected hooks, locale, session props and owner callbacks without declaring children', () => {
  const received = [];
  const teamStore = { subscribe: () => () => {}, getSnapshot: () => ({ enabled: true, members: 3 }) };
  const optionEntries = [
    {
      options: { id: 'second', order: 20 },
      component: () => ({ type: 'div', props: { className: 'opt-item' }, children: ['second'] }),
    },
    {
      locale: 'ui-agent-team',
      options: { id: 'teamwork', order: 10 },
      inject: sessionId => ({
        sessionTag: `team:${sessionId}`,
        hooks: { teamState: teamStore },
      }),
      component: props => {
        received.push(props);
        const enabled = props.useTeamState(s => s.enabled);
        return {
          type: 'div',
          props: {
            className: 'opt-item teamwork-item',
            onFail: () => props.reportFailure('teamwork toggle refused'),
            onDismiss: () => props.dismiss(),
          },
          children: [`${props.t('team.label')}:${enabled ? 'on' : 'off'}:${props.sessionTag}`],
        };
      },
    },
  ];
  const useProjection = () => ({ active: true });
  const useSessions = () => [];
  const h = harness(groups, current, false, {
    optionEntries,
    dicts: { 'ui-agent-team': { zh: { 'team.label': '团队协作' }, en: { 'team.label': 'Teamwork' } } },
    sessionProps: { useProjection, useSessions, select: 'owner-only-strip' },
  });
  assert.equal(h.registration.children, undefined, 'must not re-declare children owned by dsh-client-ui-model-selection');

  const panel = openPanel(h);
  const outlet = nodes(panel).find(n => n.props.className === 'ue-options');
  assert.ok(outlet, 'renders .ue-options in effort view');
  const items = nodes(outlet).filter(n => typeof n.props.className === 'string' && n.props.className.includes('opt-item'));
  assert.deepEqual(items.map(text), ['团队协作:on:team:test', 'second']);
  assert.equal(received.at(-1).useProjection, useProjection);
  assert.equal(received.at(-1).useSessions, useSessions);
  assert.equal(received.at(-1).select, undefined, 'owner-only model props are stripped');
  assert.equal(received.at(-1).locked, false);

  items[0].props.onFail();
  const withErr = h.render();
  assert.match(text(nodes(withErr).find(n => n.props.className === 'sk5-err')), /teamwork toggle refused/);

  nodes(withErr).find(n => n.props['aria-haspopup'] === 'listbox').props.onClick();
  const modelView = h.render();
  assert.equal(nodes(modelView).find(n => n.props.className === 'ue-options'), undefined, 'options hidden in model picker view');

  nodes(modelView).find(n => n.props['aria-haspopup'] === 'listbox').props.onClick();
  const backToEffort = h.render();
  nodes(backToEffort).find(n => n.props.className === 'opt-item teamwork-item').props.onDismiss();
  const closed = h.render();
  assert.equal(nodes(closed).find(n => n.props.role === 'dialog'), undefined);
});
test('Portal mounts .sk5-drop to document.body with data-window-drag-exclude and exempts [role="tooltip"] mousedown', () => {
  const h = harness(groups, current, false, { withPortal: true, runEffects: true });
  const opened = openPanel(h);
  const portal = nodes(opened).find(n => n.type === 'portal');
  assert.ok(portal, 'creates a react-dom portal when document.body is available');
  assert.equal(portal.props.container, h.mockBody);
  assert.match(portal.children[0].props.className, /\bsk5-root\b.*\bsk5-portal\b/);
  const drop = nodes(portal).find(n => n.props.role === 'dialog');
  assert.equal(drop.props['data-window-drag-exclude'], '');

  let prevented = false;
  h.docListeners.mousedown({
    target: { closest: sel => sel === '[role="tooltip"]' ? {} : null },
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, false, 'clicking a portaled tooltip does not close the panel');
  assert.ok(nodes(h.render()).find(n => n.props.role === 'dialog'));

  h.docListeners.mousedown({
    target: { closest: () => null },
    preventDefault() { prevented = true; },
  });
  assert.equal(prevented, true, 'clicking outside closes the panel');
  assert.equal(nodes(h.render()).find(n => n.props.role === 'dialog'), undefined);
});
test('real DSH registry elects Ultra with or without the old badge package during migration', { skip: !SlotCore }, () => {
  for (const legacy of [false, true]) {
    const h = harness(groups, current, legacy);
    assert.equal(h.core.entries('conversation.input.model')[0].options.priority, -1);
    assert.equal(h.core.specDynamic('juzi.ultra.model.label'), undefined);
    const label = nodes(h.render()).find(n => n.props.className === 'ue-triggerModel');
    assert.equal(nodes(label).filter(n => n.props.title === 'DeepSeek-V4.1-Flash-1017').length, 1);
  }
});
test('max slider and particles coexist with badges; keyboard changes use the directory contract', async () => {
  const m = { ...model, reasoning: { defaultEffort: 'high', efforts: [{ id: 'high', name: 'High' }, { id: 'max', name: 'Max' }] } };
  const h = harness([{ ...groups[0], models: [m] }], { ...current, reasoningEffort: 'max' });
  const tree = openPanel(h);
  const slider = nodes(tree).find(n => n.props.role === 'slider');
  assert.ok(slider.props.className.includes('ue-trackMax'));
  assert.equal(nodes(tree).find(n => n.props.className === 'ue-stream').children.length, 14);
  assert.match(text(tree), /1017/);
  slider.props.onKeyDown({ key: 'Home', preventDefault() {} });
  await Promise.resolve();
  assert.deepEqual(JSON.parse(JSON.stringify(h.selections)), [{ ...current, reasoningEffort: 'high' }]);
});
test('model selection retains the official directory contract', async () => {
  const pro = { id: 'deepseek-v4-pro', name: 'DeepSeek-V4-Pro' };
  const h = harness([{ ...groups[0], models: [model, pro] }], current);
  nodes(openModels(h)).find(n => n.props.role === 'option' && text(n).includes(pro.name)).props.onClick();
  await Promise.resolve();
  assert.deepEqual(JSON.parse(JSON.stringify(h.selections)), [{ provider: current.provider, model: pro.id }]);
});
test('checked-in client matches the offline build', () => {
  assert.equal(readFileSync(new URL('../plugins/dsh-ultra-effort/lib/client.js', import.meta.url), 'utf8'), renderClient());
});
