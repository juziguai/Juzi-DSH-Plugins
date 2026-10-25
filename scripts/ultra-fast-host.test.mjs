import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { mkdtemp, writeFile, mkdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve, basename } from 'node:path';
import { FAST_POLICY } from '../plugins/dsh-ultra-effort/lib/fast-policy.js';

const anchor = process.env.DSH_FAST_RUNTIME_ANCHOR;
test('actual rc.3 Loader/Settings/Editor/Sessions/Prompt: persistence, live config, frozen policy and disposal', { skip: !anchor }, async t => {
  const require = createRequire(pathToFileURL(resolve(anchor)));
  const load = name => import(pathToFileURL(require.resolve('@deepseek-ai/' + name)));
  const [{ Context, Service }, { Loader }, { mountRootInclude, readProfilePatches }, { default: Settings }, { default: Editor },
    { default: Sessions }, { default: Prompt }, { SettingsController }] = await Promise.all([
    'cordis', 'cordis-plugin-loader', 'dsh-app-boot', 'dsh-settings', 'dsh-config-editor', 'dsh-session', 'dsh-system-prompt', 'dsh-api-settings-controller',
  ].map(load));
  const dir = await mkdtemp(join(tmpdir(), 'juzi-ultra-fast-'));
  t.after(async () => { assert.equal(dirname(dir), tmpdir()); assert(basename(dir).startsWith('juzi-ultra-fast-')); await rm(dir, { recursive: true }); });
  const manifest = join(dir, 'package.json'), patchPath = join(dir, 'cordis.patch.yml'), configPath = join(dir, 'cordis.yml');
  await mkdir(join(dir, 'home')); await writeFile(manifest, JSON.stringify({ name: 'ultra-fast-test', private: true }));
  await writeFile(configPath, '[]\n');
  await writeFile(patchPath, JSON.stringify([{ insert: [{ id: 'ui-ultra-effort', name: new URL('../plugins/dsh-ultra-effort/lib/index.js', import.meta.url).href }] }]));
  const profile = { dir, name: 'test', patchPath, home: join(dir, 'home'), installAnchor: manifest, cwd: dir, startedBundles: [], overlays: [] };
  async function boot() {
    const ctx = new Context(), routes = new Map();
    // Simulate only the HTTP transport, using the public caller-owned registration contract.
    class TestConnection extends Service {
      constructor(scope) { super(scope, 'connection'); }
      get fetch() {
        const owner = this.ctx;
        return { register(route) {
          assert.deepEqual(route.methods, ['GET']);
          return owner.effect(() => { assert(!routes.has(route.path)); routes.set(route.path, route); return () => routes.delete(route.path); });
        } };
      }
    }
    await ctx.plugin({ apply(scope) { scope.provide('profileContext', profile); } });
    await ctx.plugin(TestConnection);
    await ctx.plugin(Loader, { baseUrl: pathToFileURL(dir + '/').href });
    await mountRootInclude(ctx, configPath, readProfilePatches('dsh', profile)); await ctx.loader.await();
    // Ultra remains active before optional services arrive.
    assert.equal(ctx.loader.resolve('include:ui-ultra-effort').fiber.state, 2); assert.equal(routes.size, 0);
    await ctx.plugin(Editor); await ctx.plugin(Settings); await ctx.plugin(Sessions);
    await ctx.plugin(Prompt, { includeHarnessIdentity: false, includeRuntimeContext: false });
    await ctx.plugin(SettingsController);
    const row = () => ctx.settingsController.describe().namespaces.find(row => row.ns === 'ui-ultra-effort');
    const mutate = (id, value, revision = row().revision) => ctx.settingsController.mutate(row().ns, [{ op: 'set', path: ['fastSessions', id], value }], revision);
    const capability = async id => routes.get('/api/juzi.ultra.capabilities').fetch(new Request('http://localhost/api/juzi.ultra.capabilities?sessionId=' + id));
    return { ctx, routes, row, mutate, capability };
  }
  let h = await boot();
  try {
    assert.equal(h.row().autoGenerate, false); assert.deepEqual(h.row().value.fastSessions, {});
    const uid = h.ctx.loader.resolve('include:ui-ultra-effort').fiber.uid;
    const a = h.ctx.sessions.create('session-A'), b = h.ctx.sessions.create('session-B');
    const agent = { session: a }, other = { session: b };
    const policy = async (agent, scope = agent) => (await h.ctx.systemPrompt.assemble({ agent, scope })).sections.find(row => row.name === 'juzi-ultra:fast-execution')?.text ?? '';
    assert.equal(await policy(agent), ''); const revision = h.row().revision;
    await h.mutate(a.id, true, revision);
    assert.equal(h.ctx.loader.resolve('include:ui-ultra-effort').fiber.uid, uid);
    await assert.rejects(h.mutate(b.id, true, revision), { code: 'settings/conflict' });
    a.append('turn/start', { turn: 1 });
    assert.equal(await policy(agent), FAST_POLICY); assert.equal(await policy(other), ''); assert.equal(await policy(agent, other), '');
    assert.equal((await (await h.capability(a.id)).json()).idle, false);
    await h.mutate(a.id, false); assert.equal(await policy(agent), FAST_POLICY);
    h.ctx.emit('session/event', a, { type: 'turn/end', data: { turn: 1 } });
    assert.equal(await policy(agent), '');
    h.ctx.emit('session/event', a, { type: 'turn/start', data: { turn: 2 } });
    assert.equal(await policy(agent), '');
    await h.mutate(a.id, true); assert.equal(await policy(agent), '');
    h.ctx.emit('session/disposed', a); assert.equal(await policy(agent), '');
    const child = h.ctx.sessions.create('session-child', { meta: { origin: 'subagent', delegationDepth: 1 } });
    await h.mutate(child.id, true); child.append('turn/start', { turn: 1 });
    assert.equal(await policy({ session: child }), ''); assert.equal((await h.capability(child.id)).status, 404);
    assert.equal((await h.capability('missing')).status, 404);
    const cap = await h.capability(b.id); assert.equal(cap.headers.get('cache-control'), 'no-store');
    assert.deepEqual(await cap.json(), { protocol: 1, namespace: 'ui-ultra-effort', ready: true, writable: true, idle: true, boundary: 'next-turn' });
    await h.ctx.fiber.dispose(); assert.equal(h.routes.size, 0);
    h = await boot(); assert.equal(h.row().value.fastSessions[a.id], true);
    const resumed = h.ctx.sessions.create(a.id), resumedAgent = { session: resumed };
    resumed.append('turn/start', { turn: 1 });
    assert.equal((await h.ctx.systemPrompt.assemble({ agent: resumedAgent, scope: resumedAgent })).sections.find(row => row.name === 'juzi-ultra:fast-execution').text, FAST_POLICY);
    const fork = h.ctx.sessions.create('session-fork'); assert.equal(h.row().value.fastSessions[fork.id], undefined);
    assert.match(await readFile(patchPath, 'utf8'), /session-A/);
    // Reload/dispose removes the policy and route; the rest of the assembly survives.
    const unloaded = h.ctx.loader.resolve('include:ui-ultra-effort').fiber;
    h.ctx.loader.remove('include:ui-ultra-effort'); await unloaded.dispose(); await h.ctx.loader.await();
    assert.equal(h.routes.size, 0);
    assert.equal((await h.ctx.systemPrompt.assemble({ agent: resumedAgent, scope: resumedAgent })).sections.some(row => row.name === 'juzi-ultra:fast-execution'), false);
  } finally { await h.ctx.fiber.dispose(); }
});
