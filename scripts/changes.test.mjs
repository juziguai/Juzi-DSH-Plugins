import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, rename, rm, access, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { TurnRecord } from '../plugins/dsh-changes/lib/recorder.js';
import { parseNumstat, parseHunks } from '../plugins/dsh-changes/lib/git.js';
import { workspace, nodeGit, quietWatcher } from '../plugins/dsh-changes/test/helpers.mjs';

function record(t, cwd, options = {}) {
  const record = new TurnRecord({ sessionId: 'fixture', turn: 1, cwd, git: nodeGit, watcher: quietWatcher, ...options });
  t.after(() => record.dispose()); return record;
}
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

test('turn baseline excludes pre-existing staged/unstaged/untracked work and never writes user index or refs', async t => {
  const { cwd, git } = await workspace(t);
  await writeFile(join(cwd, 'file.txt'), 'staged\n'); await git('add', 'file.txt');
  await writeFile(join(cwd, 'file.txt'), 'staged\nprior dirty\n');
  await writeFile(join(cwd, 'prior.txt'), 'prior untracked\n');
  const originalIndex = digest(await readFile(join(cwd, '.git/index'))), head = await git('rev-parse', 'HEAD');
  const r = record(t, cwd); await r.ready;
  assert.equal(r.status, 'running', r.error);
  assert.equal((await r.refresh(true)).total, 0);
  await writeFile(join(cwd, 'file.txt'), 'staged\nprior dirty\nthis turn\n');
  const summary = await r.refresh(true);
  assert.deepEqual(summary.files.map(file => file.display), ['file.txt']);
  assert.equal(summary.added, 1); assert.equal(summary.deleted, 0);
  const diff = await r.diff(summary.files[0].id, summary.revision);
  assert.ok(diff.hunks.some(hunk => hunk.lines.includes('+this turn')));
  assert.equal(digest(await readFile(join(cwd, '.git/index'))), originalIndex);
  assert.equal(await git('rev-parse', 'HEAD'), head);
});
test('add/delete/rename, binary and oversized paths remain distinguishable', async t => {
  const { cwd, git } = await workspace(t);
  await writeFile(join(cwd, 'remove.txt'), 'remove me\n'); await git('add', '.'); await git('commit', '--quiet', '-m', 'more');
  const r = record(t, cwd, { config: { maxFileBytes: 100 } }); await r.ready;
  await rename(join(cwd, 'file.txt'), join(cwd, '中文 new.txt'));
  await rm(join(cwd, 'remove.txt'));
  await writeFile(join(cwd, 'added.txt'), 'new\n'); await writeFile(join(cwd, 'binary.bin'), Buffer.from([0, 1, 2]));
  await writeFile(join(cwd, 'large.txt'), 'x'.repeat(101));
  const summary = await r.refresh(true);
  assert.equal(summary.files.find(file => file.display === '中文 new.txt').status, 'renamed');
  assert.equal(summary.files.find(file => file.display === 'remove.txt').status, 'deleted');
  assert.equal(summary.files.find(file => file.display === 'added.txt').status, 'added');
  for (const [path, kind] of [['binary.bin', 'binary'], ['large.txt', 'oversized']]) {
    const file = summary.files.find(file => file.display === path);
    assert.equal((await r.diff(file.id, summary.revision)).kind, kind);
  }
});
test('explicit ignored-file edits preserve original bytes and new shell files are not rebased at later tool edits', async t => {
  const { cwd } = await workspace(t);
  const ignored = join(cwd, 'ignored.txt'); await writeFile(ignored, 'before\n');
  const r = record(t, cwd); await r.ready;
  await r.capture(ignored); await writeFile(ignored, 'after\n');
  const added = join(cwd, 'from-shell.txt'); await writeFile(added, 'shell\n');
  await r.capture(added); await writeFile(added, 'shell\ntool\n');
  const summary = await r.refresh(true);
  const file = summary.files.find(file => file.display === 'from-shell.txt');
  assert.equal(file.status, 'added'); assert.equal(file.added, 2);
  const ignoredFile = summary.files.find(file => file.display === 'ignored.txt');
  const diff = await r.diff(ignoredFile.id, summary.revision);
  assert.ok(diff.hunks.some(hunk => hunk.lines.includes('-before') && hunk.lines.includes('+after')));
});
test('non-Git workspaces capture named file tools and announce their shell coverage limit', async t => {
  const { cwd } = await workspace(t, { repository: false });
  const path = join(cwd, 'plain.txt'); await writeFile(path, 'before\n');
  const r = record(t, cwd); await r.ready;
  assert.match(r.warning, /shell/);
  await r.capture(path); await writeFile(path, 'after\n');
  await writeFile(join(cwd, 'shell-only.txt'), 'not captured\n');
  assert.deepEqual((await r.refresh(true)).files.map(file => file.display), ['plain.txt']);
});
test('live filesystem signals refresh a running turn; finished snapshots remain fixed and stale coordinates are rejected', async t => {
  const { cwd } = await workspace(t);
  const r = record(t, cwd, { watcher: undefined }); await r.ready;
  // Use the actual fs.watch default, not a tool-result signal.
  assert.ok(r.observer);
  await writeFile(join(cwd, 'file.txt'), 'live\n');
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal(r.dirty, true);
  const first = await r.refresh(true);
  await writeFile(join(cwd, 'file.txt'), 'later\n');
  const final = await r.finish();
  assert.equal((await r.diff(first.files[0].id, first.revision)).kind, 'stale');
  await writeFile(join(cwd, 'file.txt'), 'another turn\n');
  assert.equal((await r.refresh(true)).revision, final.revision);
  const diff = await r.diff(final.files[0].id, final.revision);
  assert.ok(diff.hunks.some(hunk => hunk.lines.includes('+later')));
  assert.ok(!diff.hunks.some(hunk => hunk.lines.includes('+another turn')));
  const directory = r.directory; await r.dispose(); await assert.rejects(access(directory));
});
test('snapshots do not execute repository clean filters', async t => {
  const { cwd, git } = await workspace(t);
  await writeFile(join(cwd, '.gitattributes'), '*.txt filter=unavailable\n');
  await git('config', 'filter.unavailable.clean', 'this-command-does-not-exist');
  await git('config', 'filter.unavailable.required', 'true');
  const r = record(t, cwd); await r.ready;
  assert.equal(r.status, 'running', r.error);
  await writeFile(join(cwd, 'file.txt'), 'updated\n');
  assert.ok((await r.refresh(true)).files.some(file => file.display === 'file.txt'));
});
test('malformed Git statistics fail visibly; patch parsing preserves line prefixes', () => {
  assert.throws(() => parseNumstat('1\t0\tbroken'), /Incomplete/);
  assert.throws(() => parseNumstat('oops\0'), /Invalid/);
  assert.deepEqual(parseHunks('@@ -1 +1 @@\n-old\n+new\n'), [{ oldStart: 1, oldLines: 1, newStart: 1, newLines: 1, lines: ['-old', '+new'] }]);
});

test('explicit file tools inside a nested repository capture the original content', async t => {
  const { cwd } = await workspace(t);
  const nested = join(cwd, 'nested'); await mkdir(nested);
  assert.equal((await nodeGit(['init', '--quiet'], { cwd: nested })).code, 0);
  const path = join(nested, 'inner.txt'); await writeFile(path, 'original\n');
  const r = record(t, cwd); await r.ready;
  await r.capture(path); await writeFile(path, 'changed\n');
  const summary = await r.refresh(true);
  const file = summary.files.find(file => file.display === 'nested/inner.txt');
  const diff = await r.diff(file.id, summary.revision);
  assert.ok(diff.hunks.some(hunk => hunk.lines.includes('-original')));
});

test('shared temporary-content budget fails visibly and is released on disposal', async t => {
  const { cwd } = await workspace(t);
  const budget = { used: 0, limit: 1 };
  const r = record(t, cwd, { budget }); await r.ready;
  assert.equal(r.status, 'error'); assert.match(r.error, /上限/);
  await r.dispose(); assert.equal(budget.used, 0);
});
