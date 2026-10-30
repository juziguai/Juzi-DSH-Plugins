import {readFile, writeFile, mkdir, realpath, lstat} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {join, resolve, isAbsolute} from 'node:path';
import {parseArgs, isDeepStrictEqual} from 'node:util';
import {createMarketIndex, validateIndex, verifyPinnedIndex} from './market-index.mjs';
import {digest,json,save,inside,git,withLock,command,fingerprint,gate,materialize,mergeIndex,verifyFiles,deployPackages,normalizedSpec} from './release-core.mjs';
import {openHost} from './release-host.mjs';
import {withTiming,timingReport} from './release-timing.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const runtimeKeys=['DSH_SLOT_CORE_MODULE','DSH_CORDIS_MODULE','DSH_PRESET_MODULE','DSH_FAST_RUNTIME_ANCHOR','DSH_ULTRA_UI_RUNTIME_ANCHOR','DSH_CONVERSATION_BUNDLE','DSH_LAYOUT_SHARES_MODULE','DSH_LAYOUT_SOURCE_FILE'];
const usage=`npm run release -- <prepare|pack|market|deploy|status|report> [options]
  --plugins dir,dir       Explicit plugin directories, or all (prepare defaults to all)
  --run path              Local receipts/artifacts (default .codex/release)
  --python absolute-path  Explicit test/backup interpreter; also accepts PYTHON
  --commit full-SHA       Committed source for pack and market
  --repository HTTPS-URL  Canonical repository URL for pack and market
  --validator path        Installed official market validator; DSH_MARKET_INDEX_MODULE
  --plan path             Immutable package plan returned by pack
  --profile path --inspector http://127.0.0.1:PORT/
  --yaml path             Existing js-yaml module for live profile validation
  --changes-export path   Fresh Changes export before a Changes replacement
  --apply                 Required for live deploy; otherwise prints plan only
  --write-market          Explicitly replace marketplace/index.json; default writes a preview
  --refresh               Rerun validation instead of reusing its successful receipt
No command commits, pushes, tags, publishes a GitHub Release, or restarts DSH.`;

function npmCli(){const path=process.env.npm_execpath;if(!path||!path.endsWith('npm-cli.js'))throw Error('Run through npm run release so npm-cli.js is explicit');return path;}
async function pythonPath(value){if(!value||!isAbsolute(value))throw Error('Provide an absolute --python or PYTHON; no interpreter guessing');return realpath(value);}
function select(catalog,value){
  const dirs=value==='all'?catalog.plugins.map(p=>p.path.split('/').at(-1)):(value??'').split(',');
  if(!dirs.length||dirs.some(d=>!d)||new Set(dirs).size!==dirs.length)throw Error('Select unique plugin directories with --plugins');
  const selected=catalog.plugins.filter(p=>dirs.includes(p.path.split('/').at(-1)));
  if(selected.length!==dirs.length)throw Error('Unknown plugin directory');return {...catalog,plugins:selected};
}
async function pinned(options){
  if(!/^[0-9a-f]{40}$/.test(options.commit??''))throw Error('--commit must be a full committed source SHA');
  const catalog=select(await json(join(root,'marketplace/catalog.json')),options.plugins);
  const index=createMarketIndex({catalog,repository:options.repository,commit:options.commit,cwd:root});
  for(const p of index.plugins)if(!/^\d+\.\d+\.\d+$/.test(p.versions[0].version))throw Error('Formal packages require a stable component version');
  const targets=await validateIndex(index,options.validator);return {index,targets};
}
async function prepare(options,directory,measure){
  const started=performance.now();
  const catalog=select(await json(join(root,'marketplace/catalog.json')),options.plugins??'all');
  for(const p of catalog.plugins){
    const build=({'plugins/dsh-ultra-effort':'build/client.mjs','plugins/dsh-layout-memory':'build/client.mjs','plugins/dsh-quote-annotate':'build/client.mjs','plugins/dsh-preset-unlock':'build/patch.mjs'})[p.path];
    if(build)await measure('build:'+p.path.split('/').at(-1),()=>command(process.execPath,[join(root,p.path,build)],{cwd:root,log:join(directory,'build-'+p.path.split('/').at(-1)+'.log')}));
  }
  const python=await pythonPath(options.python);
  const identity=execFileSync(python,['-c','import sys,json,importlib.metadata as m; print(json.dumps([sys.executable,sys.version,sorted((x.metadata["Name"],x.version) for x in m.distributions())]))'],{encoding:'utf8',windowsHide:true});
  const environment={PYTHON:python,PYTHON_ID:digest(identity),NODE_OPTIONS:process.env.NODE_OPTIONS??'',NPM_CLI:digest(await readFile(npmCli())),...Object.fromEntries(runtimeKeys.map(k=>[k,process.env[k]??'']))};
  const results=await Promise.allSettled([
    measure('npm-test',()=>gate({directory:join(directory,'gates'),key:'npm-test',refresh:options.refresh,inputs:()=>fingerprint(root,environment),run:log=>command(process.execPath,[npmCli(),'test'],{cwd:root,env:{...process.env,PYTHON:python},log})})),
    measure('diff-check',()=>command('git',['diff','--check'],{cwd:root,log:join(directory,'diff-check.log')})),
  ]);
  for(const result of results)if(result.status==='rejected')throw result.reason;
  const result=results[0].value;console.log(JSON.stringify({gate:'npm-test',reused:result.reused,elapsedMs:Math.round(performance.now()-started),originalTestMs:result.elapsedMs,log:result.log}));
  return result;
}
async function pack(options,directory,measure){
  const {index,targets}=await measure('source-check',()=>pinned(options)), base=join(directory,options.commit), planPath=join(base,'plan.json');
  let old;try{old=await json(planPath);}catch(error){if(error.code!=='ENOENT')throw error;}
  if(old){
    if(!isDeepStrictEqual(old.packages.map(p=>p.name).sort(),index.plugins.map(p=>p.name).sort())||old.repository!==options.repository)throw Error('Artifact selection changed; use another run directory');
    await measure('archive-reuse',async()=>{
      for(const p of old.packages){if(digest(await readFile(p.archive))!==p.archiveSha256)throw Error('Cached archive changed');for(const f of p.files)if(digest(await readFile(inside(p.source,f.path)))!==f.sha256)throw Error('Cached package source changed');}
      return {reused:true};
    });
    console.log(JSON.stringify({plan:planPath,reused:true,packages:old.packages.length}));return {reused:true};
  }
  await mkdir(base,{recursive:true});await mkdir(join(base,'archives'));
  const sources=index.plugins.map(item=>({path:item.repository.directory,output:join(base,'source',item.repository.directory.split('/').at(-1))}));
  await measure('source-materialize',()=>materialize(root,options.commit,sources));
  const packedItems=await measure('npm-pack',async()=>{
    const result=await command(process.execPath,[npmCli(),'pack',...sources.map(s=>s.output),'--offline','--json','--ignore-scripts','--pack-destination',join(base,'archives')],{cwd:base,log:join(base,'npm-pack.log')});
    const values=JSON.parse(result.output);
    if(!Array.isArray(values)||values.length!==index.plugins.length||new Set(values.map(p=>p.name)).size!==values.length)throw Error('Packed selection differs from committed packages');
    return new Map(values.map(p=>[p.name,p]));
  });
  const packages=[];
  for(const [i,item] of index.plugins.entries()){
    await measure('verify-archive:'+item.name,async()=>{
    const source=sources[i].output,packed=packedItems.get(item.name);
    if(!packed)throw Error('Packed package missing: '+item.name);
    if(packed.name!==item.name||packed.version!==item.versions[0].version)throw Error('Packed identity differs from committed manifest');
    const archive=inside(join(base,'archives'),packed.filename),files=[];
    for(const file of packed.files){
      if(/(^|\/)(node_modules|__pycache__|\.codex)(\/|$)|\.pyc$|\.bak/.test(file.path))throw Error('Unexpected runtime/cache file in package');
      files.push({path:file.path,sha256:digest(await readFile(inside(source,file.path)))});
    }
    const listing=(await command('tar',['-tzf',archive])).output.trim().split(/\r?\n/).sort();
    if(!isDeepStrictEqual(listing,files.map(f=>'package/'+f.path).sort()))throw Error('Archive members differ from npm manifest');
    const verify=join(base,'verify',item.name.replaceAll('/','-'));await mkdir(verify,{recursive:true});await command('tar',['-xzf',archive,'-C',verify]);
    for(const f of files){const target=inside(join(verify,'package'),f.path);if(!(await lstat(target)).isFile()||digest(await readFile(target))!==f.sha256)throw Error('Archive content mismatch');}
    packages.push({name:item.name,version:packed.version,directory:item.repository.directory.split('/').at(-1),source,installSpec:targets.find(t=>t.name===item.name).spec,archive,archiveSha256:digest(await readFile(archive)),files});
    });
  }
  await save(planPath,{sourceCommit:options.commit,repository:options.repository,packages});
  await writeFile(join(base,'archives','SHA256SUMS.txt'),packages.map(p=>p.archiveSha256+'  '+p.archive.split(/[\\/]/).at(-1)).join('\n')+'\n');
  console.log(JSON.stringify({plan:planPath,packages:packages.map(p=>({name:p.name,version:p.version,files:p.files.length}))}));
  return {reused:false};
}
async function market(options,directory,measure){
  const {index}=await measure('source-check',()=>pinned(options));
  const merged=mergeIndex(await json(join(root,'marketplace/index.json')),index);
  await measure('market-verification',async()=>{verifyPinnedIndex(merged,root);await validateIndex(merged,options.validator);});
  const output=options['write-market']?join(root,'marketplace/index.json'):join(directory,options.commit,'market-index.json');
  await save(output,merged);console.log(JSON.stringify({output,updated:index.plugins.map(p=>p.name),writtenToWorkingIndex:!!options['write-market']}));
}
async function deploy(options,directory,measure){
  if(!options.plan)throw Error('--plan is required');
  const plan=await json(resolve(options.plan));
  const expected=await measure('deployment-plan',()=>pinned({...options,commit:plan.sourceCommit,repository:plan.repository,plugins:plan.packages.map(p=>p.directory).join(',')}));
  for(const p of plan.packages){
    const target=expected.targets.find(t=>t.name===p.name);
    if(target?.spec!==p.installSpec||expected.index.plugins.find(x=>x.name===p.name)?.versions[0].version!==p.version||digest(await readFile(p.archive))!==p.archiveSha256)throw Error('Package plan differs from committed/validated source');
  }
  if(!options.apply){console.log(JSON.stringify({mode:'preview',packages:plan.packages.map(p=>({name:p.name,version:p.version,source:p.installSpec})),next:'Use --apply only after authorization, CI and runtime acceptance.'}));return;}
  if(!isAbsolute(options.profile??'')||!options.inspector||!options.yaml)throw Error('Live deployment requires --profile, --inspector and --yaml');
  const python=await pythonPath(options.python),profile=await realpath(options.profile),manifestPath=join(profile,'package.json');
  const imported=await import(pathToFileURL(resolve(options.yaml))),yaml=imported.default??imported;
  const schema=yaml.DEFAULT_SCHEMA.extend([new yaml.Type('tag:yaml.org,2002:js',{kind:'scalar',construct:value=>value})]);
  const parseYaml=text=>yaml.load(text,{schema});
  const host=await measure('host-connect',()=>openHost(options.inspector,profile)),targets=new Set(plan.packages.map(p=>p.name));
  const snapshot=host.snapshot;
  host.snapshot=async()=>{const s=await snapshot(),manifest=await json(manifestPath);return {...s,bundles:s.bundles.map(b=>({...b,dependency:normalizedSpec(manifest.dependencies?.[b.name])}))};};
  const backup=async baseline=>{
    const needed=plan.packages.filter(p=>{const b=baseline.bundles.find(b=>b.name===p.name);return b?.version!==p.version||b?.dependency!==normalizedSpec(p.installSpec);});
    if(needed.some(p=>p.name==='@juzi/dsh-changes')){
      if(!options['changes-export'])throw Error('Changes replacement requires a fresh --changes-export; stopping does clear its temporary records');
      const exported=await json(resolve(options['changes-export']));
      const age=Date.now()-Date.parse(exported.createdAt);
      if(!Array.isArray(exported.sessions)||!Array.isArray(exported.errors)||exported.errors.length||exported.cappedTurns!==0||!Number.isFinite(age)||age<0||age>10*60*1000)throw Error('Changes export is incomplete or older than ten minutes');
    }
    const destination=join(directory,'rollback');await mkdir(destination);
    const backups=['package.json','cordis.patch.yml','pnpm-lock.yaml','pnpm-workspace.yaml'].map(file=>({file,original:join(profile,file),backup:join(destination,file+'.bak')}));
    execFileSync(python,['-c','import json,sys,shutil; rows=json.load(sys.stdin); [shutil.copy2(r["original"],r["backup"]) for r in rows]'],{input:JSON.stringify(backups),windowsHide:true});
    for(const b of backups){const original=await readFile(b.original),copy=await readFile(b.backup);if(!original.length||!original.equals(copy))throw Error('Profile backup mismatch');b.sha256=digest(copy);if(b.file==='package.json')JSON.parse(copy.toString());else parseYaml(copy.toString());}
    for(const p of needed){
      if(!baseline.bundles.some(b=>b.name===p.name))throw Error('Only existing installed bundles may be replaced');
      const result=await command(process.execPath,[npmCli(),'pack','--offline','--json','--ignore-scripts','--pack-destination',destination],{cwd:join(profile,'node_modules',p.name),log:join(destination,p.directory+'.log')});
      const [old]=JSON.parse(result.output);if(old.name!==p.name)throw Error('Rollback package identity mismatch');
      const archive=inside(destination,old.filename);backups.push({file:old.filename,backup:archive,sha256:digest(await readFile(archive))});
    }
    if(options['changes-export']){const backup=join(destination,'changes-export.json'),bytes=await readFile(resolve(options['changes-export']));await writeFile(backup,bytes);backups.push({file:'changes-export.json',backup,sha256:digest(bytes)});}
    return backups;
  };
  const verify=async(pkg,baseline)=>{
    await verifyFiles(pkg,join(profile,'node_modules',pkg.name));
    const manifest=await json(manifestPath),old=await json(join(directory,'rollback','package.json.bak'));
    if(normalizedSpec(manifest.dependencies[pkg.name])!==normalizedSpec(pkg.installSpec))throw Error('Installed dependency is not the pinned Git source');
    for(const name of targets){delete manifest.dependencies[name];delete old.dependencies[name];}
    manifest.dsh.profile.bundles=manifest.dsh.profile.bundles.filter(n=>!targets.has(n));old.dsh.profile.bundles=old.dsh.profile.bundles.filter(n=>!targets.has(n));
    if(!isDeepStrictEqual(manifest,old))throw Error('Unrelated profile fields changed');
    for(const file of ['cordis.patch.yml','pnpm-workspace.yaml'])if(!isDeepStrictEqual(parseYaml(await readFile(join(profile,file),'utf8')),parseYaml(await readFile(join(directory,'rollback',file+'.bak'),'utf8'))))throw Error('Profile configuration changed');
    parseYaml(await readFile(join(profile,'pnpm-lock.yaml'),'utf8'));
    const now=await host.snapshot(),original=baseline.bundles.find(b=>b.name===pkg.name),b=now.bundles.find(b=>b.name===pkg.name);
    if(b.version!==pkg.version||b.enabled!==original.enabled||b.error||original.enabled&&now.entries.find(e=>e.name===pkg.name)?.phase!=='active')throw Error('Runtime bundle not ready');
  };
  try{const state=await deployPackages({plan,directory,adapter:host,backup,verify,measure});console.log(JSON.stringify({status:state.status,packages:state.done,receipt:join(directory,'deployment.json')}));}
  finally{host.close();}
}
async function main(){
  const {values:options,positionals}=parseArgs({allowPositionals:true,options:Object.fromEntries([
    ...['plugins','run','python','commit','repository','validator','plan','profile','inspector','yaml','changes-export'].map(k=>[k,{type:'string'}]),
    ...['apply','refresh','write-market','help'].map(k=>[k,{type:'boolean',default:false}]),
  ])});
  if(options.help||!positionals.length){console.log(usage);return;}
  options.python??=process.env.PYTHON;options.validator??=process.env.DSH_MARKET_INDEX_MODULE;
  const [action,...extra]=positionals;if(extra.length||!['prepare','pack','market','deploy','status','report'].includes(action))throw Error('Unknown command; use --help');
  const directory=resolve(root,options.run??'.codex/release');
  try{git(root,['check-ignore','--quiet','--',join(directory,'release-output')]);}catch{throw Error('--run must be a Git-ignored directory inside this repository');}
  if(action==='status'){const state=await json(join(directory,'deployment.json'));console.log(JSON.stringify({status:state.status??'incomplete',pending:state.pending,done:state.done,completed:state.completed.map(p=>({name:p.name,phase:p.phase})),backups:state.backups.map(b=>b.backup)},null,2));return;}
  if(action==='report'){console.log(JSON.stringify(await timingReport(directory),null,2));return;}
  await withLock(directory,()=>withTiming(directory,action,measure=>({prepare,pack,market,deploy})[action](options,directory,measure)));
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(error=>{console.error(error.message);process.exitCode=1;});
