import assert from 'node:assert/strict';
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
execFileSync(process.execPath, [join(root, 'plugins/dsh-ultra-effort/build/client.mjs'), '--check'], { stdio: 'pipe' });
const names = new Set();
for (const dir of readdirSync(join(root, 'plugins'))) {
  const base = join(root, 'plugins', dir);
  const pkg = JSON.parse(readFileSync(join(base, 'package.json'), 'utf8'));
  assert(!names.has(pkg.name), `duplicate package: ${pkg.name}`);
  names.add(pkg.name);
  for (const entry of [pkg.main, pkg.dsh.bundle.patch, 'README.md', ...Object.values(pkg.exports)]) {
    assert(existsSync(join(base, entry)), `${dir}: missing ${entry}`);
  }
  const patch = readFileSync(join(base, pkg.dsh.bundle.patch), 'utf8');
  assert(patch.includes(`name: '${pkg.name}'`), `${dir}: bundle package mismatch`);
  for (const file of readdirSync(join(base, 'lib')).filter(f => f.endsWith('.js'))) {
    execFileSync(process.execPath, ['--check', join(base, 'lib', file)], { stdio: 'pipe' });
  }
  console.log(`OK ${pkg.name}@${pkg.version}`);
}
assert.equal(names.size, 4);
