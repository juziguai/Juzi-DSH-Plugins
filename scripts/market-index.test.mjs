import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createMarketIndex } from './market-index.mjs';

const cwd = fileURLToPath(new URL('../', import.meta.url));
const catalog = JSON.parse(readFileSync(new URL('../marketplace/catalog.json', import.meta.url), 'utf8'));
const repository = 'https://github.com/example/dsh-fixture';
const build = options => createMarketIndex({ catalog, repository, cwd, ...options });

test('market pins every package to a real commit and its own manifest', () => {
  const index = build();
  assert.equal(index.plugins.length, 3);
  for (const plugin of index.plugins) {
    const version = plugin.versions[0];
    assert.match(version.source.commit, /^[0-9a-f]{40}$/);
    const pkg = JSON.parse(execFileSync('git', ['show', `${version.source.commit}:${version.source.path}/package.json`], { cwd, encoding: 'utf8' }));
    assert.equal(plugin.name, pkg.name);
    assert.equal(version.version, pkg.version);
    assert.deepEqual(version.engines, pkg.engines);
  }
});

test('market refuses local paths, credentials and movable URL fragments', () => {
  for (const repository of ['file:///repo', 'http://example.com/a/b', 'https://user:secret@example.com/a/b', 'https://example.com/a/b#main', 'https://example.com/a/b.tgz']) {
    assert.throws(() => build({ repository }));
  }
});

test('market refuses traversal, duplicate entries and absent refs', () => {
  assert.throws(() => build({ catalog: { ...catalog, plugins: [{ path: '../outside' }] } }), /plugin path/);
  assert.throws(() => build({ catalog: { ...catalog, plugins: [catalog.plugins[0], catalog.plugins[0]] } }), /duplicate plugin path/);
  assert.throws(() => build({ commit: '--help' }), /commit must/);
  assert.throws(() => build({ commit: 'missing-market-test-ref' }));
});
