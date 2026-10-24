import { apply } from '../lib/index.js';
import { nodeGit } from './helpers.mjs';

/** DSH public seams backed by real Git, used by API and browser integration tests. */
export function host(config = {}, runner = nodeGit) {
  const events = new Map(), routes = new Map(), disposers = [], warnings = [];
  const ctx = {
    logger: { warn: message => warnings.push(message) }, fs: { processPath: target => target },
    on(event, listener) { const list = events.get(event) ?? []; list.push(listener); events.set(event, list); return () => list.splice(list.indexOf(listener), 1); },
    effect: fn => { const dispose = fn(); if (dispose) disposers.push(dispose); },
    connection: { fetch: { register: value => routes.set(value.path, value) } },
    subprocess: {
      resolveExecutable: async () => 'git',
      spawn(spec) {
        let result;
        const done = runner(spec.argv.slice(1), { cwd: spec.cwd, input: spec.stdio.stdin === 'ignore' ? undefined : spec.stdio.stdin.data,
          signal: spec.signal, env: spec.env, maxBytes: spec.stdio.stdout.maxBytes }).then(value => { result = value; return { exitCode: value.code, signal: null }; });
        return { done, collected: { stdout: { readFrom: () => ({ text: result.stdout, lossy: false }) }, stderr: { readFrom: () => ({ text: result.stderr, lossy: false }) } } };
      },
    },
  };
  apply(ctx, { refreshMs: 250, ...config });
  return {
    events, routes, warnings, context: ctx,
    emit: (event, ...args) => Promise.all((events.get(event) ?? []).map(fn => fn(...args))),
    request: (action, query = {}) => routes.get('/api/juzi.changes.' + action).fetch(new Request('http://127.0.0.1/api/juzi.changes.' + action + '?' + new URLSearchParams(query))),
    async dispose() { for (const fn of disposers.reverse()) await fn(); },
  };
}
