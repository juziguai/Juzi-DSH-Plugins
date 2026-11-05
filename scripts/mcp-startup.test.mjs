import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const inside = (base, path) => {
  const offset = relative(base, path);
  return !isAbsolute(offset) && offset !== '..' && !offset.startsWith('..' + (process.platform === 'win32' ? '\\' : '/'));
};

test('every MCP bundle uses replaceable package resources and preserves an explicit interpreter', async t => {
  const plugins = readdirSync(join(root, 'plugins')).map(dir => {
    const base = join(root, 'plugins', dir);
    return { base, pkg: JSON.parse(readFileSync(join(base, 'package.json'), 'utf8')) };
  }).filter(({ pkg }) => pkg.peerDependencies?.['@deepseek-ai/dsh-mcp-client']);
  assert.ok(plugins.length, 'MCP bundle discovery must not silently skip all plugins');
  // Packaged servers ship lib/config.js. Memory peers the same client but launches
  // a Host-configured LocalMemory core, so it must not be forced into that shape.
  const packaged = plugins.filter(({ base }) => existsSync(join(base, 'lib/config.js')));
  const external = plugins.filter(({ base }) => !existsSync(join(base, 'lib/config.js')));
  assert.deepEqual(external.map(({ pkg }) => pkg.name).sort(), ['@juzi/dsh-memory']);
  assert.ok(packaged.length, 'packaged MCP discovery must not silently skip every bundle');
  for (const { base, pkg } of packaged) {
    await t.test(pkg.name, async () => {
      const { createConfig } = await import(pathToFileURL(join(base, 'lib/config.js')));
      const config = createConfig();
      assert.equal(config.transport, 'stdio');
      assert.ok(isAbsolute(config.cwd) && existsSync(config.cwd), 'cwd must be an existing absolute directory');
      assert.ok(!inside(realpathSync(base), realpathSync(config.cwd)), 'cwd must be outside the replaceable package');
      assert.ok(isAbsolute(config.args[0]) && existsSync(config.args[0]), 'server entry must be absolute');
      assert.ok(inside(realpathSync(base), realpathSync(dirname(config.args[0]))), 'server entry must stay in the package');
      const python = join(tmpdir(), 'project venv with spaces', 'python.exe');
      assert.equal(createConfig({ python }).command, python, 'explicit project interpreters must remain authoritative');
    });
  }
});

test('memory launches the host LocalMemory core outside the replaceable package', async () => {
  const base = join(root, 'plugins/dsh-memory');
  const { mcpClientConfig } = await import(pathToFileURL(join(base, 'lib/mcp.js')));
  const work = mkdtempSync(join(tmpdir(), 'juzi-memory-core-'));
  try {
    const core = join(work, 'LocalMemory', 'src', 'interfaces', 'cli', 'index.js');
    const memoryRoot = join(work, 'isolated-memory');
    const coreConfig = join(memoryRoot, 'config.json');
    mkdirSync(dirname(core), { recursive: true });
    mkdirSync(memoryRoot, { recursive: true });
    writeFileSync(core, '');
    writeFileSync(coreConfig, '{}\n');
    const host = { coreEntry: core, memoryRoot, coreConfig, timeoutMs: 2500 };
    const project = mcpClientConfig(host, { includeGlobal: true }, 'project:atlas', 'host-key');
    assert.equal(project.transport, 'stdio');
    assert.equal(project.command, process.execPath);
    assert.deepEqual(project.args, [core, 'mcp', '--root', memoryRoot, '--scope', 'project:atlas', '--include-global']);
    assert.equal(project.cwd, dirname(core));
    assert.ok(existsSync(project.cwd));
    assert.ok(!inside(realpathSync(base), realpathSync(project.cwd)), 'core cwd must stay outside the plugin package');
    assert.ok(!inside(realpathSync(base), realpathSync(core)), 'core entry must stay outside the plugin package');
    assert.equal(project.env.LOCALMEMORY_HOST_KEY, 'host-key');
    assert.equal(project.env.LOCALMEMORY_BRAIN_CONFIG, coreConfig);
    assert.equal(project.failOnStartupError, true);
    assert.match(project.serverName, /^juzi-memory-[a-f0-9]{12}$/);
    const global = mcpClientConfig(host, { includeGlobal: true }, 'global', 'host-key');
    assert.equal(global.args.includes('--include-global'), false);
    const bare = mcpClientConfig({ ...host, coreConfig: '' }, { includeGlobal: false }, 'global', 'other-key');
    assert.equal(Object.hasOwn(bare.env, 'LOCALMEMORY_BRAIN_CONFIG'), false);
    assert.equal(bare.command, process.execPath);
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});
