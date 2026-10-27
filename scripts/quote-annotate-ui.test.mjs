import test from 'node:test';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {resolve} from 'node:path';import {pathToFileURL} from 'node:url';import {readFileSync} from 'node:fs';import vm from 'node:vm';
import {createQuote,serializeMessage} from '../plugins/dsh-quote-annotate/lib/quote-core.js';
const anchor=process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
test('React/official facade contract: A→B→new A binding, anchor degradation warns once, disposal', {skip:!anchor}, async t=>{
 const req=createRequire(pathToFileURL(resolve(anchor))),R=req('react'),{JSDOM,VirtualConsole}=req('jsdom');
 const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(e.type!=='css parsing')throw e;});
 const dom=new JSDOM('<html><head></head><body><main data-conversation-content data-conversation-session="A"><div data-chat-flow></div><div id="dock"></div><div data-composer-seat><div contenteditable="true" role="textbox"></div></div></main></body></html>',{url:'http://quote.test',pretendToBeVisual:true,virtualConsole:vc});
 const prior={window:globalThis.window,document:globalThis.document,act:globalThis.IS_REACT_ACT_ENVIRONMENT};Object.assign(globalThis,{window:dom.window,document:dom.window.document,IS_REACT_ACT_ENVIRONMENT:true});
 const resizeObservers=new Set();window.ResizeObserver=class{constructor(callback){this.callback=callback;this.targets=[];resizeObservers.add(this);}observe(target){this.targets.push(target);}disconnect(){resizeObservers.delete(this);}};
 const {createRoot}=req('react-dom/client');
 const ownedListeners=new Set(),add=document.addEventListener.bind(document),remove=document.removeEventListener.bind(document);document.addEventListener=(name,fn,options)=>{if(options?.passive&&options?.capture)ownedListeners.add(fn);return add(name,fn,options);};document.removeEventListener=(name,fn,options)=>{ownedListeners.delete(fn);return remove(name,fn,options);};
 const data=createQuote('source',{id:'q1',source:'assistant'},'note');window.localStorage.setItem('juzi.quote-annotate.v1.A',JSON.stringify({v:1,items:[data]}));
 const effects=[],slotDisposers=[],registered=new Map(),warnings=[],inserts=[];let module,current,userRule;
 const editor=document.querySelector('[role=textbox]'),paragraph={getChildren:()=>[],getFirstChild:()=>null,append(){}};editor.__lexicalEditor={getEditorState:()=>({_nodeMap:new Map([['root',{getFirstChild:()=>paragraph}]])}),update:fn=>fn()};
 const observable=(get)=>({getSnapshot:get,subscribe:()=>()=>{}});
 const binding=(id,generation)=>{
  const input={draft:'',draftRev:0,phase:'plain',occurrences:[]};
  const actions={captureInsertion:()=>({start:0,end:0,draftRev:input.draftRev}),insertText:()=>true,persistDraft(){},submit(){throw Error('Unexpected send');}};
  const context={bail(subject,name,{reference}){assert.equal(name,'slash/input-insert-reference');inserts.push(generation);input.draft+=reference.clipboardText;input.occurrences.push({...reference,offset:0,length:reference.clipboardText.length});return true;}};
  const facade={state:observable(()=>input),focus(){},submit(){throw Error('Unexpected send');}};
  const b={sessionId:id,ctx:context,input,actions,facade,eventSource:observable(()=>({entries:[]})),session:{...observable(()=>({promptError:null})),projections:{faceOf:()=>observable(()=>undefined)}}};return b;
 };
 const oldA=binding('A','A1'),b=binding('B','B1'),newA=binding('A','A2');current=oldA;
 window.__ModuleLoader__={load:({factory})=>{module=factory(id=>{assert.equal(id,'react');return R;});}};
 vm.runInThisContext(readFileSync(new URL('../plugins/dsh-quote-annotate/lib/client.js',import.meta.url),'utf8'));
 const dictionaries={};
 const ctx={effect(fn){const dispose=fn();if(dispose)effects.push(dispose);},logger:{warn:m=>warnings.push(m)},get:name=>name==='uiConversation'?{userText:{register(rule){userRule=rule;return()=>{userRule=undefined;};}}}:undefined,
  locale:{register(ns,dicts){dictionaries[ns]=dicts;return()=>delete dictionaries[ns];},bind:ns=>(key,params={})=>(dictionaries[ns]?.en[key]??key).replace(/\{(\w+)\}/g,(_,name)=>params[name]??''),subscribe:()=>()=>{}},
  sessions:{binding:()=>current,list:observable(()=>({phase:'ready',ids:['A','B']}))},conversation:{input:{for:scope=>[oldA,b,newA].find(x=>x.ctx===scope).facade}},
  inputTriggers:{sessionOf:()=>({lexicon:observable(()=>new Map())}),registerSource(){return()=>{};}},
  slots:{inject(name,fn){const dispose=fn();slotDisposers.push(dispose);},register(spec,component){registered.set(spec.name,component);return()=>registered.delete(spec.name);}}
 };
 const root=createRoot(document.getElementById('dock'));
 try{
  module.apply(ctx);const Dock=registered.get('conversation.input.dock');assert(Dock);
  const render=async target=>{current=target;document.querySelector('main').dataset.conversationSession=target.sessionId;await R.act(async()=>root.render(R.createElement(Dock,{sessionId:target.sessionId,inputActions:target.actions,useInput:select=>select(target.input)})));};
  await render(oldA);await render(b);await render(newA);assert.deepEqual(inserts,['A1','A2']);assert(!warnings.some(w=>/unavailable/.test(w)));
  assert(document.querySelector('style[data-jq]'));
  const chat=document.querySelector('[data-chat-flow]');chat.textContent='Selected source';const range=document.createRange();range.selectNodeContents(chat);document.getSelection().addRange(range);chat.removeAttribute('data-chat-flow');
  t.mock.timers.enable({apis:['setTimeout']});
  for(let i=0;i<3;i++)await R.act(async()=>{document.dispatchEvent(new window.Event('selectionchange'));t.mock.timers.tick(151);});
  assert.equal(warnings.filter(w=>w.endsWith('selection anchors unavailable')).length,1);assert.equal(document.querySelectorAll('.jq-bubble').length,0);
  chat.setAttribute('data-chat-flow','');chat.getBoundingClientRect=()=>({left:0,right:400,top:0,bottom:400});document.querySelector('[data-composer-seat]').getBoundingClientRect=()=>({top:400});let rangeRects=[{left:20,right:180,top:120,bottom:140,width:160,height:20}];window.Range.prototype.getClientRects=()=>rangeRects;
  const overlayNode=document.createElement('div');document.body.append(overlayNode);const overlayRoot=createRoot(overlayNode);await R.act(async()=>overlayRoot.render(R.createElement(registered.get('shell.overlay'))));
  try{
   const select=async()=>R.act(async()=>{const next=document.createRange();next.selectNodeContents(chat);document.getSelection().removeAllRanges();document.getSelection().addRange(next);assert.equal(document.getSelection().toString(),'Selected source');t.mock.timers.tick(0);document.dispatchEvent(new window.Event('selectionchange'));t.mock.timers.tick(151);});
   newA.input.phase='blocked';await select();assert.equal(document.querySelectorAll('.jq-bubble').length,0);
   newA.input.phase='plain';await select();assert(document.querySelector('.jq-bubble'));
   await R.act(async()=>document.querySelector('.jq-bubble').click());assert(document.querySelector('.jq-comment'));
   assert.equal(document.querySelector('.jq-compose').querySelectorAll('button').length,1);
   assert.equal(document.querySelector('.jq-selection-number').textContent,'2');assert.equal(document.querySelectorAll('.jq-selection-mark').length,1);
   assert.equal(resizeObservers.size,1);assert([...resizeObservers][0].targets.includes(chat));
   rangeRects=[{left:45,right:205,top:150,bottom:170,width:160,height:20}];
   await R.act(async()=>{for(const observer of resizeObservers)observer.callback();await new Promise(done=>window.requestAnimationFrame(done));});
   assert.equal(document.querySelector('.jq-selection-mark').style.left,'45px');assert.equal(document.querySelector('.jq-selection-mark').style.top,'150px');
   assert.equal(document.querySelector('.jq-confirm').getAttribute('aria-label'),'Add');
   const normalBefore=inserts.length;
   await R.act(async()=>document.querySelector('.jq-comment').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true})));
   assert.equal(inserts.length,normalBefore);assert(document.querySelector('.jq-compose'));
   await R.act(async()=>document.querySelector('.jq-confirm').click());assert.equal(inserts.length,normalBefore+1);assert.equal(document.querySelectorAll('.jq-selection').length,0);
   await select();await R.act(async()=>document.querySelector('.jq-bubble').click());
   assert.equal(document.querySelector('.jq-selection-number').textContent,'3');
   await R.act(async()=>document.querySelector('.jq-comment').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true})));
   assert.equal(document.querySelectorAll('.jq-compose').length,0);assert.equal(document.querySelectorAll('.jq-selection').length,0);assert.equal(inserts.length,normalBefore+1);
   await select();await R.act(async()=>document.querySelector('.jq-bubble').click());const before=inserts.length;
   newA.input.phase='blocked';await R.act(async()=>document.querySelector('.jq-comment').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true})));assert.equal(inserts.length,before);assert.equal(document.querySelectorAll('.jq-comment').length,0);
  }finally{newA.input.phase='plain';await R.act(async()=>overlayRoot.unmount());assert.equal(resizeObservers.size,0);overlayNode.remove();t.mock.timers.reset();}
  const wire=serializeMessage([createQuote('<script>plain text</script>',{},'A comment')],'unchanged request'),candidate=userRule.match(wire,0);assert.equal(userRule.match(wire,1),undefined);assert.equal(wire.slice(candidate.end),'unchanged request');
  const sentNode=document.createElement('div');document.body.append(sentNode);const sentRoot=createRoot(sentNode);try{await R.act(async()=>sentRoot.render(R.createElement(registered.get('conversation.user.text.node'),{node:candidate,raw:wire})));assert(!sentNode.textContent.includes('<juzi-quotes'));assert.equal(sentNode.querySelector('button').getAttribute('aria-expanded'),'false');await R.act(async()=>sentNode.querySelector('button').click());assert.equal(sentNode.querySelector('.jq-sent-original').textContent,'<script>plain text</script>');assert.equal(sentNode.querySelectorAll('script').length,0);assert.equal(sentNode.querySelector('.jq-sent-note').textContent,'A comment');}finally{await R.act(async()=>sentRoot.unmount());sentNode.remove();}
 }finally{await R.act(async()=>root.unmount());for(const dispose of effects.toReversed())dispose();for(const dispose of slotDisposers)dispose?.();assert.equal(userRule,undefined);assert.equal(ownedListeners.size,0);assert.equal(document.querySelectorAll('style[data-jq]').length,0);assert.equal(registered.size,0);dom.window.close();Object.assign(globalThis,{window:prior.window,document:prior.document,IS_REACT_ACT_ENVIRONMENT:prior.act});}
});
test('actual SlotCore registers and releases the four browser seats',{skip:!process.env.DSH_SLOT_CORE_MODULE},async()=>{
 const {SlotCore}=await import(pathToFileURL(process.env.DSH_SLOT_CORE_MODULE));const core=new SlotCore(),off=[];const seats=['conversation.input.dock','shell.overlay','conversation.chat.assistant-actions','conversation.user.text.node'];
 const root=core.register({name:'root',children:Object.fromEntries(seats.map(name=>[name,{kind:name==='conversation.user.text.node'?'keyed':'list',scope:name==='shell.overlay'?'global':'session'}]))},()=>null);
 let plugin;vm.runInNewContext(readFileSync(new URL('../plugins/dsh-quote-annotate/lib/client.js',import.meta.url),'utf8'),{crypto:globalThis.crypto,window:{addEventListener(){},__ModuleLoader__:{load:({factory})=>{plugin=factory(()=>({}));}}}});
 plugin.apply({effect(){},locale:{bind:()=>key=>key},logger:{warn(){}},slots:{inject:(name,fn)=>off.push(fn()),register:(spec,body)=>core.register(spec,body)}});
 for(const seat of seats)assert.equal(core.entries(seat).length,1);for(const dispose of off.toReversed())dispose();for(const seat of seats)assert.equal(core.entries(seat).length,0);root();
});
