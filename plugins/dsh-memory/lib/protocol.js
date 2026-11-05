import { createHash, createHmac } from 'node:crypto';
import path from 'node:path';

export const SOURCE = 'juzi-memory';
export const digest = value => createHash('sha256').update(typeof value === 'string' ? value : canonical(value)).digest('hex');
export function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(item => item === undefined ? 'null' : canonical(item)).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).filter(key => value[key] !== undefined).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
export function sign(key, scope, args) {
  const { signature, ...payload } = args;
  return createHmac('sha256', key).update(canonical({ scope_id: scope, ...payload })).digest('hex');
}
export function projectId(value) {
  if (typeof value !== 'string' || !/^[a-z0-9][a-z0-9._-]{0,95}$/u.test(value)) throw Error('invalid_project_id');
  return value;
}
const normalized = value => path.resolve(value).replaceAll('\\', '/').replace(/\/$/u, '').toLowerCase();
export function scopeFor(session, settings) {
  if (!session || session.header.origin === 'subagent' || session.header.delegationDepth > 0) throw Error('session_not_eligible');
  if (settings.globalSessions.includes(session.id)) return 'global';
  const cwd = session.header.cwd && normalized(session.header.cwd);
  const matches = cwd ? settings.bindings.filter(b => cwd === normalized(b.root) || cwd.startsWith(normalized(b.root) + '/')).sort((a, b) => b.root.length - a.root.length) : [];
  if (matches.length) return `project:${projectId(matches[0].project_id)}`;
  throw Error('project_not_bound');
}
export function validateSettings(value) {
  const defaults = { autoCapture: false, autoRecall: false, includeGlobal: false, budget: 4000, bindings: [], globalSessions: [] };
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k => !Object.hasOwn(defaults, k))) throw Error('invalid_settings');
  const out = { ...defaults, ...value };
  for (const key of ['autoCapture', 'autoRecall', 'includeGlobal']) if (typeof out[key] !== 'boolean') throw Error('invalid_settings');
  if (!Number.isInteger(out.budget) || out.budget < 256 || out.budget > 16000 || !Array.isArray(out.bindings) || out.bindings.length > 200 || !Array.isArray(out.globalSessions) || out.globalSessions.length > 200) throw Error('invalid_settings');
  const seen = new Set();
  for (const b of out.bindings) {
    if (!b || Object.keys(b).some(k => !['root','project_id'].includes(k)) || typeof b.root !== 'string' || !path.isAbsolute(b.root)) throw Error('invalid_project_binding');
    projectId(b.project_id);
    if (seen.has(normalized(b.root))) throw Error('duplicate_project_binding');
    seen.add(normalized(b.root));
  }
  if (out.globalSessions.some(id => typeof id !== 'string' || !id || id.length > 200)) throw Error('invalid_global_binding');
  return structuredClone(out);
}
export const messageText = message => (message?.content ?? []).filter(block => block.type === 'text').map(block => block.text).join('\n');
const bounded = (text, max = 12000) => text.length <= max ? text : text.slice(0, max / 2 - 30) + '\n[…Host片段预算截断…]\n' + text.slice(-max / 2 + 30);
export function captureEvents(session, turn) {
  const events = session.snapshotEvents();
  const start = events.find(e => e.type === 'turn/start' && e.data.turn === turn);
  const end = events.find(e => e.type === 'turn/end' && e.data.turn === turn);
  if (!start || !end) throw Error('turn_not_committed');
  const calls = new Map(events.filter(e => e.type === 'tool/call').map(e => [e.data.callId, e.data.name]));
  const result = [];
  for (const e of events) {
    if (e.seq < start.seq || e.seq > end.seq || !session.isOwnSeq(e.seq)) continue;
    const base = { event_id: `seq:${e.seq}`, timestamp: new Date(e.time).toISOString() };
    if (e.type === 'user/message' && e.data.source?.kind === 'user') result.push({ ...base, role: 'user', text: bounded(messageText(e.data)), kind: 'message' });
    if (e.type === 'assistant/message') result.push({ ...base, role: 'assistant', text: bounded(messageText(e.data.message)), kind: 'message' });
    if (e.type === 'tool/call') {
      if (!isMemoryTool(e.data.name)) result.push({ ...base, role: 'assistant', text: bounded(e.data.arguments), kind: 'tool_call', call_id: e.data.callId, tool: e.data.name });
    }
    if (e.type === 'tool/result' && !isMemoryTool(calls.get(e.data.message.toolCallId))) result.push({ ...base, role: 'tool', text: bounded(messageText(e.data.message)), kind: 'tool_result', call_id: e.data.message.toolCallId, tool: calls.get(e.data.message.toolCallId), outcome: { is_error: e.data.message.isError === true } });
    if (e.type === 'tool/ptc-dispatch-start' && !isMemoryTool(e.data.name)) result.push({ ...base, role: 'assistant', text: bounded(canonical({ arguments: e.data.arguments, parent_call_id: e.data.parentCallId, root_call_id: e.data.rootCallId })), kind: 'tool_call', call_id: e.data.subCallId, tool: e.data.name });
    if (e.type === 'tool/ptc-dispatch' && !isMemoryTool(e.data.name)) result.push({ ...base, role: 'tool', text: bounded(messageText(e.data)), kind: 'tool_result', call_id: e.data.subCallId, tool: e.data.name, outcome: { is_error: e.data.isError === true } });
  }
  return result.filter(event => !/"origin"\s*:\s*"localmemory"|<localmemory-context\b/u.test(event.text));
}
export const isMemoryTool = name => /^memory_(query|get|remember|correct|forget|feedback)$/u.test(name) || /^mcp__juzi-memory-/u.test(name);
export function captureBatches(session, turn, scope) {
  const events = captureEvents(session, turn), batches = [];
  let chunk = [], bytes = 0;
  const commit = () => {
    if (chunk.length) batches.push({ request_id: `dsh:${digest({ session: session.id, turn, scope, events: chunk })}`, session_id: session.id, derive: true, events: chunk });
    chunk = []; bytes = 0;
  };
  for (const event of events) {
    const size = Buffer.byteLength(JSON.stringify(event));
    if (chunk.length === 128 || bytes + size > 1024 * 1024) commit();
    chunk.push(event); bytes += size;
  }
  commit();
  return batches;
}
// Replace only live plugin-owned surface nodes; the original event log remains intact.
export function clearSnapshots(session, createMessage) {
  let changed = false;
  for (const seq of [...session.surface.nodes]) {
    const event = session.eventAt(seq);
    if (event?.type !== 'user/message' || event.data.source?.kind !== SOURCE || !messageText(event.data)) continue;
    session.append('user/message', createMessage({ content: [], source: { kind: SOURCE, form: 'snapshot', sections: [] } }), { surfaceOp: { op: 'replace', startSeq: seq, endSeq: seq }, sourceEventSeqs: [seq] });
    changed = true;
  }
  return changed;
}
