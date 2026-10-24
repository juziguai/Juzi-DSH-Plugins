import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, copyFileSync, rmSync, realpathSync } from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname, resolve, basename } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';

const root = fileURLToPath(new URL('../plugins/dsh-preset-unlock/', import.meta.url));
const normalized = path => readFileSync(path, 'utf8').replaceAll('\r\n', '\n');
const vendor = normalized(join(root, 'vendor/standard.patch.yml'));
const persona = normalized(join(root, 'prompts/persona.md'));
function fixture(t, source = vendor, text = persona) {
  const parent = realpathSync(tmpdir()), cwd = mkdtempSync(join(parent, 'juzi-preset-test-'));
  t.after(() => {
    const target = resolve(cwd);
    assert.equal(dirname(target), parent); assert.ok(basename(target).startsWith('juzi-preset-test-'));
    rmSync(target, { recursive: true, force: true });
  });
  for (const dir of ['build', 'vendor', 'prompts']) mkdirSync(join(cwd, dir));
  copyFileSync(join(root, 'build/patch.mjs'), join(cwd, 'build/patch.mjs'));
  writeFileSync(join(cwd, 'vendor/standard.patch.yml'), source);
  writeFileSync(join(cwd, 'prompts/persona.md'), text);
  return cwd;
}
test('preset generation is deterministic and check detects edits without overwriting them', t => {
  const cwd = fixture(t), run = args => execFileSync(process.execPath, ['build/patch.mjs', ...args], { cwd, stdio: 'pipe' });
  run([]); run(['--check']);
  assert.equal(normalized(join(cwd, 'cordis.patch.yml')), normalized(join(root, 'cordis.patch.yml')));
  writeFileSync(join(cwd, 'cordis.patch.yml'), 'edited output\n');
  assert.throws(() => run(['--check']));
  assert.equal(readFileSync(join(cwd, 'cordis.patch.yml'), 'utf8'), 'edited output\n');
});
test('invalid preset inputs fail before replacing the last good patch', async t => {
  const cases = [
    ['missing preset', vendor.replace('    - id: preset-standard', '    - id: changed'), persona],
    ['duplicate preset', vendor + '\n    - id: preset-standard\n', persona],
    ['missing plugins', vendor.replace('        plugins:', '        children:'), persona],
    ['missing persona prefix', vendor.replace('              prefix: ', '              suffix: '), persona],
    ['blank persona', vendor, ' \n\n'],
  ];
  for (const [name, source, text] of cases) await t.test(name, st => {
    const cwd = fixture(st, source, text); writeFileSync(join(cwd, 'cordis.patch.yml'), 'last good patch\n');
    const result = spawnSync(process.execPath, ['build/patch.mjs'], { cwd, encoding: 'utf8' });
    assert.notEqual(result.status, 0); assert.ok(result.stderr);
    assert.equal(readFileSync(join(cwd, 'cordis.patch.yml'), 'utf8'), 'last good patch\n');
  });
});
const official = process.env.DSH_PRESET_MODULE;
async function officialConfig() {
  const require = createRequire(pathToFileURL(official));
  const yaml = require('js-yaml');
  const { entryListSchema } = await import(pathToFileURL(require.resolve('@deepseek-ai/cordis-plugin-include')));
  const { default: Preset } = await import(pathToFileURL(official));
  const load = value => yaml.load(value, { schema: entryListSchema });
  const patch = load(normalized(join(root, 'cordis.patch.yml')));
  return { require, Preset, patch, baseline: load(vendor)[0].insert[0].config };
}
test('official YAML and preset schema preserve standard tools and replace only persona', { skip: !official }, async () => {
  const { Preset, patch, baseline } = await officialConfig();
  assert.equal(patch.length, 1); assert.deepEqual(Object.keys(patch[0]), ['insert']);
  assert.equal(patch[0].insert.length, 2);
  assert.equal(patch[0].insert[0].name, '@juzi/dsh-preset-unlock');
  const row = patch[0].insert[1]; assert.equal(row.name, '@deepseek-ai/dsh-agent-preset');
  const config = Preset.Config(row.config);
  assert.equal(config.id, 'unlock'); assert.equal(config.name, '解锁模式'); assert.equal(config.order, 2);
  const hash = value => createHash('sha256').update(value).digest('hex');
  assert.equal(hash(config.plugins.find(row => row.id === 'persona').config.prefix), hash(persona.replace(/\n+$/, '')));
  const withoutPersona = rows => rows.map(row => row.id === 'persona' ? { ...row, config: { ...row.config, prefix: '<persona>' } } : row);
  assert.deepEqual(withoutPersona(config.plugins), withoutPersona(baseline.plugins));
  assert.throws(() => Preset.Config({ plugins: [] }));
});
test('actual Cordis registers the preset declaration and disposes it without activating tools', { skip: !official }, async () => {
  const { require, Preset, patch } = await officialConfig();
  const { Context } = await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
  const ctx = new Context(), definitions = []; let disposed = 0;
  try {
    await ctx.plugin({ name: 'test-registry', apply(scope) { scope.provide('agentPresets', { register: async config => { definitions.push(config); return () => { disposed++; }; } }); } });
    await ctx.plugin(Preset, patch[0].insert[1].config);
    assert.equal(definitions.length, 1); assert.equal(definitions[0].id, 'unlock');
  } finally { await ctx.fiber.dispose(); }
  assert.equal(disposed, 1);
});
