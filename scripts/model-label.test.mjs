import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';
import { renderClient } from '../plugins/dsh-ultra-effort/build/client.mjs';
const SlotCore = process.env.DSH_SLOT_CORE_MODULE ? (await import(pathToFileURL(process.env.DSH_SLOT_CORE_MODULE))).SlotCore : null;

function harness(groups, current, legacy = false) {
  const states = []; let cursor = 0;
  const selections = [];
  const react = {
    createElement: (type, props, ...children) => typeof type === 'function' ? type(props ?? {}) : ({ type, props: props ?? {}, children: children.flat(Infinity) }),
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial; return [states[i], v => { states[i] = typeof v === 'function' ? v(states[i]) : v; }]; },
    useRef: current => ({ current }), useMemo: fn => fn(), useCallback: fn => fn,
    useEffect() {}, useLayoutEffect() {}, useSyncExternalStore: (_, snapshot) => snapshot()
  };
  const scope = {
    window: { matchMedia: () => ({ matches: true }), __ModuleLoader__: { load: ({ factory }) => { scope.result = factory(id => { assert.equal(id, 'react'); return react; }); } } },
    setTimeout, clearTimeout
  };
  function load(name) {
    vm.runInNewContext(readFileSync(new URL(`../plugins/${name}/lib/client.js`, import.meta.url), 'utf8'), scope);
    return scope.result;
  }
  let component, registration;
  const core = SlotCore ? new SlotCore() : null;
  if (core) {
    core.register({ name: 'root', children: { 'conversation.input.model': { kind: 'single', scope: 'session' } } }, () => null);
    core.register({ name: 'conversation.input.model', children: { 'conversation.input.model.label': { kind: 'single', scope: 'session', inline: true } } }, () => null);
    core.register({ name: 'conversation.input.model.label' }, () => 'official');
  }
  const registrations = [];
  const slots = {
    inject: (key, fn) => { if (!core || core.specDynamic(key)) return fn(); return core.subscribeDeclaration(key, () => { if (core.specDynamic(key)) fn(); }); },
    register: (options, fn) => {
      registrations.push(options.name);
      if (options.name === 'conversation.input.model') { registration = options; component = fn; }
      return core?.register(options, fn);
    }
  };
  if (legacy) load('dsh-model-version-badge').apply({ slots });
  load('dsh-ultra-effort').apply({ effect() {}, sessions: { subagentAddress: () => undefined }, modelDirectories: { directoryFor: () => ({
    store: { getSnapshot: () => ({ groups, current, status: 'ready', error: null }) },
    select: async selection => { selections.push(selection); return { ok: true }; }
  }) }, slots });
  // No renderSlot prop: merged Ultra must render its labels without a slot binding.
  const render = () => { cursor = 0; return component({ sessionId: 'test', locked: false, useSession: selector => selector({ running: false }) }); };
  return { render, registration, core, registrations, selections };
}
function nodes(tree) { return tree && typeof tree === 'object' ? [tree, ...(tree.children ?? []).flatMap(nodes)] : []; }
function text(tree) { return typeof tree === 'string' ? tree : (tree?.children ?? []).map(text).join(''); }
function openPanel(h) {
  nodes(h.render()).find(n => n.props['aria-haspopup'] === 'dialog').props.onClick({ detail: 1 });
  return h.render();
}
function openModels(h) {
  nodes(openPanel(h)).find(n => n.props['aria-haspopup'] === 'listbox').props.onClick();
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
test('empty directory retains its fallback label', () => {
  const label = nodes(harness([], null).render()).find(n => n.props.className === 'ue-triggerModel');
  assert.ok(text(label).length > 0);
  assert.equal(nodes(label).length, 1);
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
