import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, realpathSync } from 'node:fs';
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
  for (const { base, pkg } of plugins) {
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
