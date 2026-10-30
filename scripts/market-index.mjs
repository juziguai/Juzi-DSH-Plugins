import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { git, readTree, readBlobs } from './git-source.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));

function validateSource(repository, commit) {
  const url = new URL(repository);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
      url.href !== repository || !/^\/(?:[^/]+\/)+[^/]+$/.test(url.pathname) || /\.(?:tgz|tar\.gz)$/i.test(url.pathname)) {
    throw new Error('repository must be a canonical HTTPS Git repository URL without credentials, query or fragment');
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(commit) || commit.includes('..')) {
    throw new Error('commit must be a branch, tag or commit SHA');
  }
}

function validatePaths(plugins) {
  const paths = new Set();
  for (const {path} of plugins) {
    if (!/^plugins\/[a-z0-9][a-z0-9-]*$/.test(path) || paths.has(path)) {
      throw new Error(`invalid or duplicate plugin path: ${path}`);
    }
    paths.add(path);
  }
  return [...paths];
}

function sourceSnapshot(cwd, commit, paths) {
  const sha = git(cwd, ['rev-parse', '--verify', `${commit}^{commit}`]).trim();
  const timestamp = Number(git(cwd, ['show', '-s', '--format=%ct', sha]).trim());
  const tree = readTree(cwd, sha, paths);
  const manifests = paths.map(path => regularFile(tree, `${path}/package.json`).sha);
  return {sha, timestamp, tree, blobs:readBlobs(cwd, manifests)};
}

function regularFile(tree, path) {
  const file = tree.get(path);
  if (!file || file.type !== 'blob' || !['100644','100755'].includes(file.mode)) {
    throw new Error(`missing regular package entry: ${path}`);
  }
  return file;
}

function pluginEntry({path, ...display}, repository, source) {
  const {sha, timestamp, tree, blobs} = source;
  // Manifests and entry existence come from one immutable Git tree, never the working directory.
  const pkg = JSON.parse(blobs.get(regularFile(tree, `${path}/package.json`).sha).toString('utf8').trim());
  const patch = pkg.dsh?.bundle?.patch;
  if (typeof patch !== 'string') throw new Error(`${path}: missing DSH bundle patch`);
  for (const entry of [pkg.main, patch, 'README.md', ...Object.values(pkg.exports ?? {})]) {
    if (typeof entry !== 'string' || entry.includes('..') || /^(?:\/|[A-Za-z]:)/.test(entry)) {
      throw new Error(`${path}: unsupported or unsafe package entry`);
    }
    regularFile(tree, `${path}/${entry.replace(/^\.\//, '')}`);
  }
  return {
      ...display,
      name: pkg.name,
      repository: { url: repository, directory: path },
      versions: [{
        version: pkg.version,
        publishTimestamp: timestamp,
        engines: pkg.engines?.dsh ? { dsh: pkg.engines.dsh } : {},
        source: { type: 'git', url: repository, commit: sha, path },
      }],
  };
}

export function createMarketIndex({ catalog, repository, commit = 'HEAD', cwd = root }) {
  validateSource(repository, commit);
  const paths = validatePaths(catalog.plugins), source = sourceSnapshot(cwd, commit, paths), names = new Set();
  const plugins = catalog.plugins.map(plugin => {
    const entry = pluginEntry(plugin, repository, source);
    if (names.has(entry.name)) throw new Error(`duplicate package name: ${entry.name}`);
    names.add(entry.name); return entry;
  });
  return { format: 1, title: catalog.title, description: catalog.description, metadata: catalog.metadata, plugins };
}

export async function validateIndex(index, validatorPath) {
  if (!validatorPath) throw new Error('Set DSH_MARKET_INDEX_MODULE or pass --validator with the installed official dsh-plugin-market-index/lib/index.js path');
  const { parseMarketIndex, marketInstallTarget } = await import(pathToFileURL(resolve(validatorPath)));
  const parsed = parseMarketIndex(index, 'https://market.invalid/index.json');
  return parsed.plugins.map(plugin => ({ name: plugin.name, ...marketInstallTarget(plugin.name, plugin.versions[0]) }));
}

export function verifyPinnedIndex(index, cwd = root) {
  if (!index.plugins.length) throw new Error('Index must contain published plugins');
  const groups = new Map();
  for (const {versions} of index.plugins) {
    const source = versions[0]?.source;
    if (!source || !/^[0-9a-f]{40}$/.test(source.commit)) throw new Error('Index must pin a full source commit');
    validateSource(source.url, source.commit);
    const paths = groups.get(source.commit) ?? new Set(); paths.add(source.path); groups.set(source.commit, paths);
  }
  const sources = new Map([...groups].map(([commit,paths]) => [commit, sourceSnapshot(cwd, commit, validatePaths([...paths].map(path=>({path}))))]));
  for (const { name, repository, versions, ...display } of index.plugins) {
    const source = versions[0]?.source;
    // Display copy belongs to the market; package identity and install metadata belong to the pinned source.
    const expected = pluginEntry({...display, path:source.path}, source.url, sources.get(source.commit));
    if (JSON.stringify(expected) !== JSON.stringify({ ...display, name, repository, versions })) {
      throw new Error(`Index differs from its pinned manifest: ${name}; regenerate it`);
    }
  }
}

async function main() {
  const { values } = parseArgs({ options: {
    repository: { type: 'string' }, commit: { type: 'string', default: 'HEAD' },
    validator: { type: 'string', default: process.env.DSH_MARKET_INDEX_MODULE },
    output: { type: 'string', default: 'marketplace/index.json' },
    check: { type: 'boolean', default: false },
  } });
  const output = resolve(root, values.output);
  const catalog = JSON.parse(readFileSync(resolve(root, 'marketplace/catalog.json'), 'utf8'));
  const index = values.check ? JSON.parse(readFileSync(output, 'utf8')) : createMarketIndex({
    catalog, repository: values.repository, commit: values.commit,
  });
  const targets = await validateIndex(index, values.validator);
  // The official schema validates display fields; Git verifies package and install metadata.
  if (values.check) {
    verifyPinnedIndex(index);
  } else {
    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, `${JSON.stringify(index, null, 2)}\n`);
  }
  console.log(JSON.stringify({ file: output, plugins: targets, remoteAvailability: 'not-checked' }, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
