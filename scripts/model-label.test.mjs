import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { pathToFileURL } from 'node:url';
const SlotCore = process.env.DSH_SLOT_CORE_MODULE ? (await import(pathToFileURL(process.env.DSH_SLOT_CORE_MODULE))).SlotCore : null;

function harness(groups, current, badgeEnabled = true) {
  const states = []; let cursor = 0;
  const react = {
    createElement: (type, props, ...children) => ({ type, props: props ?? {}, children: children.flat(Infinity) }),
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial; return [states[i], v => { states[i] = typeof v === 'function' ? v(states[i]) : v; }]; },
    useRef: current => ({ current }), useMemo: fn => fn(), useCallback: fn => fn,
    useEffect() {}, useLayoutEffect() {}, useSyncExternalStore: (_, snapshot) => snapshot()
  };
  function load(name) {
    let result;
    vm.runInNewContext(readFileSync(new URL(`../plugins/${name}/lib/client.js`, import.meta.url), 'utf8'), {
      window: { __ModuleLoader__: { load: ({ factory }) => { result = factory(id => { assert.equal(id, 'react'); return react; }); } } }
    });
    return result;
  }
  const badge = load('dsh-model-version-badge');
  const ultra = load('dsh-ultra-effort');
  let component, registration;
  const core = SlotCore ? new SlotCore() : null;
  if (core) {
    core.register({ name: 'root', children: { 'conversation.input.model': { kind: 'single', scope: 'session' } } }, () => null);
    core.register({ name: 'conversation.input.model', children: { 'conversation.input.model.label': { kind: 'single', scope: 'session', inline: true } } }, () => null);
    core.register({ name: 'conversation.input.model.label' }, () => 'official');
  }
  const slots = {
    inject: (key, fn) => { if (!core || core.specDynamic(key)) return fn(); return core.subscribeDeclaration(key, () => { if (core.specDynamic(key)) fn(); }); },
    register: (options, fn) => {
      if (options.name === 'conversation.input.model') { registration = options; component = fn; }
      return core?.register(options, fn);
    }
  };
  if (core && badgeEnabled) badge.apply({ slots });
  ultra.apply({ effect() {}, sessions: { subagentAddress: () => undefined }, modelDirectories: { directoryFor: () => ({ store: { getSnapshot: () => ({ groups, current, status: 'ready', error: null }) } }) },
    slots
  });
  const calls = [];
  const render = () => { cursor = 0; calls.length = 0; return component({ sessionId: 'test', locked: false, renderSlot(name, props, options) {
    assert.equal(name, 'juzi.ultra.model.label'); calls.push(props);
    if (core) {
      const label = core.entries(name)[0];
      return label ? label.component(props) : options.fallback;
    }
    return badgeEnabled ? badge.ModelVersionBadge(props) : options.fallback;
  } }); };
  return { render, calls, registration, core };
}
function nodes(tree) { return tree && typeof tree === 'object' ? [tree, ...(tree.children ?? []).flatMap(nodes)] : []; }
function text(tree) { return typeof tree === 'string' ? tree : (tree?.children ?? []).map(text).join(''); }
const model = { id: 'deepseek-flash', name: 'DeepSeek-V4.1-Flash' };
const groups = [{ id: 'deepseek-official', name: 'DeepSeek', models: [model] }];
const current = { provider: groups[0].id, model: model.id };

test('Ultra declares label slot and renders badges in trigger, menu and options', () => {
  const h = harness(groups, current);
  assert.equal(h.registration.children['juzi.ultra.model.label'].kind, 'single');
  let tree = h.render();
  assert.match(text(tree), /1017/);
  nodes(tree).find(n => n.type === 'button' && n.props['aria-haspopup']).props.onClick({ detail: 1 });
  tree = h.render();
  nodes(tree).find(n => n.props['aria-haspopup'] === 'listbox').props.onClick({ detail: 1 });
  tree = h.render();
  assert.deepEqual(h.calls.map(c => c.placement), ['trigger', 'menu', 'option']);
  assert.ok(h.calls.every(c => c.selected === true && c.provider.id === current.provider));
  for (const cls of ['ue-triggerModel', 'ue-modelName', 'ue-rowName']) assert.match(text(nodes(tree).find(n => n.props.className === cls)), /1017/);
});
test('Ultra retains model names without a badge plugin and for unsupported providers', () => {
  assert.match(text(harness(groups, current, false).render()), /DeepSeek-V4.1-Flash/);
  const foreign = [{ ...groups[0], id: 'other' }];
  assert.doesNotMatch(text(harness(foreign, { ...current, provider: 'other' }).render()), /1017/);
});
test('empty model directory renders fallback without calling label slot', () => {
  const h = harness([], null); h.render(); assert.equal(h.calls.length, 0);
});

test('real DSH registry elects Ultra while both label slots coexist', { skip: !SlotCore }, () => {
  const h = harness(groups, current);
  assert.equal(h.core.entries('conversation.input.model')[0].options.priority, -1);
  assert.equal(h.core.entries('conversation.input.model.label')[0].options.priority, -1);
  assert.equal(h.core.entries('juzi.ultra.model.label').length, 1);
});

test('Ultra retains max-effort slider and particle animation elements alongside badge', () => {
  const m = { ...model, reasoning: { defaultEffort: 'high', efforts: [{ id: 'high', name: 'High' }, { id: 'max', name: 'Max' }] } };
  const h = harness([{ ...groups[0], models: [m] }], { ...current, reasoningEffort: 'max' });
  let tree = h.render();
  nodes(tree).find(n => n.props['aria-haspopup'] === 'dialog').props.onClick({ detail: 1 });
  tree = h.render();
  assert.match(text(tree), /1017/);
  assert.ok(nodes(tree).some(n => n.props.role === 'slider' && n.props.className.includes('ue-trackMax')));
  assert.equal(nodes(tree).find(n => n.props.className === 'ue-stream').children.length, 14);
});
