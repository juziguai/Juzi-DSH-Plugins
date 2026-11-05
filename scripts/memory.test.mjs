import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { MemoryHost, configOf } from '../plugins/dsh-memory/lib/index.js';
import { validateSettings, scopeFor, captureBatches, sign, SOURCE } from '../plugins/dsh-memory/lib/protocol.js';

function fixture(fn) {
  const root = mkdtempSync(path.join(os.tmpdir(), 'juzi-memory-'));
  const events = [], nodes = [], calls = []; let revision = 1, durable = true, contextValue;
  const session = { id: 'native-session', header: { cwd: path.join(root, 'Atlas') }, surface: { nodes }, snapshotEvents: () => [...events], isOwnSeq: seq => seq >= 0, eventAt: seq => events.find(e => e.seq === seq),
    append(type, data, options) { const event = { type, data, seq: events.length, time: 1793710000000 + events.length }; events.push(event); if (options?.surfaceOp) { if (typeof options.surfaceOp === 'object') nodes.splice(nodes.indexOf(options.surfaceOp.startSeq), 1); nodes.push(event.seq); } return event; } };
  const message = text => ({ id: 'user-1', role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text }] });
  const pool = { disposed: false, async call(scope, operation, args, signal) { calls.push({ scope, operation, args }); signal?.throwIfAborted();
    if (operation === 'revision') return { revision: [{ scope_id: scope, revision }] };
    if (operation === 'context') return contextValue ? contextValue(scope) : { evaluated_at: new Date(Date.now()).toISOString(), next_change_at: null, text: '<localmemory-context>old-fact</localmemory-context>', items: [{ id: 'fact:1', scope_id: scope, version: revision, title: '合成约定' }], revision: [{ scope_id: scope, revision }] };
    if (operation === 'capture') return { ok: true, evidence: args.events.map(e => ({ event_id: e.event_id })), candidates: { candidates: 1 } };
    return { ok: true }; }, async dispose() { this.disposed = true; } };
  const ctx = { sessions: { get: id => id === session.id ? session : undefined, list: () => [session], flush: async () => durable }, logger: { warn() {} } };
  const stateFile = path.join(root, 'settings.json');
  const host = new MemoryHost(ctx, { initialSettings: { autoRecall: true, autoCapture: false, bindings: [{ root: session.header.cwd, project_id: 'atlas-a' }] } }, { stateFile, createMessage: data => ({ ...data, role: 'user', id: 'injected-' + events.length }), appendRecord: (s, type, data) => s.append(type, data), connections: () => pool });
  const begin = turn => host.onEvent(session,session.append('turn/start',{turn}));
  return Promise.resolve().then(() => fn({ root, host, ctx, session, pool, calls, message, events, nodes, stateFile, begin, setContext: value => { contextValue = value; }, setRevision: n => { revision = n; }, setDurable: value => { durable = value; } })).finally(async () => { await host.dispose(); rmSync(root, { recursive: true, force: true }); });
}

test('trusted root binding distinguishes same-named projects and explicit global selection', () => {
  const a = path.resolve('a/Atlas'), b = path.resolve('b/Atlas');
  const settings = validateSettings({ bindings: [{ root: a, project_id: 'one' }, { root: b, project_id: 'two' }] });
  assert.equal(scopeFor({ id: 's', header: { cwd: a } }, settings), 'project:one');
  assert.equal(scopeFor({ id: 's', header: { cwd: b } }, settings), 'project:two');
  assert.throws(() => scopeFor({ id: 's', header: { cwd: path.resolve('c/Atlas') } }, settings), /project_not_bound/);
  assert.equal(scopeFor({ id: 's', header: { cwd: a } }, { ...settings, globalSessions: ['s'] }), 'global');
  assert.throws(() => validateSettings({ bindings: [{ root: a, project_id: 'one' }, { root: a, project_id: 'two' }] }), /duplicate_project_binding/);
  assert.throws(() => configOf({ coreEntry: 'relative.js' }), /absolute_host_path/);
});

test('same input only recalls once; revisions refresh; old owned snapshots leave the next request', () => fixture(async f => {
  const { host, session, message, calls, setRevision } = f;
  f.begin(1);
  const payload = { agent: { session }, turn: 1, step: 1, messages: [message('查询合成约定')], signal: new AbortController().signal };
  const next = async () => ({ kind: 'enter', messages: payload.messages });
  const first = await host.preStep(payload, next);
  assert.equal(first.messages.length, 2);
  session.append('user/message', first.messages[1], { surfaceOp: 'append' });
  const oldSeq = session.surface.nodes[0];
  const second = await host.preStep({ ...payload, step: 2, messages: [] }, async () => ({ kind: 'enter', messages: [] }));
  assert.equal(calls.filter(c => c.operation === 'context').length, 1);
  assert(session.surface.nodes.includes(oldSeq));
  assert.equal(second.messages.length, 0);
  assert.equal(session.eventAt(oldSeq).data.content[0].text.includes('old-fact'), true);
  setRevision(2); await host.preStep({ ...payload, step: 3, messages: [] }, async () => ({ kind: 'enter', messages: [] }));
  assert(!session.surface.nodes.includes(oldSeq));
  assert.equal(calls.filter(c => c.operation === 'context').length, 2);
  await host.updateSettings({ autoRecall: false });
  const off = await host.preStep(payload, next);
  assert.equal(off.messages.length, 1);
}));

test('recall error keeps ordinary conversation usable and never accepts a planned injection', () => fixture(async f => {
  f.begin(1);
  f.pool.call = async () => { throw Error('memory_timeout_or_cancelled'); };
  const ordinary = f.message('继续正常对话'); let downstream = 0;
  const result = await f.host.preStep({ agent: { session: f.session }, turn: 1, messages: [ordinary], signal: new AbortController().signal }, async () => { downstream++; return { kind: 'enter', messages: [ordinary] }; });
  assert.equal(downstream, 1); assert.deepEqual(result.messages, [ordinary]);
  assert.equal(f.host.status(f.session.id).recall_error, 'memory_timeout_or_cancelled');
  assert.equal(f.host.status(f.session.id).turns[0].injection, undefined);
}));

test('turn capture retains failed tool and final B; rejects undurable logs and replays identical keys', () => fixture(async f => {
  const { session, host, message } = f;
  const start = session.append('turn/start', { turn: 1 }); host.onEvent(session, start); await Promise.resolve();
  session.append('user/message', message('先尝试A'), { surfaceOp: 'append' });
  session.append('tool/call', { turn: 1, callId: 'verify', name: 'shell', arguments: '{"cmd":"verify A"}' });
  session.append('tool/result', { turn: 1, message: { toolCallId: 'verify', isError: true, content: [{ type: 'text', text: 'A failed' }] } }, { surfaceOp: 'append' });
  session.append('user/message', { ...message('最终决定B'), id: 'user-b' }, { surfaceOp: 'append' });
  session.append('user/message', { ...message('DO-NOT-REIMPORT'), source: { kind: SOURCE } }, { surfaceOp: 'append' });
  session.append('tool/call', { turn: 1, callId: 'memory', name: 'memory_query', arguments: '{}' });
  session.append('tool/result', { turn: 1, message: { toolCallId: 'memory', content: [{ type: 'text', text: 'DO-NOT-REIMPORT' }] } }, { surfaceOp: 'append' });
  session.append('turn/end', { turn: 1, reason: 'completed' });
  f.setDurable(false); await assert.rejects(host.captureTurn(session, 1), /session_not_durable/); assert.equal(f.calls.length, 0);
  f.setDurable(true); await host.captureTurn(session, 1); await host.captureTurn(session, 1);
  assert.deepEqual(f.calls[0], f.calls[1]);
  const events = f.calls[0].args.events;
  assert.deepEqual(events.map(e => e.role), ['user','assistant','tool','user']);
  assert.equal(events[2].outcome.is_error, true); assert.equal(events.at(-1).text, '最终决定B');
  assert.equal(events.some(e => e.text.includes('DO-NOT-REIMPORT')), false);
}));

test('browser cannot set paths, approve, broaden scope or mutate without expected version', () => fixture(async f => {
  const request = body => new Request('http://localhost/api', { method: 'POST', body: JSON.stringify(body) });
  await assert.rejects(f.host.route(request({ memoryRoot: 'C:/elsewhere' }), 'settings'), /invalid_parameters/);
  await assert.rejects(f.host.route(request({ binding: { session_id: f.session.id, project_id: 'x', root: 'C:/elsewhere' } }), 'settings'), /invalid_parameters/);
  await assert.rejects(f.host.route(new Request('http://localhost/api?scope=project:foreign&id=x'), 'get'), /scope_not_allowed/);
  await assert.rejects(f.host.route(request({ scope: 'project:atlas-a', id: 'x', confirm: true }), 'forget'), /expected_version_required/);
  await assert.rejects(f.host.route(request({ scope: 'project:atlas-a', id: 'x', confirm: true, expected_version: 1, authorized: true }), 'forget'), /invalid_parameters/);
  await f.host.updateSettings({ binding: { session_id: f.session.id, project_id: 'bound' }, autoCapture: true });
  const saved = JSON.parse(readFileSync(f.stateFile, 'utf8'));
  assert.equal(saved.bindings[0].root, f.session.header.cwd); assert.equal(f.host.scope(f.session), 'project:bound');
  assert(!JSON.stringify(f.host.status()).includes(f.root));
}));

test('stable native batches and HMAC distinguish scopes and changed evidence', () => fixture(async f => {
  f.session.append('turn/start', { turn: 1 });
  for (let i = 0; i < 130; i++) f.session.append('user/message', { ...f.message('原始证据' + i), id: 'u' + i }, { surfaceOp: 'append' });
  f.session.append('turn/end', { turn: 1, reason: 'completed' });
  const a = captureBatches(f.session, 1, 'project:a'), b = captureBatches(f.session, 1, 'project:b');
  assert.deepEqual(a.map(x => x.events.length), [128, 2]); assert.notEqual(a[0].request_id, b[0].request_id);
  assert.notEqual(sign('test-only', 'project:a', a[0]), sign('test-only', 'project:b', a[0]));
}));

test('large UTF-8 evidence stays within the MCP wire budget and orphan results remain experiences', () => fixture(async f => {
  f.session.append('turn/start', { turn: 1 });
  for (let i = 0; i < 100; i++) f.session.append('user/message', { ...f.message('证'.repeat(12000)), id: 'u' + i }, { surfaceOp: 'append' });
  f.session.append('tool/result', { turn: 1, message: { toolCallId: 'missing-call', isError: true, content: [{ type: 'text', text: '原调用缺失，但失败结果不能丢弃。' }] } }, { surfaceOp: 'append' });
  f.session.append('turn/end', { turn: 1, reason: 'completed' });
  const batches = captureBatches(f.session, 1, 'project:a');
  assert(batches.length > 1);
  assert.equal(batches.flatMap(b => b.events).length, 101);
  assert(batches.every(b => Buffer.byteLength(JSON.stringify(b)) < 1100000));
  assert.equal(batches.at(-1).events.at(-1).call_id, 'missing-call');
}));

test('native PTC subcalls retain pairing and parent evidence while memory echoes do not flow back', () => fixture(async f => {
  f.session.append('turn/start', { turn: 1 });
  const call = { rootCallId: 'root', parentCallId: 'parent', subCallId: 'sub', name: 'shell', arguments: { cmd: 'verify A' } };
  f.session.append('tool/ptc-dispatch-start', call);
  f.session.append('tool/ptc-dispatch', { ...call, isError: true, content: [{ type: 'text', text: 'A failed' }] });
  f.session.append('tool/result', { turn: 1, message: { toolCallId: 'root', content: [{ type: 'text', text: '{"origin":"localmemory","title":"不要回流"}' }] } }, { surfaceOp: 'append' });
  f.session.append('turn/end', { turn: 1, reason: 'completed' });
  const events = captureBatches(f.session, 1, 'project:a').flatMap(b => b.events);
  assert.equal(events.length, 2);
  assert.equal(events[0].call_id, events[1].call_id);
  assert.equal(JSON.parse(events[0].text).parent_call_id, 'parent');
  assert.equal(events[1].outcome.is_error, true);
}));

test('concurrent rebindings pin recall, model tools and capture until the next native turn', () => fixture(async f => {
  const {host,session,pool,calls}=f; f.begin(1);
  session.append('user/message',f.message('项目约定使用当前回合范围。'),{surfaceOp:'append'});
  let release, entered;
  const blocked=new Promise(resolve=>{release=resolve;}), ready=new Promise(resolve=>{entered=resolve;});
  const original=pool.call.bind(pool);
  pool.call=async (...args)=>{if(args[1]==='context'){entered();await blocked;}return original(...args);};
  const payload={agent:{session},turn:1,messages:[f.message('项目约定')],signal:new AbortController().signal};
  const recall=host.preStep(payload,async()=>({kind:'enter',messages:payload.messages}));
  await ready;
  await Promise.all(['atlas-b','atlas-c'].map(project_id=>host.updateSettings({binding:{session_id:session.id,project_id}})));
  await host.modelTool('remember',{title:'本轮约定',content:'本轮约定必须归入原项目。'},{agent:{session},callId:'write-a',signal:payload.signal});
  const status=host.status(session.id); assert.equal(status.scope_id,'project:atlas-a');assert.equal(status.next_scope_id,'project:atlas-c');
  release(); const recalled=await recall;assert.equal(recalled.messages.at(-1).source.sections[0].items[0].scope_id,'project:atlas-a');
  session.append('turn/end',{turn:1,reason:'completed'});await host.captureTurn(session,1);
  assert(calls.every(call=>call.scope==='project:atlas-a'));
  assert(host.visibleScopes().includes('project:atlas-a'));
  await assert.rejects(host.modelTool('query',{}, {agent:{session}}),/requires_active_turn/);
  f.begin(2);session.append('user/message',{...f.message('下一回合使用新范围。'),id:'u2'},{surfaceOp:'append'});
  const offset=calls.length;
  await host.preStep({...payload,turn:2},async()=>({kind:'enter',messages:payload.messages}));
  await host.modelTool('query',{query:'约定'},{agent:{session},signal:payload.signal});
  session.append('turn/end',{turn:2,reason:'completed'});await host.captureTurn(session,2);
  assert(calls.slice(offset).every(call=>call.scope==='project:atlas-c'));
  host.states.delete(session.id);
  assert.equal(host.scopeForTurn(session,1),'project:atlas-a','restored log retains the original binding');
}));

test('missing trusted turn binding rejects model tools without writing or guessing settings', () => fixture(async f => {
  f.session.append('turn/start',{turn:1});
  await assert.rejects(f.host.modelTool('remember',{title:'x',content:'x'},{agent:{session:f.session}}),/turn_binding_missing/);
  assert.equal(f.calls.length,0);
}));

test('time boundaries refresh expiry and empty-cache future activation without revision changes', () => fixture(async f => {
  const originalNow=Date.now; let now=originalNow(), start=now;
  Date.now=()=>now;
  try {
    f.begin(1);
    f.setContext(scope=>{
      const name=now<start+1000?'expiring':now>=start+2000&&now<start+3000?'future':null;
      return {evaluated_at:new Date(now).toISOString(),next_change_at:now<start+1000?new Date(start+1000).toISOString():now<start+2000?new Date(start+2000).toISOString():now<start+3000?new Date(start+3000).toISOString():null,
        text:name?`<localmemory-context>${name}</localmemory-context>`:'',items:name?[{id:name,scope_id:scope,version:1,title:name}]:[],revision:[{scope_id:scope,revision:1}]};
    });
    const payload={agent:{session:f.session},turn:1,messages:[f.message('时效约定')],signal:new AbortController().signal};
    const step=async()=>f.host.preStep(payload,async()=>({kind:'enter',messages:payload.messages}));
    const first=await step();f.session.append('user/message',first.messages[1],{surfaceOp:'append'});const old=f.nodes.at(-1);
    now=start+1500;assert.equal((await step()).messages.length,1);assert(!f.nodes.includes(old));
    assert.match(f.session.eventAt(old).data.content[0].text,/expiring/,'original host history remains');
    now=start+2500;const activated=await step();assert.match(activated.messages[1].content[0].text,/future/);
    f.session.append('user/message',activated.messages[1],{surfaceOp:'append'});const future=f.nodes.at(-1);
    now=start+3000;assert.equal((await step()).messages.length,1);assert(!f.nodes.includes(future));
    assert.equal(f.calls.filter(call=>call.operation==='context').length,4);
  } finally {Date.now=originalNow;}
}));

test('expiry during downstream preparation removes owned snapshots before use', () => fixture(async f => {
  const originalNow=Date.now;let now=originalNow();Date.now=()=>now;
  try {
    f.begin(1);const end=now+100;
    f.setContext(scope=>({evaluated_at:new Date(now).toISOString(),next_change_at:new Date(end).toISOString(),text:'expired',items:[{id:'x',scope_id:scope}],revision:[]}));
    const input=f.message('时效约定');
    const result=await f.host.preStep({agent:{session:f.session},turn:1,messages:[input],signal:new AbortController().signal},async()=>{now=end;return {kind:'enter',messages:[input]};});
    assert.deepEqual(result.messages,[input]);assert.equal(f.host.status(f.session.id).recall_error,'context_expired_before_use');
  } finally {Date.now=originalNow;}
}));

test('partial capture remains retryable with the same request key and distinct derivation progress', () => fixture(async f => {
  f.begin(1);f.session.append('user/message',f.message('项目约定需要分批提炼。'),{surfaceOp:'append'});f.session.append('turn/end',{turn:1,reason:'completed'});
  const original=f.pool.call.bind(f.pool);let attempts=0;
  f.pool.call=async (...args)=>{const value=await original(...args);if(args[1]!=='capture')return value;return {...value,status:++attempts===1?'partial':'committed',capture_status:'committed',derivation:{complete:attempts>1,pending:attempts===1?2:0}};};
  assert.equal((await f.host.captureTurn(f.session,1)).status,'partial');assert.equal(f.host.status(f.session.id).turns[0].capture,'partial');
  assert.equal((await f.host.captureTurn(f.session,1)).status,'committed');
  assert.deepEqual(f.calls[0].args,f.calls[1].args);
  assert.equal(f.host.status(f.session.id).turns[0].receipts[0].derivation.complete,true);
}));

test('Host cleanup retains its acquired session service after the injected context is revoked', () => fixture(async f => {
  let flushed=0;f.ctx.sessions.flush=async()=>{flushed++;return true;};
  f.session.append('user/message',{...f.message('owned-memory'),source:{kind:SOURCE}},{surfaceOp:'append'});
  Object.defineProperty(f.ctx,'sessions',{get(){throw Error('inactive_context');}});
  await f.host.dispose();assert.equal(f.pool.disposed,true);assert.equal(flushed,1);
  assert(f.nodes.every(seq=>!f.session.eventAt(seq).data.content.length));
}));

test('status keeps the accepted injection in history after the active snapshot expires', () => fixture(async f => {
  const {host,session,message}=f;
  f.begin(1);
  const expires=Date.now()+30000;
  f.setContext(scope=>({evaluated_at:new Date().toISOString(),next_change_at:new Date(expires).toISOString(),text:'accepted snapshot',items:[{id:'fact:1',scope_id:scope,title:'旧约定',version:1}],revision:[]}));
  const first=await host.preStep({agent:{session},turn:1,step:1,messages:[message('查询旧约定')],signal:new AbortController().signal},async()=>({kind:'enter',messages:[]}));
  const event=session.append('user/message',first.messages[0],{surfaceOp:'append'});
  host.onEvent(session,event);
  assert.equal(host.status(session.id).current_injection.message_id,event.data.id);
  const now=Date.now;
  try {
    Date.now=()=>expires+1;
    const status=host.status(session.id);
    assert.equal(status.current_injection,null);
    assert.equal(status.turns[0].injection.message_id,event.data.id);
    assert.equal(session.eventAt(event.seq).data.content[0].text,'accepted snapshot');
  } finally { Date.now=now; }
}));

test('turn capture reports disabled after completion and rejects a concurrent retry', () => fixture(async f => {
  const {host,session,message}=f;
  f.begin(1);
  session.append('user/message',message('需要保留证据的正文'),{surfaceOp:'append'});
  host.onEvent(session,session.append('turn/end',{turn:1}));
  assert.equal(host.status(session.id).turns[0].capture,'disabled');
  assert.equal(f.calls.length,0);
  let release;
  const resume=new Promise(resolve=>{release=resolve;});
  const original=f.pool.call.bind(f.pool);
  f.pool.call=async (...args)=>{await resume;return original(...args);};
  const capture=host.captureTurn(session,1);
  try {
    assert.equal(host.status(session.id).turns[0].capture,'capturing');
    await assert.rejects(host.captureTurn(session,1),/capture_in_progress/);
  } finally { release(); }
  assert.equal((await capture).status,'committed');
  assert.equal(f.calls.length,1);
}));
