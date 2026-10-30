import test,{after} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,dirname,basename} from 'node:path';
import {execFileSync} from 'node:child_process';
import {Script} from 'node:vm';
import {gate,fingerprint,materialize,mergeIndex,withLock,deployPackages,json,save,normalizedSpec,digest,command,verifyFiles} from './release-core.mjs';
import {readBlobs} from './git-source.mjs';
import {openHost} from './release-host.mjs';
import {withTiming,timingReport,summarizeTimings} from './release-timing.mjs';

const parent=await realpath(tmpdir()),directory=await mkdtemp(join(parent,'juzi-release-test-'));
after(async()=>{const target=resolve(directory);assert.equal(dirname(target),parent);assert.ok(basename(target).startsWith('juzi-release-test-'));await rm(target,{recursive:true,force:true});});
let sequence=0;
async function fixture(){const path=join(directory,String(++sequence));await mkdir(path);return path;}

test('validation runs once for identical inputs, and invalidates on changes or refresh',async()=>{
  const path=await fixture();let key='one',runs=0;
  const options={directory:path,key:'suite',inputs:async()=>key,run:async log=>{runs++;await writeFile(log,'passed '+runs);return {elapsedMs:5};}};
  assert.equal((await gate(options)).reused,false);
  assert.equal((await gate(options)).reused,true);assert.equal(runs,1);
  key='two';assert.equal((await gate(options)).reused,false);
  await gate({...options,refresh:true});assert.equal(runs,3);
  await writeFile(join(path,'suite.log'),'tampered');await gate(options);assert.equal(runs,4);
});
test('failed or concurrent-input validation cannot leave a reusable success',async()=>{
  const path=await fixture();let input='same';
  const options={directory:path,key:'suite',inputs:async()=>input,run:async log=>{await writeFile(log,'pass');return {elapsedMs:1};}};
  await gate(options);
  await assert.rejects(gate({...options,refresh:true,run:async()=>{throw Error('failure');}}),/failure/);
  await assert.rejects(readFile(join(path,'suite.json')),/ENOENT/);
  await assert.rejects(gate({...options,run:async log=>{await writeFile(log,'pass');input='changed';return {elapsedMs:1};}}),/inputs changed/);
  await assert.rejects(readFile(join(path,'suite.json')),/ENOENT/);
});
test('run lock prevents a second writer and releases on failure',async()=>{
  const path=await fixture();
  await withLock(path,()=>assert.rejects(withLock(path,async()=>{}),/Another release process/));
  await assert.rejects(withLock(path,async()=>{throw Error('stop');}),/stop/);
  await withLock(path,async()=>{});
});

const env={...Object.fromEntries(Object.entries(process.env).filter(([k])=>!k.startsWith('GIT_'))),GIT_AUTHOR_NAME:'Release fixture',GIT_AUTHOR_EMAIL:'fixture@example.invalid',GIT_COMMITTER_NAME:'Release fixture',GIT_COMMITTER_EMAIL:'fixture@example.invalid'};
function git(cwd,args,input){return execFileSync('git',args,{cwd,env,input,encoding:'utf8',stdio:['pipe','pipe','pipe'],windowsHide:true}).trim();}
async function repository(){const cwd=await fixture();git(cwd,['init','--quiet','--object-format=sha1']);await mkdir(join(cwd,'plugins/p'),{recursive:true});await mkdir(join(cwd,'scripts'));await writeFile(join(cwd,'.gitignore'),'.codex/\nnode_modules/\n');await writeFile(join(cwd,'package.json'),'{}');await writeFile(join(cwd,'plugins/p/a.bin'),Buffer.from([0,1,2,10,255]));await writeFile(join(cwd,'scripts/a.mjs'),'export const a=1;');git(cwd,['add','.']);git(cwd,['-c','commit.gpgsign=false','commit','--quiet','-m','fixture']);return cwd;}
test('fingerprint covers untracked source, runtime contents and locks, and ignores docs',async()=>{
  const cwd=await repository(),runtime=join(cwd,'.codex/runtime');await mkdir(join(runtime,'node_modules/pkg'),{recursive:true});
  const entry=join(runtime,'node_modules/pkg/index.js');await writeFile(entry,'one');await writeFile(join(runtime,'package-lock.json'),'one');
  const environment={DSH_SLOT_CORE_MODULE:entry,PYTHON_ID:'python-one'};
  const initial=await fingerprint(cwd,environment);await writeFile(join(cwd,'notes.md'),'unrelated');assert.equal(await fingerprint(cwd,environment),initial);
  await writeFile(join(cwd,'scripts/new.mjs'),'new');const changed=await fingerprint(cwd,environment);assert.notEqual(changed,initial);
  await writeFile(entry,'two');const moduleChanged=await fingerprint(cwd,environment);assert.notEqual(moduleChanged,changed);
  await writeFile(join(runtime,'package-lock.json'),'two');assert.notEqual(await fingerprint(cwd,environment),moduleChanged);
  assert.notEqual(await fingerprint(cwd,{...environment,PYTHON_ID:'python-two'}),await fingerprint(cwd,environment));
  for(const key of ['DSH_CONVERSATION_BUNDLE','DSH_LAYOUT_SOURCE_FILE','DSH_LAYOUT_SHARES_MODULE']){
    const input=join(runtime,key+'.js');await writeFile(input,'one');const options={...environment,[key]:input},before=await fingerprint(cwd,options);
    await writeFile(input,'two');assert.notEqual(await fingerprint(cwd,options),before,key+' must invalidate on file changes');
  }
});
test('installed content permits only UTF-8 line-ending conversion and checks its saved source',async()=>{
  const source=await fixture(),installed=await fixture();const bytes=Buffer.from('one\ntwo\n');await writeFile(join(source,'a.js'),bytes);
  const pkg={name:'p',source,files:[{path:'a.js',sha256:digest(bytes)}]};
  await writeFile(join(installed,'a.js'),'one\r\ntwo\r\n');await verifyFiles(pkg,installed);
  await writeFile(join(installed,'a.js'),'changed');await assert.rejects(verifyFiles(pkg,installed),/mismatch/);
  await writeFile(join(source,'a.js'),'changed');await assert.rejects(verifyFiles(pkg,installed),/source changed/);
  const invalid=Buffer.from([0xff,10]);await writeFile(join(source,'a.js'),invalid);pkg.files[0].sha256=digest(invalid);await writeFile(join(installed,'a.js'),Buffer.from([0xfe,10]));await assert.rejects(verifyFiles(pkg,installed),/mismatch/);
});
test('committed source uses one binary-safe blob batch and ignores dirty working files',async()=>{
  const cwd=await repository(),sha=git(cwd,['rev-parse','HEAD']),output=await fixture();await writeFile(join(cwd,'plugins/p/a.bin'),'dirty');
  await materialize(cwd,sha,[{path:'plugins/p',output}]);assert.deepEqual(await readFile(join(output,'a.bin')),Buffer.from([0,1,2,10,255]));
  const blob=git(cwd,['hash-object','-w','--stdin'],'a.bin');git(cwd,['update-index','--add','--cacheinfo',`120000,${blob},plugins/p/link`]);git(cwd,['-c','commit.gpgsign=false','commit','--quiet','-m','symlink fixture']);
  await assert.rejects(materialize(cwd,git(cwd,['rev-parse','HEAD']),[{path:'plugins/p',output:await fixture()}]),/unsupported file or symlink/);
});

test('multiple committed packages are isolated and missing selections fail before writing',async()=>{
  const cwd=await repository(),first=await fixture(),second=await fixture();
  await mkdir(join(cwd,'plugins/q'));await writeFile(join(cwd,'plugins/q/other.bin'),Buffer.from([255,0,10]));git(cwd,['add','.']);git(cwd,['-c','commit.gpgsign=false','commit','--quiet','-m','second package']);
  const sha=git(cwd,['rev-parse','HEAD']);await writeFile(join(cwd,'plugins/q/other.bin'),'dirty');
  const selections=[{path:'plugins/p',output:first},{path:'plugins/q',output:second}];await materialize(cwd,sha,selections);
  assert.deepEqual(await readFile(join(first,'a.bin')),Buffer.from([0,1,2,10,255]));assert.deepEqual(await readFile(join(second,'other.bin')),Buffer.from([255,0,10]));
  await assert.rejects(readFile(join(first,'other.bin')),error=>error.code==='ENOENT');
  const untouched=await fixture();await assert.rejects(materialize(cwd,sha,[{path:'plugins/p',output:untouched},{path:'plugins/missing',output:second}]),/No committed plugin files/);
  await assert.rejects(readFile(join(untouched,'a.bin')),error=>error.code==='ENOENT');
  await assert.rejects(materialize(cwd,sha,[selections[0],selections[0]]),/unique/);
});

test('shared Git batches preserve empty and duplicate binary blobs and refuse non-blobs',async()=>{
  const cwd=await repository(),binary=Buffer.from([255,10,0,254]);
  const empty=git(cwd,['hash-object','-w','--stdin'],''),id=git(cwd,['hash-object','-w','--stdin'],binary);
  const result=readBlobs(cwd,[empty,id,id]);assert.equal(result.size,2);assert.equal(result.get(empty).length,0);assert.deepEqual(result.get(id),binary);
  assert.throws(()=>readBlobs(cwd,['0'.repeat(40)]),/batch mismatch/);
  assert.throws(()=>readBlobs(cwd,[git(cwd,['rev-parse','HEAD^{tree}'])]),/batch mismatch/);
});
test('selected market updates preserve unrelated pins and display metadata',()=>{
  const old={title:'market',plugins:[{name:'a',version:1},{name:'b',version:2}]};
  const merged=mergeIndex(old,{plugins:[{name:'a',version:3}]});assert.equal(merged.plugins[1],old.plugins[1]);assert.equal(merged.title,'market');assert.equal(merged.plugins[0].version,3);
});

async function deployment({disabled=false,failInstall=false,verifyFailure=false,alreadyInstalled=false}={}){
  const path=await fixture(),calls=[];
  const pkg={name:'@juzi/p',version:'2.0.0',installSpec:'git+https://github.com/example/repo.git#'+'a'.repeat(40)+'&path:/plugins/p'};
  const plan={packages:[pkg]},bundles=[{name:pkg.name,version:alreadyInstalled?pkg.version:'1.0.0',enabled:!disabled,error:null,dependency:alreadyInstalled?normalizedSpec(pkg.installSpec):'file:old'},{name:'other',version:'3.0.0',enabled:true,error:null}];
  let running=false,failVerify=verifyFailure;
  const adapter={snapshot:async()=>({running:running?['task']:[],bundles:structuredClone(bundles)}),
    disable:async()=>{calls.push('disable');bundles[0].enabled=false;return {application:'applied'};},
    install:async()=>{calls.push('install');bundles[0].version=pkg.version;bundles[0].dependency=normalizedSpec(pkg.installSpec);if(failInstall)throw Error('response lost');return {application:'applied'};},
    enable:async()=>{calls.push('enable');bundles[0].enabled=true;return {application:'applied'};}};
  const backup=async()=>{calls.push('backup');await writeFile(join(path,'backup'),'original');return [];};
  const verify=async()=>{assert.equal(bundles[0].version,pkg.version);assert.equal(bundles[0].enabled,!disabled);if(failVerify){failVerify=false;throw Error('verification interrupted');}};
  return {options:{plan,directory:path,adapter,backup,verify},calls,bundles,pkg,path,setRunning:value=>{running=value;}};
}
test('deployment backs up first, advances all phases and becomes a no-op on resume',async()=>{
  const x=await deployment();const state=await deployPackages(x.options);assert.equal(state.status,'verified');assert.deepEqual(x.calls,['backup','disable','install','enable']);
  for(const phase of state.completed)assert.ok(Date.parse(phase.finishedAt)>=Date.parse(phase.startedAt));
  await deployPackages(x.options);assert.deepEqual(x.calls,['backup','disable','install','enable']);assert.equal(x.bundles[1].version,'3.0.0');
});

test('timing persists success, failure and reuse without repeating completed deployment writes',async()=>{
  const x=await deployment(),quiet={report:()=>{}};
  await withTiming(x.path,'deploy',measure=>deployPackages({...x.options,measure}),quiet);
  await withTiming(x.path,'deploy',measure=>deployPackages({...x.options,measure}),quiet);
  await assert.rejects(withTiming(x.path,'pack',async measure=>measure('source-check',async()=>{throw Error('fixture failure');}),quiet),/fixture failure/);
  await withTiming(x.path,'prepare',measure=>measure('npm-test',async()=>({reused:true})),quiet);
  const summary=await timingReport(x.path);assert.deepEqual(summary.runs.map(r=>r.status),['completed','completed','failed','completed']);
  assert.deepEqual(summary.runs[0].stages.map(s=>s.phase),['backup','deploy:@juzi/p:disable','deploy:@juzi/p:install','deploy:@juzi/p:enable']);
  assert.deepEqual(summary.runs[1].stages,[]);assert.equal(summary.runs[2].stages[0].status,'failed');assert.equal(summary.runs[3].stages[0].reused,true);
  assert.deepEqual(x.calls,['backup','disable','install','enable']);assert.equal(summary.incompleteCommands,0);
  assert.equal(summary.measuredCommandMs,summary.runs.reduce((sum,r)=>sum+r.elapsedMs,0));
});

test('timing distinguishes gaps and interrupted commands and rejects corrupt journals',async()=>{
  const event=(runId,scope,stageId,status,at,elapsedMs)=>({version:1,runId,command:'pack',scope,stageId,phase:'pack',status,at,elapsedMs});
  const rows=[event('one','command','one','started','2026-10-30T00:00:00Z',0),event('one','phase','p','started','2026-10-30T00:00:00Z',0),
    event('one','phase','p','completed','2026-10-30T00:00:02Z',2000),event('one','command','one','completed','2026-10-30T00:00:03Z',3000),
    event('two','command','two','started','2026-10-30T00:00:13Z',0)];
  const result=summarizeTimings(rows);assert.equal(result.measuredCommandMs,3000);assert.equal(result.betweenCommandsMs,10000);assert.equal(result.incompleteCommands,1);
  assert.equal(result.runs[1].status,'incomplete');assert.equal(result.runs[1].finishedAt,null);
  assert.throws(()=>summarizeTimings([rows[3]]),/sequence/);
  const path=await fixture();assert.deepEqual((await timingReport(path)).runs,[]);await writeFile(join(path,'timing.jsonl'),'{broken');
  await assert.rejects(timingReport(path),/line 1/);
});
test('disabled bundles stay disabled and already-aligned sources are never reinstalled',async()=>{
  const disabled=await deployment({disabled:true});await deployPackages(disabled.options);assert.deepEqual(disabled.calls,['backup','install']);
  const aligned=await deployment({alreadyInstalled:true});await deployPackages(aligned.options);assert.deepEqual(aligned.calls,['backup']);
});
test('unknown installation result stops and is never resent after resume',async()=>{
  const x=await deployment({failInstall:true});await assert.rejects(deployPackages(x.options),/response lost/);
  const state=await json(join(x.path,'deployment.json'));assert.equal(state.pending.phase,'install');assert.equal(x.bundles[0].version,'2.0.0');
  await assert.rejects(deployPackages(x.options),/unknown outcome/);assert.deepEqual(x.calls,['backup','disable','install']);
});
test('interruption after confirmed mutations resumes verification without repeating writes',async()=>{
  const x=await deployment({verifyFailure:true});await assert.rejects(deployPackages(x.options),/verification interrupted/);assert.equal((await json(join(x.path,'deployment.json'))).pending,null);
  await deployPackages(x.options);assert.deepEqual(x.calls,['backup','disable','install','enable']);
});
test('running tasks, plan drift, unrelated changes and changed baselines stop deployment',async()=>{
  const x=await deployment();x.setRunning(true);await assert.rejects(deployPackages(x.options),/task is running/);assert.deepEqual(x.calls,[]);
  x.setRunning(false);await deployPackages(x.options);
  await assert.rejects(deployPackages({...x.options,plan:{packages:[{...x.pkg,version:'9.0.0'}]}}),/plan changed/);
  x.bundles[1].version='4.0.0';await assert.rejects(deployPackages(x.options),/Unrelated bundles changed/);
  const y=await deployment();const baseline=await y.options.adapter.snapshot();await save(join(y.path,'deployment.json'),{identity:digest(JSON.stringify(y.options.plan)),baseline,backups:[],completed:[],done:[],pending:null});y.bundles[0].version='8.0.0';await assert.rejects(deployPackages(y.options),/outside this run/);
  const z=await deployment();const prior=await z.options.adapter.snapshot();await save(join(z.path,'deployment.json'),{identity:digest(JSON.stringify(z.options.plan)),baseline:prior,backups:[],completed:[],done:[],pending:null});z.bundles[0].dependency='file:another-source';await assert.rejects(deployPackages(z.options),/outside this run/);assert.deepEqual(z.calls,[]);
});
test('live host adapter refuses nonlocal inspector endpoints before networking',async()=>{
  for(const url of ['http://example.com/','https://127.0.0.1:9230/','http://user:password@127.0.0.1:9230/','http://127.0.0.1:9230/?token=secret'])await assert.rejects(openHost(url),/loopback HTTP origin/);
});
test('failed manager results retain diagnostic receipt and block later phases',async()=>{
  const x=await deployment();x.options.adapter.install=async()=>({application:'failed',logPath:'private-local-log'});
  await assert.rejects(deployPackages(x.options),/did not apply/);const state=await json(join(x.path,'deployment.json'));assert.equal(state.pending.result.logPath,'private-local-log');assert.deepEqual(x.calls,['backup','disable']);
  await assert.rejects(deployPackages(x.options),/unknown outcome/);
});
test('rollback backup corruption stops a resumed run before any mutation',async()=>{
  const x=await deployment(),backup=join(x.path,'original.bak');
  x.options.backup=async()=>{await writeFile(backup,'original');return [{backup,sha256:digest('original')}];};await deployPackages(x.options);const calls=[...x.calls];
  await writeFile(backup,'corrupt');await assert.rejects(deployPackages(x.options),/backup changed/);assert.deepEqual(x.calls,calls);
});
test('command output stays parseable when a tool also emits stderr warnings',async()=>{
  const path=await fixture(),log=join(path,'command.log');const result=await command(process.execPath,['-e','console.error("warning");console.log(JSON.stringify({ok:true}))'],{log});
  assert.deepEqual(JSON.parse(result.output),{ok:true});assert.match(await readFile(log,'utf8'),/warning/);
});

test('command streams its log before completion and retains output from failed commands',async()=>{
  const path=await fixture(),log=join(path,'live.log'),ack=join(path,'ack');
  const code='const fs=require("node:fs");console.log("ready");const timer=setInterval(()=>{if(fs.existsSync(process.argv[1])){clearInterval(timer);console.log("finished");}},10);setTimeout(()=>process.exit(3),5000).unref();';
  const running=command(process.execPath,['-e',code,ack],{log});
  const ready=async()=>{const deadline=performance.now()+4500;while(performance.now()<deadline){try{if((await readFile(log,'utf8')).includes('ready'))return;}catch(error){if(error.code!=='ENOENT')throw error;}await new Promise(yes=>setTimeout(yes,10));}throw Error('Live command log did not appear');};
  try{await Promise.race([running.then(()=>{throw Error('Command finished before receiving acknowledgement');}),ready()]);}
  finally{await writeFile(ack,'ok');await running;}
  assert.match(await readFile(log,'utf8'),/ready[\s\S]*finished/);
  const failure=join(path,'failed.log');await assert.rejects(command(process.execPath,['-e','console.error("before-failure");process.exitCode=7;'],{log:failure}),/Command failed \(7\)/);
  assert.match(await readFile(failure,'utf8'),/before-failure/);
});
test('host transport reuses one connection, compiles guarded requests and rejects lost responses',async t=>{
  const requests=[];let connections=0,disconnect=false,hostProfile=directory,mutations=0;
  const manager={listBundles:async()=>[],listPlugins:async()=>[],setBundleEnabled:async()=>{mutations++;return {application:'applied'};},installBundle:async()=>{mutations++;return {application:'applied'};}};
  const context={get:service=>({pluginManager:manager,sessions:{list:()=>[]},agents:{get:()=>null}})[service],get profileContext(){return {dir:hostProfile};}};
  const sandbox={Symbol,globalThis:{[Symbol.for('dsh.inspector.realm-object-registries')]:new Map([['fixture',{resolve:()=>context}]])}};
  class Socket extends EventTarget {
    constructor(){super();connections++;queueMicrotask(()=>this.dispatchEvent(new Event('open')));}
    send(text){const request=JSON.parse(text);requests.push(request);const script=new Script(request.params.expression);if(disconnect){queueMicrotask(()=>this.close());return;}
      Promise.resolve().then(()=>script.runInNewContext(sandbox)).then(value=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({id:request.id,result:{result:{value}}})})),()=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({id:request.id,result:{exceptionDetails:{text:'fixture refusal'}}})})));
    }
    close(){this.dispatchEvent(new Event('close'));}
  }
  t.mock.method(globalThis,'fetch',async()=>Response.json([{webSocketDebuggerUrl:'ws://127.0.0.1:9230/devtools/test'}]));
  const original=globalThis.WebSocket;globalThis.WebSocket=Socket;t.after(()=>{globalThis.WebSocket=original;});
  const host=await openHost('http://127.0.0.1:9230/',directory);await host.snapshot();await host.disable({name:'@juzi/a'});await host.install({name:'@juzi/a',installSpec:'git+https://example.invalid/repo#pin'},'once');
  assert.equal(connections,1);assert.equal(requests.length,3);assert.match(requests[1].params.expression,/status==='running'/);assert.equal(mutations,2);
  hostProfile=join(directory,'another-profile');await assert.rejects(host.enable({name:'@juzi/a'}),/Host rejected/);assert.equal(mutations,2);hostProfile=directory;
  disconnect=true;await assert.rejects(host.enable({name:'@juzi/a'}),/disconnected/);host.close();
});
