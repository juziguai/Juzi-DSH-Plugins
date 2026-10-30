import { mkdtemp, realpath, mkdir, writeFile, rm, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, dirname, basename } from 'node:path';
import { deflate } from 'node:zlib';
import { promisify } from 'node:util';

const compress = promisify(deflate);

/** Immutable Git blobs shared by live turn leases; indexes and trees remain private. */
export class BlobStore {
  constructor(budget) {
    this.budget = budget;
    this.blobs = new Map();
    this.cache = new Map();
    this.ready = this.initialize();
    this.queue = this.ready.catch(() => {});
  }
  async initialize() {
    this.tempRoot = await realpath(tmpdir());
    this.directory = await mkdtemp(join(this.tempRoot, 'juzi-dsh-blobs-'));
  }
  enqueue(task) {
    const work = this.queue.then(async () => { await this.ready; return task(); });
    this.queue = work.catch(() => {});
    return work;
  }
  retain(hash, bytes) {
    return this.enqueue(async () => {
      let blob = this.blobs.get(hash);
      if (blob) { blob.refs++; return true; }
      if (!bytes) return false;
      if (this.budget.used + bytes.length > this.budget.limit) throw new Error('变更记录空间已达上限，请结束本次运行后重试');
      // Git loose objects are zlib(header + original bytes), without repository filters.
      const content = Buffer.concat([Buffer.from(`blob ${bytes.length}\0`), bytes]);
      const folder = join(this.directory, hash.slice(0, 2));
      await mkdir(folder, { recursive: true });
      const path = join(folder, hash.slice(2));
      try { await writeFile(path, await compress(content), { flag: 'wx' }); }
      catch (error) { await unlink(path).catch(() => {}); throw error; }
      blob = { refs: 1, size: bytes.length, paths: new Set() };
      this.blobs.set(hash, blob); this.budget.used += bytes.length;
      return true;
    });
  }
  remember(entry) {
    const previous = this.cache.get(entry.path);
    if (previous) this.blobs.get(previous.hash)?.paths.delete(entry.path);
    this.cache.set(entry.path, entry);
    this.blobs.get(entry.hash).paths.add(entry.path);
  }
  release(hashes) {
    return this.enqueue(async () => {
      for (const hash of hashes) {
        const blob = this.blobs.get(hash);
        if (!blob || --blob.refs > 0) continue;
        await unlink(join(this.directory, hash.slice(0, 2), hash.slice(2)));
        this.blobs.delete(hash);
        for (const path of blob.paths) this.cache.delete(path);
        this.budget.used -= blob.size;
      }
    });
  }
  async dispose() {
    await this.ready;
    await this.queue;
    const target = resolve(this.directory);
    if (dirname(target) !== this.tempRoot || !basename(target).startsWith('juzi-dsh-blobs-')) throw new Error('Unexpected blob cleanup path');
    await rm(target, { recursive: true, force: true });
    this.budget.used -= [...this.blobs.values()].reduce((sum, blob) => sum + blob.size, 0);
    this.blobs.clear(); this.cache.clear();
  }
}
