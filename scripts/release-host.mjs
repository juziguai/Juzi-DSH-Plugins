import {isAbsolute} from 'node:path';

const context = `const registries=globalThis[Symbol.for('dsh.inspector.realm-object-registries')];const c=registries&&[...registries.values()][0]?.resolve('object-1');if(!c?.get)throw Error('Unsupported inspector context');const m=c.get('pluginManager');if(!m?.listBundles||!m?.installBundle||!m?.setBundleEnabled)throw Error('Unsupported plugin manager');`;
const quiet = `if(c.get('sessions').list().some(s=>c.get('agents').get(s.id)?.status==='running'))throw Error('A DSH task is running');`;
function normalizedProfile(value,windows){const path=value.replaceAll('\\','/').replace(/\/$/,'');return windows?path.toLowerCase():path;}

export async function openHost(endpoint,profile) {
  const url=new URL(endpoint);
  if(url.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(url.hostname)||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error('Inspector must be an explicit loopback HTTP origin');
  if(!isAbsolute(profile??''))throw Error('Inspector requires an absolute target profile');
  const windows=process.platform==='win32',expected=normalizedProfile(profile,windows);
  const guard=`const normalizeProfile=${normalizedProfile.toString()};if(typeof c.profileContext?.dir!=='string'||normalizeProfile(c.profileContext.dir,${windows})!==${JSON.stringify(expected)})throw Error('Inspector belongs to another profile');`;
  const response=await fetch(new URL('/json/list',url),{redirect:'error',signal:AbortSignal.timeout(8000)});
  if(!response.ok)throw Error('Cannot read inspector targets');
  const targets=await response.json();
  if(targets.length!==1)throw Error('Inspector target must be unique');
  const websocket=new URL(targets[0].webSocketDebuggerUrl);
  if(websocket.protocol!=='ws:'||websocket.hostname!==url.hostname||websocket.port!==url.port)throw Error('Inspector WebSocket origin differs');
  const socket=new WebSocket(websocket), pending=new Map();let sequence=0;
  await new Promise((yes,no)=>{
    const timer=setTimeout(()=>{socket.close();no(Error('Inspector connection timed out'));},8000);
    socket.addEventListener('open',()=>{clearTimeout(timer);yes();},{once:true});
    socket.addEventListener('error',()=>{clearTimeout(timer);no(Error('Inspector connection failed'));},{once:true});
  });
  socket.addEventListener('message',event=>{
    const reply=JSON.parse(event.data), item=pending.get(reply.id);if(!item)return;
    pending.delete(reply.id);clearTimeout(item.timer);
    if(reply.error||reply.result?.exceptionDetails)item.no(Error('Host rejected the request; inspect before continuing'));
    else item.yes(reply.result.result.value);
  });
  socket.addEventListener('close',()=>{for(const item of pending.values()){clearTimeout(item.timer);item.no(Error('Inspector disconnected; mutation outcome may be unknown'));}pending.clear();});
  const evaluate=(body,timeout=15000)=>new Promise((yes,no)=>{
    const id=++sequence,timer=setTimeout(()=>{pending.delete(id);no(Error('Host response timed out; do not repeat a mutation'));},timeout);
    pending.set(id,{yes,no,timer});
    try{socket.send(JSON.stringify({id,method:'Runtime.evaluate',params:{expression:`(async()=>{${context}${guard}${body}})()`,returnByValue:true,awaitPromise:true}}));}
    catch(error){pending.delete(id);clearTimeout(timer);no(error);}
  });
  const action=operation=>evaluate(`${quiet}const r=await ${operation};return {application:r.application,changed:r.changed,version:r.version,errorCode:r.error?.code,packageExitCode:r.packageResult?.exitCode,logPath:r.packageResult?.logPath};`,180000);
  return {
    snapshot:()=>evaluate(`return {running:c.get('sessions').list().filter(s=>c.get('agents').get(s.id)?.status==='running').map(s=>s.id),bundles:(await m.listBundles()).map(b=>({name:b.name,version:b.version,enabled:b.enabled,error:b.error?.code??null})),entries:(await m.listPlugins()).map(p=>({name:p.moduleName,phase:p.fiberPhase}))};`),
    disable:pkg=>action(`m.setBundleEnabled(${JSON.stringify(pkg.name)},false)`),
    install:(pkg,requestId)=>action(`m.installBundle(${JSON.stringify(pkg.installSpec)},{enabled:false,saveExact:true,requestId:${JSON.stringify(requestId)}})`),
    enable:pkg=>action(`m.setBundleEnabled(${JSON.stringify(pkg.name)},true)`),
    close:()=>socket.close(),
  };
}
