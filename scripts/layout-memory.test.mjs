import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import vm from 'node:vm';
import { attachLayoutMemory, STORAGE_KEY } from '../plugins/dsh-layout-memory/lib/memory.js';

function storage(initial) {
  const rows = new Map([['unrelated', 'keep'], ...(initial === undefined ? [] : [[STORAGE_KEY, typeof initial === 'string' ? initial : JSON.stringify(initial)]])]);
  let writes = 0;
  return { rows, get writes() { return writes; }, getItem: key => rows.get(key) ?? null, setItem(key, value) { writes++; rows.set(key, value); } };
}
function store(overrides = {}) {
  let state = { layoutInfo: { sidebar: 280, rightbar: null, viewportWidth: 1600, narrowExpanded: false, rightbarShown: false, rightbarTrack: false, rightbarFullscreen: false, rightbarInstant: false, ...overrides } };
  const listeners = new Set(), calls = [];
  const change = patch => { state = { ...state, layoutInfo: { ...state.layoutInfo, ...patch } }; for (const fn of [...listeners]) fn(); };
  return {
    calls, change, get subscriptions() { return listeners.size; }, getSnapshot: () => state,
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    actions: {
      setSidebar(px) { calls.push(['sidebar', px]); change({ sidebar: Math.min(420, Math.max(264, Math.round(px))), rightbarInstant: false }); },
      setRightbar(px) { calls.push(['rightbar', px]); change({ rightbar: Math.min(Math.max(300, state.layoutInfo.viewportWidth * .7), Math.max(300, Math.round(px))), rightbarInstant: false }); },
    },
  };
}
function slots(initial) {
  let entry = initial && { store: { create: () => initial } };
  const listeners = new Set();
  return {
    get subscriptions() { return listeners.size; }, entries: () => entry ? [entry] : [],
    subscribe(_name, fn) { listeners.add(fn); return () => listeners.delete(fn); },
    replace(next) { entry = next && { store: { create: () => next } }; for (const fn of [...listeners]) fn(); },
  };
}
function bind(t, current, saved = storage(), registry = slots(current)) {
  const events = new EventTarget(), warnings = [];
  const stop = attachLayoutMemory({ slots: registry, storage: saved, events, warn: code => warnings.push(code) });
  t.after(stop);
  return { stop, saved, registry, events, warnings, info: () => current.getSnapshot().layoutInfo };
}
const visible = { rightbar: 420, rightbarShown: true, rightbarTrack: true };

test('widths survive a genuinely fresh layout and preserve panel visibility and unrelated storage', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const saved = storage(), first = store(visible), a = bind(t, first, saved);
  first.actions.setSidebar(370); first.actions.setRightbar(510); a.events.dispatchEvent(new Event('pagehide'));
  a.stop(); assert.equal(first.subscriptions, 0);
  const second = store(), b = bind(t, second, saved);
  assert.equal(b.info().sidebar, 370); assert.equal(b.info().rightbar, 510);
  assert.equal(b.info().rightbarShown, false); assert.equal(b.info().rightbarTrack, false);
  assert.equal(saved.getItem('unrelated'), 'keep');
  assert.equal(saved.writes, 1); t.mock.timers.tick(500); assert.equal(saved.writes, 1);
});

test('first activation captures an already-adjusted layout; writes are coalesced and flushed on disposal', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const current = store({ ...visible, sidebar: 340, rightbar: 470 }), b = bind(t, current);
  for (let i = 0; i < 30; i++) current.actions.setRightbar(470 + i);
  assert.equal(b.saved.writes, 0); t.mock.timers.tick(199); assert.equal(b.saved.writes, 0);
  t.mock.timers.tick(1); assert.equal(b.saved.writes, 1);
  assert.equal(JSON.parse(b.saved.getItem(STORAGE_KEY)).rightbar, 499);
  current.actions.setRightbar(530); b.stop(); assert.equal(b.saved.writes, 2);
  t.mock.timers.tick(500); assert.equal(b.saved.writes, 2);
});

test('collapse, hidden panels and fullscreen never replace remembered widths or force panels open', t => {
  const saved = storage({ version: 1, sidebar: 370, rightbar: 520 }), current = store(visible), b = bind(t, current, saved);
  current.change({ sidebar: 0 }); assert.equal(b.info().sidebar, 0);
  current.change({ sidebar: 280 }); assert.equal(b.info().sidebar, 370);
  current.change({ rightbarShown: false, rightbarTrack: false });
  current.actions.setRightbar(700); assert.equal(b.info().rightbarShown, false); assert.equal(b.info().rightbar, 520);
  current.change({ rightbarFullscreen: true }); current.actions.setRightbar(900);
  assert.equal(b.info().rightbar, 900);
  current.change({ rightbarFullscreen: false }); assert.equal(b.info().rightbar, 520);
  b.events.dispatchEvent(new Event('pagehide')); assert.equal(saved.writes, 0);
});

test('temporary viewport clamps do not overwrite preferences and expansion restores their original size', t => {
  const saved = storage({ version: 1, sidebar: 390, rightbar: 800 }), current = store({ ...visible, viewportWidth: 600, narrowExpanded: false }), b = bind(t, current, saved);
  assert.equal(b.info().rightbar, 420); assert.equal(b.info().narrowExpanded, false);
  current.change({ viewportWidth: 400 }); assert.equal(b.info().rightbar, 300);
  current.change({ viewportWidth: 1800 }); assert.equal(b.info().rightbar, 800);
  assert.equal(b.info().sidebar, 390); assert.equal(saved.writes, 0);
});

test('invalid or inaccessible records leave native state untouched and warn only once', t => {
  for (const raw of ['{', { version: 2, sidebar: 300 }, { version: 1, rightbar: '500' }, { version: 1, sidebar: -1 }, '{"version":1,"rightbar":1e309}']) {
    const current = store(visible), saved = storage(raw), b = bind(t, current, saved);
    assert.equal(b.info().rightbar, 420); assert.equal(current.subscriptions, 0);
    assert.deepEqual(b.warnings, ['invalid-record']); assert.equal(saved.writes, 0);
    b.registry.replace(current); assert.deepEqual(b.warnings, ['invalid-record']);
  }
  const current = store(), b = bind(t, current, { getItem() { throw Error('denied'); } });
  assert.deepEqual(b.warnings, ['storage']); assert.equal(current.subscriptions, 0);
});

test('quota failure stops the controller without repeated writes or leaking subscriptions', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const saved = storage(), current = store(visible); let attempts = 0;
  saved.setItem = () => { attempts++; throw Error('quota'); };
  const b = bind(t, current, saved); t.mock.timers.tick(200);
  assert.equal(current.subscriptions, 0); assert.deepEqual(b.warnings, ['storage']);
  current.actions.setRightbar(550); b.events.dispatchEvent(new Event('pagehide')); b.stop();
  assert.equal(attempts, 1);
});

test('late root registration, root replacement and repeated activation release all listeners', t => {
  const saved = storage({ version: 1, sidebar: 360, rightbar: 500 }), registry = slots();
  for (let i = 0; i < 3; i++) {
    const first = store(), b = bind(t, first, saved, registry); registry.replace(first);
    assert.equal(first.subscriptions, 1); assert.equal(first.getSnapshot().layoutInfo.rightbar, 500);
    const next = store(); registry.replace(next); assert.equal(first.subscriptions, 0);
    assert.equal(next.getSnapshot().layoutInfo.sidebar, 360); assert.equal(next.subscriptions, 1);
    b.stop(); b.stop(); assert.equal(next.subscriptions, 0); assert.equal(registry.subscriptions, 0);
    registry.replace(undefined);
  }
});

test('duplicate activations share one width observer and do not reset or double-save preferences', t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const current = store(visible), saved = storage(), registry = slots(current);
  const a = bind(t, current, saved, registry), b = bind(t, current, saved, registry);
  assert.equal(current.subscriptions, 1); current.actions.setRightbar(550); t.mock.timers.tick(200);
  assert.equal(saved.writes, 1); a.stop(); assert.equal(current.subscriptions, 1);
  b.stop(); assert.equal(current.subscriptions, 0); assert.equal(registry.subscriptions, 0);
});

test('unexpected root contract fails closed, including a factory that creates detached stores', t => {
  const current = store(), registry = slots(); registry.entries = () => [{ store: { create: () => store() } }];
  const b = bind(t, current, storage(), registry);
  assert.deepEqual(b.warnings, ['incompatible']); assert.equal(current.subscriptions, 0);
});

test('official SlotCore exposes the root lifetime and Store handle used by the adapter', { skip: !process.env.DSH_SLOT_CORE_MODULE }, async t => {
  const { SlotCore } = await import(pathToFileURL(resolve(process.env.DSH_SLOT_CORE_MODULE)));
  const core = new SlotCore(), current = store(), saved = storage({ version: 1, rightbar: 460 });
  const stop = attachLayoutMemory({ slots: core, storage: saved, events: new EventTarget() }); t.after(stop);
  const unregister = core.register({ name: 'root', store: { create: () => current } }, () => null);
  await new Promise(resolve => setImmediate(resolve)); assert.equal(current.getSnapshot().layoutInfo.rightbar, 460);
  unregister(); await new Promise(resolve => setImmediate(resolve)); assert.equal(current.subscriptions, 0);
});

test('current installed frontend Store and SlotCore restore widths on a new actual LayoutStore', {
  skip: !process.env.DSH_LAYOUT_SHARES_MODULE || !process.env.DSH_LAYOUT_SOURCE_FILE || !process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR,
}, async t => {
  const require = createRequire(pathToFileURL(resolve(process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR))), { JSDOM } = require('jsdom');
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', { url: 'http://fixture.invalid' });
  const prior = { window: globalThis.window, document: globalThis.document, MutationObserver: globalThis.MutationObserver };
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, MutationObserver: dom.window.MutationObserver });
  t.after(() => { dom.window.close(); Object.assign(globalThis, prior); });
  const shares = await import(pathToFileURL(resolve(process.env.DSH_LAYOUT_SHARES_MODULE)));
  const source = readFileSync(process.env.DSH_LAYOUT_SOURCE_FILE, 'utf8'), start = source.indexOf('function createLayoutStore()'), end = source.indexOf('\n\t\t//#endregion', start);
  assert(start >= 0 && end > start);
  const create = () => vm.runInNewContext(`(${source.slice(start, end)})().create()`, {
    window: { innerWidth: 1600 }, _deepseek_ai_dsh_client_store: shares.store,
    RIGHTBAR_DEFAULT_RATIO: .45, RIGHTBAR_MAX_RATIO: .7, clampWidth: (value, min, max) => Math.min(max, Math.max(min, Math.round(value))),
  });
  const saved = storage(), core = new shares.slots.SlotCore(), first = create();
  first.actions.openRightbar(true, false); first.actions.setSidebar(355); first.actions.setRightbar(465);
  let unmount = core.register({ name: 'root', store: { create: () => first } }, () => null);
  const stop = attachLayoutMemory({ slots: core, storage: saved, events: new EventTarget() }); t.after(stop);
  unmount(); await new Promise(resolve => setImmediate(resolve));
  const second = create(); unmount = core.register({ name: 'root', store: { create: () => second } }, () => null);
  await new Promise(resolve => setImmediate(resolve));
  const state = second.getSnapshot().layoutInfo;
  assert.equal(state.sidebar, 355); assert.equal(state.rightbar, 465); assert.equal(state.rightbarShown, false);
  second.actions.openRightbar(true, false); assert.equal(second.getSnapshot().layoutInfo.rightbar, 465);
  unmount(); await new Promise(resolve => setImmediate(resolve));
});
