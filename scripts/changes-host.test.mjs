import test from 'node:test';
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { host } from '../plugins/dsh-changes/test/host.mjs';
import { workspace } from '../plugins/dsh-changes/test/helpers.mjs';
import * as pluginModule from '../plugins/dsh-changes/lib/index.js';

test('host barriers capture before a tool, serve revisions, isolate Sessions, and keep history until unload', async t => {
  const { cwd } = await workspace(t);
  const runtime = host(); t.after(() => runtime.dispose());
  const session = { id: 'session-A', header: { cwd } };
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  const exec = { agent: { session } };
  let toolEntered = false;
  await runtime.emit('tools/pre-execute', exec, () => { toolEntered = true; });
  assert.equal(toolEntered, true);
  await runtime.emit('fs/edit-intent', join(cwd, 'ignored.txt'), exec, async () => ({ allowed: true }));
  await writeFile(join(cwd, 'ignored.txt'), 'new ignored content\n');
  await runtime.emit('session/event', session, { type: 'tool/result', data: { turn: 1 } });
  const response = await runtime.request('turn', { sessionId: session.id, turn: '1', refresh: '1' });
  assert.equal(response.headers.get('cache-control'), 'no-store');
  const summary = await response.json();
  assert.equal(summary.files[0].display, 'ignored.txt');
  const diff = await runtime.request('diff', { sessionId: session.id, turn: '1', file: summary.files[0].id, revision: String(summary.revision) });
  assert.equal(diff.status, 200); assert.equal((await diff.json()).kind, 'text');
  assert.equal((await runtime.request('diff', { sessionId: session.id, turn: '1', file: '../../secret', revision: String(summary.revision) })).status, 404);
  assert.equal((await runtime.request('diff', { sessionId: session.id, turn: '1', file: summary.files[0].id, revision: '0' })).status, 409);
  assert.equal((await runtime.request('turn', { sessionId: 'session-B', turn: '1' })).status, 404);
  await runtime.emit('session/event', session, { type: 'workspace/changes', seq: 100, data: { turn: 1 } });
  await runtime.emit('session/event', session, { type: 'turn/end', data: { turn: 1 } });
  // The event enqueues completion; a later turn's barrier waits for it.
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 2 } });
  await runtime.emit('tools/pre-execute', { agent: { session } }, () => {});
  const previous = await (await runtime.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(previous.status, 'finished');
  assert.equal((await (await runtime.request('turn', { sessionId: session.id, turn: '2' })).json()).total, 0);
  await runtime.emit('session/disposed', session);
  const list = await (await runtime.request('list', { sessionId: session.id })).json();
  assert.equal(list.turns.length, 2);
  assert.ok(list.turns.every(turn => turn.officialSeq === null));
  assert.equal((await runtime.request('list', {})).status, 400);
  assert.equal(runtime.warnings.length, 0, runtime.warnings.join('\n'));
});

test('subagent Sessions are not silently recorded as top-level work', async t => {
  const { cwd } = await workspace(t);
  const runtime = host(); t.after(() => runtime.dispose());
  const session = { id: 'child', header: { cwd, origin: 'subagent' } };
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  assert.deepEqual((await (await runtime.request('list', { sessionId: 'child' })).json()).turns, []);
});

test('recording failures stay observable without preventing Agent tools from running', async t => {
  const { cwd } = await workspace(t);
  const runtime = host({}, async () => ({ code: 1, stdout: '', stderr: 'unavailable' }));
  t.after(() => runtime.dispose());
  const session = { id: 'error-session', header: { cwd } };
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  let entered = false;
  await runtime.emit('tools/pre-execute', { agent: { session } }, () => { entered = true; });
  assert.equal(entered, true);
  const summary = await (await runtime.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(summary.status, 'error'); assert.match(summary.error, /Git exit/);
  assert.ok(runtime.warnings.length);
});

test('failure to capture original bytes invalidates that turn instead of fabricating an added file', async t => {
  const { cwd } = await workspace(t);
  const runtime = host(); t.after(() => runtime.dispose());
  const session = { id: 'capture-failure', header: { cwd } }, exec = { agent: null };
  exec.agent = { session };
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  await runtime.emit('tools/pre-execute', exec, () => {});
  runtime.context.fs.processPath = () => { throw new Error('capture denied'); };
  await runtime.emit('fs/edit-intent', 'ignored.txt', exec, () => ({ allowed: true }));
  await writeFile(join(cwd, 'ignored.txt'), 'tool may continue\n');
  await runtime.emit('session/event', session, { type: 'turn/end', data: { turn: 1 } });
  const summary = await (await runtime.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(summary.status, 'error'); assert.match(summary.error, /capture denied/);
  assert.equal(summary.total, 0);
});

test('browser registers its own tab and header entries against the real SlotCore', { skip: !process.env.DSH_SLOT_CORE_MODULE }, async () => {
  const { SlotCore } = await import(pathToFileURL(process.env.DSH_SLOT_CORE_MODULE));
  const core = new SlotCore();
  core.register({ name: 'root', children: {
    'sidebar.right.pane.tab': { kind: 'keyed', scope: 'session' },
    'sidebar.right.pane.tab.title': { kind: 'keyed', scope: 'session' },
    'conversation.session.header.utilities': { kind: 'list', scope: 'session' },
  } }, () => null);
  let plugin, definition;
  vm.runInNewContext(readFileSync(new URL('../plugins/dsh-changes/lib/client.js', import.meta.url), 'utf8'), {
    window: { __ModuleLoader__: { load: ({ factory }) => { plugin = factory(() => ({ createElement() {} })); } } },
  });
  plugin.apply({ effect() {}, on() {}, sidebarRight: {}, sidebarRightTabs: { register: value => { definition = value; } },
    slots: { inject: (_, fn) => fn(), register: (options, body) => core.register(options, body) } });
  // effect() intentionally doesn't execute document/CSS work; tab type registration is tested in the browser smoke.
  assert.equal(core.entries('sidebar.right.pane.tab')[0].options.key, '@juzi/dsh-changes');
  assert.equal(core.entries('sidebar.right.pane.tab.title')[0].options.key, '@juzi/dsh-changes');
  assert.equal(core.entries('conversation.session.header.utilities')[0].options.id, '@juzi/dsh-changes');
  assert.equal(core.specDynamic('juzi.ultra.model.label'), undefined);
  assert.equal(definition, undefined);
});

test('actual Cordis activates the Host plugin through its declared services and releases it', { skip: !process.env.DSH_CORDIS_MODULE }, async t => {
  const { Context } = await import(pathToFileURL(process.env.DSH_CORDIS_MODULE));
  const { cwd } = await workspace(t), adapter = host(), ctx = new Context();
  t.after(async () => { await ctx.fiber.dispose(); await adapter.dispose(); });
  await ctx.plugin({ name: 'isolated-capabilities', apply(scope) {
    for (const key of ['subprocess', 'fs', 'connection']) scope.provide(key, adapter.context[key]);
  } });
  await ctx.plugin(pluginModule, { refreshMs: 250 });
  const session = { id: 'actual-cordis-session', header: { cwd } };
  ctx.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  const initial = await (await adapter.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(initial.status, 'running', JSON.stringify(initial));
  await writeFile(join(cwd, 'file.txt'), 'through real Cordis\n');
  ctx.emit('session/event', session, { type: 'turn/end', data: { turn: 1 } });
  const final = await (await adapter.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(final.status, 'finished'); assert.equal(final.total, 1);
});
