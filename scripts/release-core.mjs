import {createHash, randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import {createWriteStream} from 'node:fs';
import {finished} from 'node:stream/promises';
import {mkdir, readFile, writeFile, rename, open, unlink} from 'node:fs/promises';
import {resolve, join, dirname, relative, isAbsolute} from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {git, readTree, readBlobs} from './git-source.mjs';

export {git};

export const digest = bytes => createHash('sha256').update(bytes).digest('hex');
export const normalizedSpec = spec => spec?.replace('git+https://github.com/','github:').replace('.git#','#');
export const json = async path => JSON.parse((await readFile(path, 'utf8')).replace(/^\uFEFF/, ''));
export async function save(path, value) {
  await mkdir(dirname(path), {recursive:true});
  const temporary = path + '.' + randomUUID() + '.tmp';
  await writeFile(temporary, JSON.stringify(value, null, 2) + '\n');
  await rename(temporary, path);
}
export function inside(root, path) {
  const result = resolve(root, path), rel = relative(resolve(root), result);
  if (!rel || rel.startsWith('..') || isAbsolute(rel)) throw Error('Path must stay inside output directory');
  return result;
}
export async function withLock(directory, action) {
  await mkdir(directory, {recursive:true});
  const path = join(directory, 'run.lock');
  try {
    const owner = await json(path);
    try { process.kill(owner.pid, 0); throw Error('Another release process owns this run'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
    await unlink(path);
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  const handle = await open(path, 'wx');
  try { await handle.writeFile(JSON.stringify({pid:process.pid})); await handle.close(); return await action(); }
  finally { await handle.close(); await unlink(path); }
}
export async function command(file, args, {cwd, env=process.env, log}={}) {
  const started=performance.now(),stdout=[];let sink,logDone,child,code;
  if(log){
    await mkdir(dirname(log),{recursive:true});sink=createWriteStream(log);
    logDone=finished(sink,{cleanup:true}).then(()=>null,error=>error);
    sink.on('error',()=>{child?.stdout.resume();child?.stderr.resume();});
    await new Promise((yes,no)=>{sink.once('open',yes);sink.once('error',no);});
  }
  try{
    child=spawn(file,args,{cwd,env,windowsHide:true,shell:false,stdio:['ignore','pipe','pipe']});
    child.stdout.on('data',bytes=>stdout.push(bytes));
    if(sink){child.stdout.pipe(sink,{end:false});child.stderr.pipe(sink,{end:false});}else child.stderr.resume();
    code=await new Promise((yes,no)=>{child.once('error',no);child.once('close',yes);});
  }catch(error){if(sink&&!sink.destroyed)sink.write('Command could not start: '+error.message+'\n');throw error;}
  finally{if(sink){sink.end();const error=await logDone;if(error)throw error;}}
  if(code!==0)throw Error(`Command failed (${code}): ${file}; inspect ${log ?? 'command output'}`);
  return {output:Buffer.concat(stdout).toString('utf8'),elapsedMs:Math.round(performance.now()-started)};
}
export async function step(phase,action,{report=event=>console.log(JSON.stringify(event)),intervalMs=10000}={}){
  const started=performance.now(),emit=(status,extra={})=>report({phase,status,elapsedMs:Math.round(performance.now()-started),...extra});
  emit('started');const timer=setInterval(()=>emit('running'),intervalMs);timer.unref();
  try{const result=await action();emit('completed',typeof result?.reused==='boolean'?{reused:result.reused}:{});return result;}
  catch(error){emit('failed');throw error;}
  finally{clearInterval(timer);}
}
export async function fingerprint(cwd, environment={}) {
  const paths=git(cwd,['ls-files','-z','--cached','--others','--exclude-standard']).split('\0').filter(Boolean)
    .filter(p=>/^(plugins\/|scripts\/|\.github\/|marketplace\/catalog\.json$|package(?:-lock)?\.json$)/.test(p));
  const files=[];
  for(const path of [...new Set(paths)].sort()){
    try{files.push([path,digest(await readFile(join(cwd,path)))]);}
    catch(error){if(error.code!=='ENOENT')throw error;files.push([path,'deleted']);}
  }
  const runtime=[];
  for(const [key,path] of Object.entries(environment).filter(([k])=>/^DSH_.*_(MODULE|ANCHOR|BUNDLE|SOURCE_FILE)$/.test(k)).sort()){
    if(!path)continue;
    const absolute=resolve(path); runtime.push([key,absolute,digest(await readFile(absolute))]);
    let base=dirname(absolute);
    // Integration runtimes are external to the repository; include their dependency lock and manifest.
    while(base!==dirname(base)){
      for(const file of ['package.json','package-lock.json','node_modules/.package-lock.json']){
        try{runtime.push([join(base,file),digest(await readFile(join(base,file)))]);}catch(error){if(error.code!=='ENOENT')throw error;}
      }
      if(!base.includes('node_modules')&&base!==dirname(absolute))break;
      base=dirname(base);
    }
  }
  return digest(JSON.stringify({files,runtime,node:process.version,platform:process.platform,arch:process.arch,environment}));
}
export async function gate({directory,key,inputs,run,refresh=false}) {
  const path=join(directory,key+'.json');
  const before=await inputs();
  if(!refresh){
    try{const previous=await json(path);if(previous.inputs===before&&previous.status==='passed'&&digest(await readFile(previous.log))===previous.logSha256)return {...previous,reused:true};}
    catch(error){if(error.code!=='ENOENT')throw error;}
  }
  try{await unlink(path);}catch(error){if(error.code!=='ENOENT')throw error;}
  const log=join(directory,key+'.log');
  const result=await run(log);
  if(await inputs()!==before)throw Error('Validation inputs changed while running; result was not cached');
  const receipt={status:'passed',inputs:before,log,logSha256:digest(await readFile(log)),elapsedMs:result.elapsedMs,finishedAt:new Date().toISOString()};
  await save(path,receipt); return {...receipt,reused:false};
}
export async function materialize(cwd, commit, selections) {
  if(!selections.length||new Set(selections.map(s=>s.path)).size!==selections.length)throw Error('Select unique committed package paths');
  const tree=[...readTree(cwd,commit,selections.map(s=>s.path)).values()];
  const rows=selections.flatMap(({path,output})=>{
    const selected=tree.filter(row=>row.path.startsWith(path+'/'));
    if(!selected.length)throw Error('No committed plugin files: '+path);
    return selected.map(row=>{
      if(!['100644','100755'].includes(row.mode)||row.type!=='blob')throw Error('Source contains an unsupported file or symlink');
      return {...row,target:inside(output,row.path.slice(path.length+1))};
    });
  });
  const blobs=readBlobs(cwd,rows.map(row=>row.sha));
  for(const row of rows){
    await mkdir(dirname(row.target),{recursive:true});
    await writeFile(row.target,blobs.get(row.sha),{mode:parseInt(row.mode,8)&0o777});
  }
}
export function mergeIndex(existing, replacement) {
  const changes=new Map(replacement.plugins.map(p=>[p.name,p]));
  const plugins=existing.plugins.map(p=>{const next=changes.get(p.name);changes.delete(p.name);return next??p;});
  return {...existing,plugins:[...plugins,...changes.values()]};
}
export async function verifyFiles(pkg, installed) {
  for(const file of pkg.files){
    const actual=await readFile(inside(installed,file.path));
    if(digest(actual)===file.sha256)continue;
    const expected=await readFile(inside(pkg.source,file.path));
    if(digest(expected)!==file.sha256)throw Error('Cached package source changed: '+pkg.name+'/'+file.path);
    let equivalent=false;
    try{const decoder=new TextDecoder('utf-8',{fatal:true});equivalent=!actual.includes(0)&&decoder.decode(actual).replaceAll('\r\n','\n')===decoder.decode(expected).replaceAll('\r\n','\n');}catch(error){if(error.code!=='ERR_ENCODING_INVALID_ENCODED_DATA')throw error;}
    if(!equivalent)throw Error('Installed file mismatch: '+pkg.name+'/'+file.path);
  }
}
export async function deployPackages({plan,directory,adapter,backup,verify,measure=(_phase,action)=>action()}) {
  const statePath=join(directory,'deployment.json');
  const identity=digest(JSON.stringify(plan));
  let state;try{state=await json(statePath);}catch(error){if(error.code!=='ENOENT')throw error;}
  const quiet=async()=>{const s=await adapter.snapshot();if(s.running.length)throw Error('A DSH task is running');return s;};
  if(state&&state.identity!==identity)throw Error('Deployment plan changed; use a new run directory');
  if(state?.pending)throw Error('Previous mutation has unknown outcome; inspect state and logs before any further writes');
  if(!state){
    const baseline=await quiet();
    state={identity,baseline,backups:await measure('backup',()=>backup(baseline)),completed:[],done:[],pending:null};
    await save(statePath,state);
  }
  for(const b of state.backups)if(b.sha256&&digest(await readFile(b.backup))!==b.sha256)throw Error('Rollback backup changed');
  for(const pkg of plan.packages){
    let snapshot=await quiet();
    const bundle=snapshot.bundles.find(b=>b.name===pkg.name), original=state.baseline.bundles.find(b=>b.name===pkg.name);
    if(!original||!bundle)throw Error('Target bundle missing: '+pkg.name);
    const phases=original.enabled?['disable','install','enable']:['install'];
    const completed=state.completed.filter(p=>p.name===pkg.name);
    if(state.done.includes(pkg.name)){await verify(pkg,state.baseline);continue;}
    if(!completed.length&&bundle.version===pkg.version&&bundle.dependency===normalizedSpec(pkg.installSpec)){
      await verify(pkg,state.baseline);state.done.push(pkg.name);await save(statePath,state);continue;
    }
    const expectedVersion=completed.some(p=>p.phase==='install')?pkg.version:original.version;
    const expectedEnabled=completed.length?completed.at(-1).phase==='enable':original.enabled;
    const expectedDependency=completed.some(p=>p.phase==='install')?normalizedSpec(pkg.installSpec):original.dependency;
    if(bundle.version!==expectedVersion||bundle.enabled!==expectedEnabled||bundle.dependency!==expectedDependency)throw Error('Bundle changed outside this run: '+pkg.name);
    for(const phase of phases){
      if(completed.some(p=>p.phase===phase))continue;
      await quiet();
      state.pending={name:pkg.name,phase,requestId:identity.slice(0,24)+'-'+pkg.name,startedAt:new Date().toISOString()};
      await save(statePath,state);
      // A lost response is deliberately left pending; a later invocation must not repeat the mutation.
      const result=await measure('deploy:'+pkg.name+':'+phase,()=>adapter[phase](pkg,state.pending.requestId));
      state.pending.result=result;await save(statePath,state);
      if(result.application!=='applied')throw Error('Manager did not apply '+pkg.name+'/'+phase);
      snapshot=await quiet();
      const current=snapshot.bundles.find(b=>b.name===pkg.name);
      if(!current||current.error||current.version!==(phase==='disable'?original.version:pkg.version)||current.enabled!==(phase==='enable'))throw Error('Manager postcondition mismatch: '+pkg.name+'/'+phase);
      state.completed.push({...state.pending,result,finishedAt:new Date().toISOString()});state.pending=null;await save(statePath,state);
    }
    await verify(pkg,state.baseline);state.done.push(pkg.name);await save(statePath,state);
  }
  const final=await quiet(), targets=new Set(plan.packages.map(p=>p.name));
  if(!isDeepStrictEqual(state.baseline.bundles.filter(b=>!targets.has(b.name)),final.bundles.filter(b=>!targets.has(b.name))))throw Error('Unrelated bundles changed');
  for(const pkg of plan.packages)await verify(pkg,state.baseline);
  state.status='verified';state.finishedAt=new Date().toISOString();await save(statePath,state);return state;
}
