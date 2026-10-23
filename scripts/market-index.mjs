import { execFileSync } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const root = fileURLToPath(new URL('../', import.meta.url));

function git(cwd, args) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

export function createMarketIndex({ catalog, repository, commit = 'HEAD', cwd = root }) {
  const url = new URL(repository);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
      url.href !== repository || !/^\/(?:[^/]+\/)+[^/]+$/.test(url.pathname) || /\.(?:tgz|tar\.gz)$/i.test(url.pathname)) {
    throw new Error('repository must be a canonical HTTPS Git repository URL without credentials, query or fragment');
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(commit) || commit.includes('..')) {
    throw new Error('commit must be a branch, tag or commit SHA');
  }
  const sha = git(cwd, ['rev-parse', '--verify', `${commit}^{commit}`]);
  const timestamp = Number(git(cwd, ['show', '-s', '--format=%ct', sha]));
  const paths = new Set();
  const names = new Set();
  const plugins = catalog.plugins.map(({ path, ...display }) => {
    if (!/^plugins\/[a-z0-9][a-z0-9-]*$/.test(path) || paths.has(path)) {
      throw new Error(`invalid or duplicate plugin path: ${path}`);
    }
    paths.add(path);
    // Read the pinned tree, never label uncommitted working files as a published Git version.
    const pkg = JSON.parse(git(cwd, ['show', `${sha}:${path}/package.json`]));
    if (names.has(pkg.name)) throw new Error(`duplicate package name: ${pkg.name}`);
    names.add(pkg.name);
    const patch = pkg.dsh?.bundle?.patch;
    if (typeof patch !== 'string') throw new Error(`${path}: missing DSH bundle patch`);
    for (const entry of [pkg.main, patch, 'README.md', ...Object.values(pkg.exports ?? {})]) {
      if (typeof entry !== 'string' || entry.includes('..') || /^(?:\/|[A-Za-z]:)/.test(entry)) {
        throw new Error(`${path}: unsupported or unsafe package entry`);
      }
      git(cwd, ['cat-file', '-e', `${sha}:${path}/${entry.replace(/^\.\//, '')}`]);
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
  });
  return { format: 1, title: catalog.title, description: catalog.description, metadata: catalog.metadata, plugins };
}

export async function validateIndex(index, validatorPath) {
  if (!validatorPath) throw new Error('Set DSH_MARKET_INDEX_MODULE or pass --validator with the installed official dsh-plugin-market-index/lib/index.js path');
  const { parseMarketIndex, marketInstallTarget } = await import(pathToFileURL(resolve(validatorPath)));
  const parsed = parseMarketIndex(index, 'https://market.invalid/index.json');
  return parsed.plugins.map(plugin => ({ name: plugin.name, ...marketInstallTarget(plugin.name, plugin.versions[0]) }));
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
  // Also verify saved index versions and display fields against their pinned Git trees.
  if (values.check) {
    const source = index.plugins[0]?.versions[0]?.source;
    if (!source) throw new Error('Index is empty');
    const expected = createMarketIndex({ catalog, repository: source.url, commit: source.commit });
    if (JSON.stringify(expected) !== JSON.stringify(index)) throw new Error('Index differs from catalog or pinned manifests; regenerate it');
  } else {
    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, `${JSON.stringify(index, null, 2)}\n`);
  }
  console.log(JSON.stringify({ file: output, plugins: targets, remoteAvailability: 'not-checked' }, null, 2));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
