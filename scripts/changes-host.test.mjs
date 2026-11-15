import test from 'node:test';
import assert from 'node:assert/strict';
import { rm, writeFile } from 'node:fs/promises';
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

test('fs/delete-intent captures pre-delete snapshots for ignored, out-of-workspace, and non-Git files', async t => {
  const { cwd } = await workspace(t);
  const nonGit = await workspace(t, { repository: false });
  const ignoredPath = join(cwd, 'ignored.txt');
  const outsidePath = join(nonGit.cwd, 'outside-delete.txt');
  const nonGitPath = join(nonGit.cwd, 'local-remove.txt');
  await writeFile(ignoredPath, 'ignored line 1\nignored line 2\n');
  await writeFile(outsidePath, 'outside before remove\n');
  await writeFile(nonGitPath, 'non-git before remove\n');

  const runtime = host(); t.after(() => runtime.dispose());
  const session = { id: 'delete-intent-git', header: { cwd } };
  await runtime.emit('session/event', session, { type: 'turn/start', data: { turn: 1 } });
  const exec = { agent: { session } };
  await runtime.emit('tools/pre-execute', exec, () => {});
  await runtime.emit('fs/delete-intent', ignoredPath, exec, async () => ({ path: ignoredPath }));
  await rm(ignoredPath);
  await runtime.emit('fs/delete-intent', outsidePath, exec, async () => ({ path: outsidePath }));
  await rm(outsidePath);
  await runtime.emit('session/event', session, { type: 'turn/end', data: { turn: 1 } });

  const gitSummary = await (await runtime.request('turn', { sessionId: session.id, turn: '1' })).json();
  assert.equal(gitSummary.status, 'finished');
  assert.equal(gitSummary.total, 2);
  const ignoredEntry = gitSummary.files.find(file => file.display === 'ignored.txt');
  const outsideEntry = gitSummary.files.find(file => file.path === outsidePath);
  assert.ok(ignoredEntry);
  assert.equal(ignoredEntry.status, 'deleted');
  assert.equal(ignoredEntry.added, 0);
  assert.equal(ignoredEntry.deleted, 2);
  const ignoredDiff = await (await runtime.request('diff', {
    sessionId: session.id, turn: '1', file: ignoredEntry.id, revision: String(gitSummary.revision),
  })).json();
  assert.deepEqual(ignoredDiff.hunks[0].lines, ['-ignored line 1', '-ignored line 2']);
  assert.ok(outsideEntry);
  assert.equal(outsideEntry.status, 'deleted');
  assert.equal(outsideEntry.deleted, 1);

  const plainSession = { id: 'delete-intent-nongit', header: { cwd: nonGit.cwd } };
  await runtime.emit('session/event', plainSession, { type: 'turn/start', data: { turn: 1 } });
  const plainExec = { agent: { session: plainSession } };
  await runtime.emit('tools/pre-execute', plainExec, () => {});
  await runtime.emit('fs/delete-intent', nonGitPath, plainExec, async () => ({ path: nonGitPath }));
  await rm(nonGitPath);
  await runtime.emit('session/event', plainSession, { type: 'turn/end', data: { turn: 1 } });

  const plainSummary = await (await runtime.request('turn', { sessionId: plainSession.id, turn: '1' })).json();
  assert.equal(plainSummary.status, 'finished');
  assert.equal(plainSummary.total, 1);
  assert.equal(plainSummary.files[0].display, 'local-remove.txt');
  assert.equal(plainSummary.files[0].status, 'deleted');
  assert.equal(plainSummary.files[0].deleted, 1);
  const plainDiff = await (await runtime.request('diff', {
    sessionId: plainSession.id, turn: '1', file: plainSummary.files[0].id, revision: String(plainSummary.revision),
  })).json();
  assert.deepEqual(plainDiff.hunks[0].lines, ['-non-git before remove']);
  assert.equal(runtime.warnings.length, 0, runtime.warnings.join('\n'));
});

test('subagent Sessions are not recorded standalone, while subagent tool writes/deletes capture into the active parent turn', async t => {
  const { cwd } = await workspace(t);
  const outside = await workspace(t, { repository: false });
  const ignoredPath = join(cwd, 'ignored.txt');
  const removedOutside = join(outside.cwd, 'subagent-removed.txt');
  const managedOutside = join(outside.cwd, 'managed-created.txt');
  const headerOutside = join(outside.cwd, 'header-created.txt');
  const postTurnOutside = join(outside.cwd, 'post-turn.txt');
  await writeFile(ignoredPath, 'original ignored\n');
  await writeFile(removedOutside, 'to be removed by subagent\n');

  const parentSession = { id: 'parent-session', header: { cwd } };
  const rootAgent = { session: parentSession };
  let managedAgent;
  const runtime = host({}, undefined, {
    subagents: {
      rootOf(agent) {
        if (agent === managedAgent) return rootAgent;
        const error = new Error('not a managed subagent');
        error.code = 'UNAUTHORIZED';
        throw error;
      },
    },
  });
  t.after(() => runtime.dispose());

  const child1 = { id: 'child-1', header: { cwd, origin: 'subagent', delegationDepth: 1 } };
  const child2 = { id: 'child-2', header: { cwd, origin: 'subagent', delegationDepth: 2 } };
  await runtime.emit('session/event', child1, { type: 'turn/start', data: { turn: 1 } });
  await runtime.emit('session/event', child2, { type: 'turn/start', data: { turn: 1 } });
  assert.deepEqual((await (await runtime.request('list', { sessionId: child1.id })).json()).turns, []);
  assert.deepEqual((await (await runtime.request('list', { sessionId: child2.id })).json()).turns, []);

  await runtime.emit('session/event', parentSession, { type: 'turn/start', data: { turn: 1 } });

  // 1) Nested ownerAgent chain (depth 2 -> depth 1 -> parent rootAgent)
  const ownerExec = { agent: { session: child2, ownerAgent: { session: child1, ownerAgent: rootAgent } } };
  await runtime.emit('tools/pre-execute', ownerExec, () => {});
  await runtime.emit('fs/edit-intent', ignoredPath, ownerExec, async () => ({ path: ignoredPath }));
  await writeFile(ignoredPath, 'updated by nested subagent\n');
  await runtime.emit('fs/delete-intent', removedOutside, ownerExec, async () => ({ path: removedOutside }));
  await rm(removedOutside);

  // 2) DSH 0.2.2-rc.3 subagents.rootOf(agent) without ownerAgent property
  const managedSession = { id: 'child-managed', header: { cwd, origin: 'subagent', delegationDepth: 1 } };
  managedAgent = { session: managedSession };
  const managedExec = { agent: managedAgent };
  await runtime.emit('tools/pre-execute', managedExec, () => {});
  await runtime.emit('fs/write-intent', managedOutside, managedExec, async () => ({ path: managedOutside }));
  await writeFile(managedOutside, 'created via subagents.rootOf\n');

  // 3) Subagent header parentSession lineage + live tool/result dirty notification
  const headerSession = { id: 'child-header', header: { cwd, origin: 'subagent', delegationDepth: 1, parentSession: parentSession.id } };
  const headerExec = { agent: { session: headerSession } };
  await runtime.emit('tools/pre-execute', headerExec, () => {});
  await runtime.emit('fs/write-intent', headerOutside, headerExec, async () => ({ path: headerOutside }));
  await writeFile(headerOutside, 'created via parentSession header\n');
  await runtime.emit('session/event', headerSession, { type: 'tool/result', data: { turn: 1 } });

  // 4) Ordinary user-forked top-level session with parentSession must NOT leak into parentSession unless running its own turn
  const forkedTopSession = { id: 'forked-user-session', header: { cwd: outside.cwd, parentSession: parentSession.id } };
  const forkedExec = { agent: { session: forkedTopSession } };
  await runtime.emit('tools/pre-execute', forkedExec, () => {});
  const forkUntracked = join(outside.cwd, 'fork-isolated.txt');
  await runtime.emit('fs/write-intent', forkUntracked, forkedExec, async () => ({ path: forkUntracked }));
  await writeFile(forkUntracked, 'isolated from parent\n');

  await runtime.emit('session/event', parentSession, { type: 'turn/end', data: { turn: 1 } });
  const summary = await (await runtime.request('turn', { sessionId: parentSession.id, turn: '1' })).json();
  assert.equal(summary.status, 'finished');
  assert.equal(summary.total, 4);
  const byPath = new Map(summary.files.map(file => [file.path, file]));
  assert.equal(byPath.get('ignored.txt')?.status, 'modified');
  assert.equal(byPath.get(removedOutside)?.status, 'deleted');
  assert.equal(byPath.get(managedOutside)?.status, 'added');
  assert.equal(byPath.get(headerOutside)?.status, 'added');
  assert.equal(byPath.has(forkUntracked), false);

  // 5) Subagent executing after parent turn finished must not mutate finished turn 1
  const lateExec = { agent: { session: child1, ownerAgent: rootAgent } };
  await runtime.emit('tools/pre-execute', lateExec, () => {});
  await runtime.emit('fs/write-intent', postTurnOutside, lateExec, async () => ({ path: postTurnOutside }));
  await writeFile(postTurnOutside, 'after parent turn ended\n');
  const afterLate = await (await runtime.request('turn', { sessionId: parentSession.id, turn: '1', refresh: '1' })).json();
  assert.equal(afterLate.status, 'finished');
  assert.equal(afterLate.total, 4);
  assert.equal(runtime.warnings.length, 0, runtime.warnings.join('\n'));
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
