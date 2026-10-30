import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdtempSync, mkdirSync, copyFileSync, realpathSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createMarketIndex, verifyPinnedIndex } from './market-index.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const catalog = JSON.parse(readFileSync(new URL('../marketplace/catalog.json', import.meta.url), 'utf8'));
const repository = 'https://github.com/example/dsh-fixture';
// Validate the working catalog and manifests together, independent of release commits in this repo.
const parent = realpathSync(tmpdir()), cwd = mkdtempSync(join(parent, 'juzi-market-test-'));
after(() => {
  const target = resolve(cwd);
  assert.equal(dirname(target), parent); assert.ok(basename(target).startsWith('juzi-market-test-'));
  rmSync(target, { recursive: true, force: true });
});
const env = { ...Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_'))),
  GIT_AUTHOR_NAME: 'Market fixture', GIT_AUTHOR_EMAIL: 'fixture@example.invalid',
  GIT_COMMITTER_NAME: 'Market fixture', GIT_COMMITTER_EMAIL: 'fixture@example.invalid' };
const git = args => execFileSync('git', args, { cwd, env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
git(['init', '--quiet']);
for (const { path } of catalog.plugins) {
  const pkg = JSON.parse(readFileSync(join(root, path, 'package.json'), 'utf8'));
  for (const entry of new Set(['package.json', 'README.md', pkg.main, pkg.dsh.bundle.patch, ...Object.values(pkg.exports ?? {})])) {
    const target = join(cwd, path, entry);
    mkdirSync(dirname(target), { recursive: true }); copyFileSync(join(root, path, entry), target);
  }
}
mkdirSync(join(cwd, 'marketplace'), { recursive: true });
writeFileSync(join(cwd, 'marketplace/catalog.json'), JSON.stringify(catalog));
git(['add', '.']); git(['-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'market fixture']);
const build = options => createMarketIndex({ catalog, repository, cwd, ...options });

test('market pins every package to a real commit and its own manifest', () => {
  const index = build();
  assert.equal(index.plugins.length, catalog.plugins.length);
  for (const plugin of index.plugins) {
    const version = plugin.versions[0];
    assert.match(version.source.commit, /^[0-9a-f]{40}$/);
    const pkg = JSON.parse(git(['show', `${version.source.commit}:${version.source.path}/package.json`]));
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

test('published market validates pinned manifests while source and display catalogs advance independently', () => {
  const index = build();
  index.title = 'Updated market title';
  index.plugins[0].title = 'Updated display title';
  index.plugins[0].description = 'Display copy published after source';
  writeFileSync(join(cwd, 'marketplace/catalog.json'), JSON.stringify({ ...catalog, title: 'Next source catalog', plugins: [] }));
  assert.doesNotThrow(() => verifyPinnedIndex(index, cwd));
});

test('published market rejects tampered package identity, install metadata and movable pins', () => {
  const index = build();
  for (const mutate of [
    copy => { copy.plugins[0].name = 'tampered-package'; },
    copy => { copy.plugins[0].versions[0].version = '99.0.0'; },
    copy => { copy.plugins[0].versions[0].source.commit = 'HEAD'; },
    copy => { copy.plugins[0].versions[0].publishTimestamp += 1; },
    copy => { copy.plugins[0].versions[0].engines.dsh = '*'; },
    copy => { copy.plugins[0].repository.directory = 'plugins/absent'; },
    copy => { copy.plugins[0].versions[0].source.path = 'plugins/absent'; },
  ]) {
    const copy = structuredClone(index); mutate(copy);
    assert.throws(() => verifyPinnedIndex(copy, cwd));
  }
});

test('published market validates each plugin at its own full source commit', () => {
  const index = build(), path = catalog.plugins[0].path;
  const pkgPath = join(cwd, path, 'package.json'), pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
  writeFileSync(pkgPath, JSON.stringify({ ...pkg, version: '99.0.1' }));
  git(['add', path]); git(['-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'next plugin source']);
  index.plugins[0] = build().plugins[0];
  assert.doesNotThrow(() => verifyPinnedIndex(index, cwd));
  index.plugins[0].versions[0].source.commit = index.plugins[1].versions[0].source.commit;
  assert.throws(() => verifyPinnedIndex(index, cwd), /pinned manifest/);
});

test('market batches Git reads per immutable source without caching moving HEAD or working files', () => {
  const trace=join(cwd,'git-batch-trace.jsonl'),previous=process.env.GIT_TRACE2_EVENT;
  const calls=()=>readFileSync(trace,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse).filter(e=>e.event==='start').length;
  try {
    process.env.GIT_TRACE2_EVENT=trace;writeFileSync(trace,'');
    const index=build();assert.equal(calls(),4);
    writeFileSync(trace,'');verifyPinnedIndex(index,cwd);assert.equal(calls(),4);
    const path=join(cwd,catalog.plugins[0].path,'package.json');
    const original=readFileSync(path);writeFileSync(path,JSON.stringify({...JSON.parse(original),version:'100.0.0'}));
    assert.deepEqual(build(),index);git(['add',path]);git(['-c','commit.gpgsign=false','commit','--quiet','-m','move fixture HEAD']);
    const moved=build();assert.notEqual(moved.plugins[0].versions[0].source.commit,index.plugins[0].versions[0].source.commit);assert.equal(moved.plugins[0].versions[0].version,'100.0.0');
    assert.doesNotThrow(()=>verifyPinnedIndex(index,cwd));
  } finally {if(previous===undefined)delete process.env.GIT_TRACE2_EVENT;else process.env.GIT_TRACE2_EVENT=previous;}
});

test('market entry validation requires committed regular files, including exports and symlinks', () => {
  const path=catalog.plugins[0].path,pkgPath=join(cwd,path,'package.json'),pkg=JSON.parse(readFileSync(pkgPath,'utf8'));
  writeFileSync(pkgPath,JSON.stringify({...pkg,main:'lib'}));git(['add',pkgPath]);git(['-c','commit.gpgsign=false','commit','--quiet','-m','directory entry fixture']);
  assert.throws(()=>build(),/missing regular package entry/);
  writeFileSync(pkgPath,JSON.stringify(pkg));git(['add',pkgPath]);
  const target=execFileSync('git',['hash-object','-w','--stdin'],{cwd,env,input:'README.md',encoding:'utf8',stdio:['pipe','pipe','pipe']}).trim();
  git(['update-index','--add','--cacheinfo',`120000,${target},${path}/${pkg.main.replace(/^\.\//,'')}`]);
  git(['-c','commit.gpgsign=false','commit','--quiet','-m','symlink entry fixture']);
  assert.throws(()=>build(),/missing regular package entry/);
});
