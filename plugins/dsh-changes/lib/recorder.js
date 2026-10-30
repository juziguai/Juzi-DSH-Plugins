import { watch } from 'node:fs';
import { lstat, open, writeFile, readlink, mkdtemp, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, relative, isAbsolute, join, sep, dirname, basename } from 'node:path';
import { createHash } from 'node:crypto';
import { isUtf8 } from 'node:buffer';
import { checked, parseNumstat, parseHunks } from './git.js';
import { BlobStore } from './blob-store.js';

export const defaults = { refreshMs: 750, timeoutMs: 15000, maxFiles: 500, maxFileBytes: 2 * 1024 * 1024,
  maxSnapshotBytes: 128 * 1024 * 1024, maxStoredBytes: 512 * 1024 * 1024, maxTrackedFiles: 20000, maxTurns: 30 };

export function configOf(value = {}) {
  const config = { ...defaults, ...value };
  for (const key of Object.keys(defaults)) if (!Number.isSafeInteger(config[key]) || config[key] < 1) throw new Error(`Invalid changes config: ${key}`);
  if (config.refreshMs < 250) throw new Error('refreshMs must be at least 250');
  return config;
}
const slash = path => path.split(sep).join('/');
const inside = (root, path) => { const part = relative(root, path); return part === '' || (!isAbsolute(part) && part !== '..' && !part.startsWith('..' + sep)); };
const ignoredEvent = path => /(^|[\\/])(\.git|node_modules|__pycache__)([\\/]|$)/.test(path);
const signature = stat => `${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}:${stat.ino}:${stat.mode}`;
async function canonical(path) {
  let head = resolve(path); const missing = [];
  while (true) {
    try { return join(await realpath(head), ...missing); }
    catch (error) {
      if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error;
      if (dirname(head) === head) throw error;
      missing.unshift(basename(head)); head = dirname(head);
    }
  }
}

const sameTree = (a, b) => a.size === b.size && [...a].every(([key, value]) => {
  const other = b.get(key); return other?.hash === value.hash && other.mode === value.mode;
});

/** Per-turn trees/index with shared immutable blobs, outside the user's Git directory. */
export class TurnRecord {
  constructor({ sessionId, turn, cwd, git, config = {}, signal, watcher = watch, onError = () => {}, budget, store }) {
    Object.assign(this, { sessionId, turn, cwd: resolve(cwd), git, config: configOf(config), watcher, onError });
    this.controller = new AbortController();
    this.signal = signal ? AbortSignal.any([signal, this.controller.signal]) : this.controller.signal;
    this.before = new Map(); this.after = new Map(); this.extra = new Set(); this.dirtyPaths = new Set();
    this.revision = 0; this.dirty = true; this.status = 'starting'; this.warning = null; this.error = null;
    this.files = []; this.total = 0; this.added = 0; this.deleted = 0; this.lastScan = 0;
    this.queue = Promise.resolve();
    this.budget = store?.budget ?? budget ?? { used: 0, limit: this.config.maxStoredBytes };
    this.store = store ?? new BlobStore(this.budget); this.ownsStore = !store;
    this.heldHashes = new Set();
    this.ready = this.enqueue(async () => {
      try { await this.initialize(); this.status = 'running'; }
      catch (error) { this.fail(error); }
    });
  }
  enqueue(task) {
    const work = this.queue.then(() => { this.signal.throwIfAborted(); return task(); });
    this.queue = work.catch(() => {});
    return work;
  }
  fail(error) {
    if (this.signal.aborted) return;
    this.error = error.message; this.status = 'error'; this.onError(error);
  }
  async run(args, options = {}) {
    return this.git(args, { cwd: this.cwd, signal: this.signal, ...options });
  }
  async privateRun(args, options = {}) {
    return checked(await this.run(['--git-dir=' + this.directory, ...args], options), `changes ${args[0]}`);
  }
  async initialize() {
    this.cwd = await realpath(this.cwd);
    this.tempRoot = await realpath(tmpdir());
    this.directory = await mkdtemp(join(this.tempRoot, 'juzi-dsh-changes-'));
    checked(await this.run(['init', '--bare', '--object-format=sha1', '--quiet', this.directory]), 'private Git init');
    await this.store.ready;
    await writeFile(join(this.directory, 'objects/info/alternates'), slash(this.store.directory) + '\n');
    const found = await this.run(['-C', this.cwd, 'rev-parse', '--show-toplevel']);
    if (found.code === 0) this.root = await realpath(found.stdout.trim());
    else if (found.code === 128 && /not a git repository/i.test(found.stderr)) this.warning = '当前目录没有 Git 仓库，仅记录文件编辑工具；shell 修改不在覆盖范围。';
    else checked(found, 'locate workspace');
    this.after = await this.readWorkspace(new Map());
    this.before = new Map(this.after);
    this.beforeTree = await this.writeTree(this.before);
    this.afterTree = this.beforeTree; this.baseRevision = this.beforeTree; this.dirty = false;
    if (this.root) {
      try {
        this.observer = this.watcher(this.root, { recursive: true }, (_event, path) => {
          if (!path) this.markDirty();
          else if (!ignoredEvent(String(path))) this.markDirty(resolve(this.root, String(path)));
        });
        this.observer.on('error', error => { this.observer.close(); this.warning = '文件监听已停止，工具执行结束后更新；可手动刷新。'; this.markDirty(); this.onError(error); });
      } catch (error) { this.warning = '无法监听文件，工具执行结束后更新；可手动刷新。'; this.onError(error); }
    }
  }
  markDirty(path) { this.dirty = true; if (path) this.dirtyPaths.add(path); }
  key(path) { return 'f/' + createHash('sha256').update(process.platform === 'win32' ? path.toLowerCase() : path).digest('hex'); }
  label(path) { const part = relative(this.cwd, path); return inside(this.cwd, path) ? slash(part) : path; }
  async readEntry(path, old, force, budget) {
    let stat;
    try { stat = await lstat(path); } catch (error) { if (error.code === 'ENOENT' || error.code === 'ENOTDIR') return null; throw error; }
    if (!stat.isFile() && !stat.isSymbolicLink()) return null;
    const stamp = signature(stat);
    const cached = old ?? this.store.cache.get(path);
    if (cached && cached.stamp === stamp && (old || !cached.oversized) && !force) {
      if (this.heldHashes.has(cached.hash) || await this.store.retain(cached.hash)) {
        this.heldHashes.add(cached.hash);
        const display = this.label(path);
        return cached.display === display ? cached : { ...cached, display };
      }
    }
    let oversized = stat.size > this.config.maxFileBytes || budget.bytes + stat.size > this.config.maxSnapshotBytes;
    let bytes;
    if (oversized) bytes = Buffer.from(`omitted:${stamp}`);
    else {
      if (stat.isSymbolicLink()) bytes = Buffer.from(await readlink(path));
      else {
        const handle = await open(path, 'r');
        try {
          const buffer = this.readBuffer ??= Buffer.alloc(this.config.maxFileBytes + 1); let length = 0;
          while (length < buffer.length) {
            const { bytesRead } = await handle.read(buffer, length, buffer.length - length, length);
            if (!bytesRead) break;
            length += bytesRead;
          }
          bytes = buffer.subarray(0, length);
        } finally { await handle.close(); }
      }
      if (bytes.length > this.config.maxFileBytes) { oversized = true; bytes = Buffer.from(`omitted:${stamp}`); }
      else budget.bytes += bytes.length;
    }
    const hash = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    if (!this.heldHashes.has(hash)) {
      await this.store.retain(hash, bytes);
      this.heldHashes.add(hash);
    }
    const entry = { key: this.key(path), path, display: this.label(path), stamp, hash,
      mode: stat.isSymbolicLink() ? '120000' : '100644', oversized, binary: !oversized && (bytes.includes(0) || !isUtf8(bytes)) };
    this.store.remember(entry);
    return entry;
  }
  async paths() {
    if (!this.root) return [...this.extra];
    const list = checked(await this.run(['-C', this.root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard']), 'list workspace files');
    if (list && !list.endsWith('\0')) throw new Error('Incomplete workspace file list');
    const paths = [...new Set([...list.split('\0').filter(Boolean).map(path => resolve(this.root, path)), ...this.extra])];
    if (paths.length > this.config.maxTrackedFiles) throw new Error(`Workspace exceeds maxTrackedFiles (${this.config.maxTrackedFiles})`);
    return paths;
  }
  async readWorkspace(old, force = false, forcedPaths = this.dirtyPaths) {
    const next = new Map(), budget = { bytes: 0 };
    for (const path of await this.paths()) {
      this.signal.throwIfAborted();
      const entry = await this.readEntry(path, old.get(this.key(path)), force || forcedPaths.has(path), budget);
      if (entry) next.set(entry.key, entry);
    }
    return next;
  }
  async writeTree(entries) {
    await this.privateRun(['read-tree', '--empty']);
    if (entries.size) {
      const input = [...entries.values()].map(file => `${file.mode} ${file.hash}\t${file.key}\0`).join('');
      await this.privateRun(['update-index', '-z', '--index-info'], { input });
    }
    return (await this.privateRun(['write-tree'])).trim();
  }
  async covered(path) {
    if (!this.root || !inside(this.root, path)) return false;
    // Git doesn't enumerate files beneath directory symlinks or nested repositories.
    for (let parent = dirname(path); parent !== this.root && inside(this.root, parent); parent = dirname(parent)) {
      try { if ((await lstat(parent)).isSymbolicLink()) return false; }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      try { await lstat(join(parent, '.git')); return false; }
      catch (error) { if (error.code !== 'ENOENT' && error.code !== 'ENOTDIR') throw error; }
    }
    const ignored = await this.run(['-C', this.root, 'check-ignore', '-q', '--', path]);
    if (ignored.code !== 0 && ignored.code !== 1) checked(ignored, 'classify edited file');
    return ignored.code === 1;
  }
  /** Called before a file tool writes; ignored/outside paths gain their own exact baseline. */
  async capture(path) {
    await this.ready;
    if (this.status !== 'running' || this.closing) return;
    path = await canonical(path);
    return this.enqueue(async () => {
      const key = this.key(path);
      const covered = await this.covered(path);
      if (!covered && !this.before.has(key) && !this.extra.has(path)) {
        const entry = await this.readEntry(path, null, true, { bytes: 0 });
        this.extra.add(path);
        if (entry) { this.before.set(key, entry); this.beforeTree = await this.writeTree(this.before); }
      }
      this.extra.add(path);
      this.markDirty(path);
    });
  }
  async refresh(force = false) {
    await this.ready;
    if (this.status === 'error' || this.status === 'finished' || this.status === 'interrupted' || (this.closing && !force)) return this.summary();
    return this.enqueue(async () => {
      if (['finished', 'interrupted', 'error'].includes(this.status) || (this.closing && !force)) return this.summary();
      if (!force && (!this.dirty || Date.now() - this.lastScan < this.config.refreshMs)) return this.summary();
      const dirty = this.dirtyPaths; this.dirtyPaths = new Set(); this.dirty = false;
      try {
        // Keep write events arriving during the scan for the next revision.
        const after = await this.readWorkspace(this.after, false, dirty);
        const tree = sameTree(this.after, after) ? this.afterTree : await this.writeTree(after);
        if (tree !== this.afterTree || this.baseRevision !== this.beforeTree) {
          const rows = parseNumstat(await this.privateRun(['diff-tree', '--no-commit-id', '-r', '-M', '--numstat', '-z', this.beforeTree, tree]));
          this.files = rows.map(row => {
            const previous = this.before.get(row.oldPath ?? row.path), current = after.get(row.path);
            const file = current ?? previous;
            const oversized = Boolean(current?.oversized || previous?.oversized);
            const binary = !oversized && Boolean(row.binary || current?.binary || previous?.binary);
            return { id: row.path, path: this.label(file.path), display: file.display, status: row.oldPath ? 'renamed' : !previous ? 'added' : !current ? 'deleted' : 'modified',
              ...(row.oldPath ? { oldId: row.oldPath, oldDisplay: previous.display } : {}),
              added: oversized || binary ? 0 : row.added, deleted: oversized || binary ? 0 : row.deleted, binary, oversized };
          }).sort((a, b) => a.display < b.display ? -1 : a.display > b.display ? 1 : 0);
          this.total = this.files.length; this.added = this.files.reduce((n, file) => n + file.added, 0); this.deleted = this.files.reduce((n, file) => n + file.deleted, 0);
          this.afterTree = tree; this.baseRevision = this.beforeTree; this.revision++;
        }
        this.after = after;
        this.lastScan = Date.now(); this.error = null;
      } catch (error) {
        if (this.error !== error.message) this.onError(error);
        this.error = error.message; this.dirty = true; for (const path of dirty) this.dirtyPaths.add(path);
      }
      return this.summary();
    });
  }
  summary() {
    return { turn: this.turn, status: this.status, revision: this.revision, files: this.files.slice(0, this.config.maxFiles), total: this.total,
      added: this.added, deleted: this.deleted, warning: this.warning, error: this.error, updatedAt: this.lastScan || null };
  }
  async finish(status = 'finished') {
    this.closing = true; this.observer?.close();
    await this.refresh(true);
    if (this.status !== 'error') this.status = status;
    this.observer?.close();
    this.readBuffer = null;
    return this.summary();
  }
  async diff(id, revision) {
    await this.ready;
    return this.enqueue(async () => {
      if (revision !== this.revision) return { kind: 'stale' };
      const file = this.files.slice(0, this.config.maxFiles).find(file => file.id === id);
      if (!file) return null;
      if (file.oversized || file.binary) return { kind: file.oversized ? 'oversized' : 'binary', display: file.display };
      const patch = await this.privateRun(['diff', '--no-ext-diff', '--no-textconv', '--no-color', '--unified=3', '-M', this.beforeTree, this.afterTree, '--', file.oldId ?? file.id, file.id]);
      return { kind: 'text', display: file.display, hunks: parseHunks(patch) };
    });
  }
  async dispose() {
    if (this.disposal) return this.disposal;
    this.disposal = this.release();
    return this.disposal;
  }
  async release() {
    this.controller.abort(); this.observer?.close();
    await this.queue;
    if (this.directory) {
      const target = resolve(this.directory);
      if (dirname(target) !== this.tempRoot || !basename(target).startsWith('juzi-dsh-changes-')) throw new Error('Unexpected snapshot cleanup path');
      await rm(target, { recursive: true, force: true });
    }
    await this.store.release(this.heldHashes); this.heldHashes.clear();
    if (this.ownsStore) await this.store.dispose();
    this.before.clear(); this.after.clear();
    this.readBuffer = null;
  }
}
