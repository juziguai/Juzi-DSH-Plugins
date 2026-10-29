export const STORAGE_KEY = 'juzi.layout-memory.v1';
const owners = new WeakMap();
const width = value => typeof value === 'number' && Number.isFinite(value) && value > 0;
const fault = code => Object.assign(new Error(code), { code });
const sidebarWidth = px => Math.min(420, Math.max(264, Math.round(px)));
const rightbarWidth = (px, viewport) => Math.min(Math.max(300, viewport * .7), Math.max(300, Math.round(px)));

function snapshot(store) {
  const state = store.getSnapshot()?.layoutInfo;
  if (!state || !Number.isFinite(state.sidebar) || state.sidebar < 0
    || !(state.rightbar === null || width(state.rightbar)) || !width(state.viewportWidth)
    || ['narrowExpanded', 'rightbarShown', 'rightbarTrack', 'rightbarFullscreen'].some(key => typeof state[key] !== 'boolean')) throw fault('incompatible');
  return { ...state };
}

function preferences(storage) {
  let raw;
  try { raw = storage.getItem(STORAGE_KEY); } catch { throw fault('storage'); }
  if (raw === null) return {};
  let value;
  try { value = JSON.parse(raw); } catch { throw fault('invalid-record'); }
  if (!value || value.version !== 1 || Array.isArray(value)
    || ['sidebar', 'rightbar'].some(key => value[key] !== undefined && !width(value[key]))) throw fault('invalid-record');
  return { ...(value.sidebar === undefined ? {} : { sidebar: value.sidebar }), ...(value.rightbar === undefined ? {} : { rightbar: value.rightbar }) };
}

function remember(store, { storage, events, warn, timers, delay }) {
  let previous = snapshot(store);
  const preferred = preferences(storage);
  let dirty = false, timer, restoring = false, stopped = false, off;

  function flush() {
    timers.clearTimeout(timer); timer = undefined;
    if (stopped || !dirty) return;
    try { storage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, ...preferred })); dirty = false; }
    catch { warn('storage'); stop(false); }
  }
  function changed() {
    dirty = true; timers.clearTimeout(timer); timer = timers.setTimeout(flush, delay);
  }
  function restore(info) {
    restoring = true;
    try {
      // A zero sidebar is a visibility choice, not a width preference.
      if (preferred.sidebar !== undefined && info.sidebar > 0) {
        const px = sidebarWidth(preferred.sidebar);
        if (info.sidebar !== px) store.actions.setSidebar(px);
      }
      if (preferred.rightbar !== undefined && !info.rightbarFullscreen) {
        const px = rightbarWidth(preferred.rightbar, info.viewportWidth);
        if (info.rightbar !== px) store.actions.setRightbar(px);
      }
      previous = snapshot(store);
    } finally { restoring = false; }
  }
  function observe() {
    if (stopped || restoring) return;
    try {
      const next = snapshot(store);
      const resized = next.viewportWidth !== previous.viewportWidth;
      if (!resized) {
        if (next.sidebar !== previous.sidebar && next.sidebar > 0 && previous.sidebar > 0
          && (next.viewportWidth >= 1024 || next.narrowExpanded) && preferred.sidebar !== next.sidebar) {
          preferred.sidebar = next.sidebar; changed();
        }
        if (next.rightbar !== previous.rightbar && next.rightbarShown && next.rightbarTrack
          && !next.rightbarFullscreen && !previous.rightbarFullscreen && preferred.rightbar !== next.rightbar) {
          preferred.rightbar = next.rightbar; changed();
        }
      }
      // Reopening the sidebar must restore its width without saving the Host's reset-to-280 value.
      if (preferred.sidebar === undefined && next.sidebar > 0) { preferred.sidebar = next.sidebar; changed(); }
      if (preferred.rightbar === undefined && width(next.rightbar)) { preferred.rightbar = next.rightbar; changed(); }
      restore(next);
    } catch (error) { warn(error.code ?? 'incompatible'); stop(false); }
  }
  function stop(save = true) {
    if (stopped) return;
    if (save) flush();
    if (stopped) return;
    stopped = true; timers.clearTimeout(timer); off?.(); events.removeEventListener('pagehide', flush);
  }

  // Install after the user has adjusted a layout: that current preference is the initial record.
  if (preferred.sidebar === undefined && previous.sidebar > 0) { preferred.sidebar = previous.sidebar; dirty = true; }
  if (preferred.rightbar === undefined && width(previous.rightbar)) { preferred.rightbar = previous.rightbar; dirty = true; }
  restore(previous);
  off = store.subscribe(observe);
  if (typeof off !== 'function') throw fault('incompatible');
  events.addEventListener('pagehide', flush);
  if (dirty) changed();
  return stop;
}

/** Bind only the rendered root's shared Store; never create a detached layout or replace its component. */
export function attachLayoutMemory({ slots, storage, events, warn = () => {}, timers = globalThis, delay = 200 }) {
  const warned = new Set();
  const report = code => { if (!warned.has(code)) { warned.add(code); warn(code); } };
  let entry, release, disposed = false;
  if (typeof slots?.entries !== 'function' || typeof slots.subscribe !== 'function') { report('incompatible'); return () => {}; }
  function bind() {
    if (disposed) return;
    try {
      const next = slots.entries('root')[0];
      if (next === entry) return;
      release?.(); release = undefined; entry = next;
      if (!entry) return;
      const handle = entry.store;
      if (typeof handle?.create !== 'function') throw fault('incompatible');
      const store = handle.create();
      if (store !== handle.create() || typeof store?.getSnapshot !== 'function' || typeof store.subscribe !== 'function'
        || typeof store.actions?.setSidebar !== 'function' || typeof store.actions?.setRightbar !== 'function') throw fault('incompatible');
      let owner = owners.get(store);
      if (!owner) {
        owner = { users: 0, stop: remember(store, { storage, events, warn: report, timers, delay }) };
        owners.set(store, owner);
      }
      owner.users++;
      release = () => { if (--owner.users === 0) { owner.stop(); owners.delete(store); } };
    } catch (error) { report(error.code ?? 'incompatible'); }
  }
  const off = slots.subscribe('root', bind);
  bind();
  return () => {
    if (disposed) return;
    disposed = true; off(); release?.(); release = undefined;
  };
}
