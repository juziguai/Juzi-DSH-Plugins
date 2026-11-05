import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { digest, sign } from './protocol.js';

export class MemoryConnections {
  constructor(ctx, config, settings) {
    this.ctx = ctx; this.config = config; this.settings = settings; this.entries = new Map(); this.cleanups = new Set(); this.closed = false;
    this.key = randomBytes(32).toString('hex');
  }
  async connection(scope, signal) {
    if (this.closed) throw Error('connection_closed');
    if (!this.config.coreEntry || !this.config.memoryRoot) throw Error('connection_not_configured');
    if (!['global'].includes(scope) && !/^project:[a-z0-9][a-z0-9._-]{0,95}$/u.test(scope)) throw Error('invalid_scope');
    let entry = this.entries.get(scope);
    if (!entry) {
      if (this.entries.size >= 3) {
        const idle = [...this.entries.entries()].find(([, value]) => value.users === 0);
        if (!idle) throw Error('connection_capacity');
        this.entries.delete(idle[0]); await this.release(idle[1]);
      }
      entry = { users: 0, controller: new AbortController(), fibers: [] };
      this.entries.set(scope, entry);
      const timer = setTimeout(() => { entry.controller.abort(Error('memory_startup_timeout')); this.release(entry).catch(error => this.ctx.logger.warn(`memory: ${error.message}`)); }, this.config.timeoutMs);
      entry.ready = this.open(scope, entry).catch(async error => {
        const failure = entry.controller.signal.reason ?? new Error('memory_connection_failed', { cause: error });
        entry.controller.abort(failure);
        if (this.entries.get(scope) === entry) this.entries.delete(scope);
        await this.release(entry);
        throw failure;
      }).finally(() => clearTimeout(timer));
    }
    entry.users++;
    const combined = AbortSignal.any([entry.controller.signal, ...(signal ? [signal] : [])]);
    let stop;
    try {
      combined.throwIfAborted();
      await Promise.race([entry.ready, new Promise((_, reject) => { stop = () => reject(combined.reason); combined.addEventListener('abort', stop, { once: true }); })]);
      return entry;
    } catch (error) {
      entry.users--;
      if (!entry.users) {
        if (this.entries.get(scope) === entry) this.entries.delete(scope);
        this.release(entry).catch(e => this.ctx.logger.warn(`memory: ${e.message}`));
      }
      throw error;
    } finally { if (stop) combined.removeEventListener('abort', stop); }
  }
  async open(scope, entry) {
    const [{ default: SystemPrompt }, { default: ToolRuntime }, mcp] = await Promise.all([import('@deepseek-ai/dsh-system-prompt'), import('@deepseek-ai/dsh-tools'), import('@deepseek-ai/dsh-mcp-client')]);
    const context = this.ctx.isolate('tools').isolate('systemPrompt'); entry.context = context;
    const install = async (plugin, config) => { entry.controller.signal.throwIfAborted(); const fiber = context.plugin(plugin, config); entry.fibers.push(fiber); await fiber; };
    await install(SystemPrompt); await install(ToolRuntime, { mode: 'native' });
    const args = [this.config.coreEntry, 'mcp', '--root', this.config.memoryRoot, '--scope', scope];
    if (scope !== 'global' && this.settings.includeGlobal) args.push('--include-global');
    const env = { LOCALMEMORY_HOST_KEY: this.key };
    if (this.config.coreConfig) env.LOCALMEMORY_BRAIN_CONFIG = this.config.coreConfig;
    await install(mcp, { transport: 'stdio', serverName: 'juzi-memory-' + digest(scope).slice(0, 12), command: process.execPath, args, env, cwd: path.dirname(this.config.coreEntry), toolCallTimeoutMs: this.config.timeoutMs,
      failOnStartupError: true, reconnect: { enabled: true, initialDelayMs: 100, maxDelayMs: 1000, maxAttempts: 2 } });
    // The calling plugin already injects the root tools service. get() reads
    // this isolated service instead of its inherited injection snapshot.
    entry.tools = context.get('tools');
    entry.controller.signal.throwIfAborted();
  }
  async schemas(scope = 'global', { releaseAfter = false } = {}) {
    const entry = await this.connection(scope);
    try { return entry.tools.schemas(); } finally {
      entry.users--;
      if (releaseAfter && !entry.users && this.entries.get(scope) === entry) { this.entries.delete(scope); await this.release(entry); }
    }
  }
  async call(scope, operation, args = {}, signal) {
    const entry = await this.connection(scope, signal);
    try {
      const combined = AbortSignal.any([entry.controller.signal, ...(signal ? [signal] : []), AbortSignal.timeout(this.config.timeoutMs)]);
      combined.throwIfAborted();
      const tool = entry.tools.schemas().find(s => s.parameters?.title === `localmemory.${operation}`);
      if (!tool) throw Error('incompatible_core_contract');
      const parameters = operation === 'capture' ? { ...args, signature: sign(this.key, scope, args) } : args;
      const result = await entry.tools.execute({ callId: `memory-${digest({ scope, operation, args }).slice(0, 24)}`, name: tool.name, arguments: parameters, signal: combined });
      if (result.isError) {
        const text = [result.error?.message ?? '', ...(result.content ?? []).filter(c => c.type === 'text').map(c => c.text)].join('\n');
        const code = /^([a-z][a-z0-9]*(?:_[a-z0-9]+)+)(?::[a-zA-Z0-9_.:-]+)?$/mu.exec(text)?.[1]
          ?? /MCP error -?\d+:\s*([a-z][a-z0-9_]+)/u.exec(text)?.[1]
          ?? /"reason"\s*:\s*"([a-z][a-z0-9_]+)"/u.exec(text)?.[1];
        throw Error(code ?? (combined.aborted ? 'memory_timeout_or_cancelled' : 'memory_call_failed'));
      }
      const value = result.value?.structuredContent;
      if (!value || typeof value !== 'object') throw Error('incompatible_core_response');
      return value;
    } finally { entry.users--; }
  }
  release(entry) {
    if (entry.releasing) return entry.releasing;
    entry.releasing = Promise.resolve().then(async () => {
      entry.controller.abort();
      for (const fiber of entry.fibers.splice(0).reverse()) await fiber.dispose();
    });
    this.cleanups.add(entry.releasing);
    entry.releasing.finally(() => this.cleanups.delete(entry.releasing)).catch(error => this.ctx.logger.warn(`memory: ${error.message}`));
    return entry.releasing;
  }
  async dispose() {
    this.closed = true;
    const entries = [...this.entries.values()]; this.entries.clear();
    for (const entry of entries) entry.controller.abort();
    await Promise.allSettled(entries.map(entry => entry.ready));
    await Promise.all(entries.map(entry => this.release(entry)));
    await Promise.all([...this.cleanups]);
  }
}
