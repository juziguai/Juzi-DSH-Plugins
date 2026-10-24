import { spawn } from 'node:child_process';
import { mkdtemp, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, dirname, basename } from 'node:path';
import assert from 'node:assert/strict';

export async function nodeGit(args, { cwd, input, signal, env = {}, maxBytes = 8 * 1024 * 1024 } = {}) {
  return new Promise((resolve, reject) => {
    const base = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_')));
    const child = spawn('git', args, { cwd, signal, windowsHide: true, env: { ...base, ...env, GIT_OPTIONAL_LOCKS: '0', LC_ALL: 'C' }, stdio: ['pipe', 'pipe', 'pipe'] });
    const output = [], errors = []; let size = 0;
    child.stdout.on('data', chunk => { size += chunk.length; output.push(chunk); if (size > maxBytes) child.kill(); });
    child.stderr.on('data', chunk => errors.push(chunk));
    child.on('error', reject);
    child.on('close', code => size > maxBytes ? reject(new Error('Git output limit exceeded')) : resolve({ code, stdout: Buffer.concat(output).toString('utf8'), stderr: Buffer.concat(errors).toString('utf8') }));
    child.stdin.on('error', error => { if (error.code !== 'EPIPE') reject(error); });
    child.stdin.end(input);
  });
}
export async function workspace(t, { repository = true } = {}) {
  const parent = await realpath(tmpdir());
  const cwd = await mkdtemp(join(parent, 'juzi-changes-test-'));
  t.after(async () => {
    const target = resolve(cwd);
    assert.equal(dirname(target), parent); assert.ok(basename(target).startsWith('juzi-changes-test-'));
    await rm(target, { recursive: true, force: true });
  });
  const git = async (...args) => {
    const result = await nodeGit(args, { cwd });
    assert.equal(result.code, 0, result.stderr); return result.stdout;
  };
  if (repository) {
    await git('init', '--quiet');
    await git('config', 'user.name', 'Changes fixture'); await git('config', 'user.email', 'fixture@example.invalid');
    await writeFile(join(cwd, 'file.txt'), 'base\n'); await writeFile(join(cwd, '.gitignore'), 'ignored.txt\nnode_modules/\n');
    await git('add', '.'); await git('commit', '--quiet', '-m', 'fixture');
  }
  return { cwd, git };
}
export const quietWatcher = () => ({ on() {}, close() {} });
