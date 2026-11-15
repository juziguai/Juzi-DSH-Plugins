import test from 'node:test';import assert from 'node:assert/strict';import {createRequire} from 'node:module';import {resolve} from 'node:path';import {pathToFileURL} from 'node:url';import {readFileSync} from 'node:fs';import vm from 'node:vm';
import {createQuote,serializeMessage,serializePrefix,QUOTE_SOURCE} from '../plugins/dsh-quote-annotate/lib/quote-core.js';
async function loadSlotCore(modulePath){
 const source=readFileSync(modulePath,'utf8');
 const m=/const (\w+)=Object\.freeze\(Object\.defineProperty\(\{__proto__:null,SlotCore:(\w+),[^}]*standardHookPropName:(\w+)\},Symbol\.toStringTag,\{value:"Module"\}\)\)/.exec(source);
 if(m){
  const start=source.indexOf(`function ${m[3]}(`);assert(start>=0);
  return vm.runInNewContext(`(function(){${source.slice(start,m.index+m[0].length)};return ${m[1]};})()`,{queueMicrotask}).SlotCore;
 }
 return (await import(pathToFileURL(resolve(modulePath)))).SlotCore;
}
function createMiniReact(){
 const Fragment=Symbol('Fragment');
 let currentComp=null;
 const mount=()=>({hooks:[],layout:[],passive:[],vnode:null,element:null,comp:null,props:null,render(comp,props){
  this.comp=comp;this.props=props;this.idx=0;const prev=currentComp;currentComp=this;
  let nextLayout=[],nextPassive=[];this.pendingLayout=nextLayout;this.pendingPassive=nextPassive;
  try{this.vnode=evalTree(comp(props));}finally{currentComp=prev;}
  runEffects(this.layout,nextLayout);this.layout=nextLayout;
  runEffects(this.passive,nextPassive);this.passive=nextPassive;
  return this.vnode;
 },unmount(){for(const e of [...this.layout,...this.passive])e.cleanup?.();this.layout=[];this.passive=[];}});
 const runEffects=(prev,next)=>{for(let i=0;i<next.length;i++){const old=prev[i],cur=next[i];if(old&&cur.deps&&old.deps&&cur.deps.length===old.deps.length&&cur.deps.every((d,j)=>Object.is(d,old.deps[j]))){cur.cleanup=old.cleanup;continue;}old?.cleanup?.();cur.cleanup=cur.fn()||undefined;}};
 const evalTree=node=>{
  if(node==null||typeof node==='boolean'||typeof node==='string'||typeof node==='number')return node;
  if(Array.isArray(node))return node.map(evalTree);
  if(node.type===Fragment)return (node.children??[]).map(evalTree);
  if(typeof node.type==='function'){
   const prev=currentComp,inst={hooks:[],idx:0,pendingLayout:[],pendingPassive:[]};currentComp=inst;
   let out;try{out=evalTree(node.type(node.props??{}));}finally{currentComp=prev;}
   for(const e of inst.pendingLayout)e.cleanup=e.fn()||undefined;
   for(const e of inst.pendingPassive)e.cleanup=e.fn()||undefined;
   currentComp?.pendingLayout.push(...inst.pendingLayout.map(e=>({fn:()=>e.cleanup,deps:[]})));
   return out;
  }
  const hostView=currentComp?.hostView??null;
  if(node.props?.ref&&typeof node.props.ref==='object')node.props.ref.current=node.domStub??{closest:()=>hostView,offsetWidth:320,offsetHeight:48,scrollHeight:20,scrollTop:0,style:{},focus(){},querySelector:()=>({focus(){}}),querySelectorAll:()=>[]};
  return {...node,children:(node.children??[]).map(evalTree)};
 };
 const findAll=(tree,pred,out=[])=>{if(!tree||typeof tree!=='object')return out;if(Array.isArray(tree)){for(const c of tree)findAll(c,pred,out);return out;}if(pred(tree))out.push(tree);for(const c of tree.children??[])findAll(c,pred,out);return out;};
 return {
  Fragment,mount,findAll,
  createElement:(type,props,...children)=>({type,props:props??{},children:children.flat()}),
  useRef:init=>{const c=currentComp,i=c.idx++;return c.hooks[i]??(c.hooks[i]={current:init});},
  useState:init=>{const c=currentComp,i=c.idx++;if(!(i in c.hooks))c.hooks[i]=typeof init==='function'?init():init;return [c.hooks[i],v=>{c.hooks[i]=typeof v==='function'?v(c.hooks[i]):v;}];},
  useReducer:(red,init)=>{const c=currentComp,i=c.idx++;if(!(i in c.hooks))c.hooks[i]=init;return [c.hooks[i],a=>{c.hooks[i]=red(c.hooks[i],a);}];},
  useId:()=>'jq-id',
  useSyncExternalStore:(_sub,get)=>get(),
  useLayoutEffect:(fn,deps)=>{currentComp.pendingLayout.push({fn,deps});},
  useEffect:(fn,deps)=>{currentComp.pendingPassive.push({fn,deps});}
 };
}
test('0.2.2 client integration: sending freeze guard, QuoteNode spanOf/observe coexistence, native toolbar obstacle avoidance, menu material, and window-drag-exclude',async()=>{
 const R=createMiniReact();
 const storageData=new Map(),storage={get length(){return storageData.size;},key:i=>[...storageData.keys()][i],getItem:k=>storageData.get(k)??null,setItem:(k,v)=>storageData.set(k,v),removeItem:k=>storageData.delete(k)};
 storage.setItem('juzi.quote-annotate.v1.S1',JSON.stringify({v:1,items:[createQuote('alpha',{id:'q1',source:'assistant'},'note')]}));
 let lexicalNodes=[],nativeSurfaceRects=[],menuEls=[],selectionHit=null,docListeners=new Map();
 const paragraph={getChildren:()=>lexicalNodes,getFirstChild:()=>lexicalNodes[0]??null,append(n){lexicalNodes.push(n);}};
 const lexicalEditor={
  getEditorState:()=>({_nodeMap:new Map([['root',{getChildren:()=>[paragraph],getFirstChild:()=>paragraph}],...lexicalNodes.map((n,i)=>[`n${i}`,n])]),read:fn=>fn()}),
  update:fn=>fn()
 };
 const chatEl={ownerDocument:null,contains:()=>true,closest:()=>null,getBoundingClientRect:()=>({left:0,top:0,right:500,bottom:500})};
 const editorEl={__lexicalEditor:lexicalEditor};
 const composerEl={querySelector:sel=>sel.includes('textbox')?editorEl:null,getBoundingClientRect:()=>({top:500})};
 let chipEls=[];
 const view={isConnected:true,dataset:{conversationSession:'S1'},parentElement:null,ownerDocument:null,
  matches:()=>false,closest:sel=>sel.includes('data-conversation-content')?view:null,
  querySelector:sel=>sel==='[data-chat-flow]'?chatEl:sel==='[data-composer-seat]'?composerEl:null,
  querySelectorAll:sel=>sel.includes('data-composer-chip')?chipEls:[],
  getBoundingClientRect:()=>({left:0,top:0,right:500,bottom:500,width:500,height:500})
 };
 const doc={
  defaultView:null,activeElement:null,
  head:{append(){}},createElement:()=>({dataset:{},style:{},remove(){}}),
  addEventListener:(n,fn)=>{docListeners.set(n,fn);},removeEventListener:(n)=>{docListeners.delete(n);},
  getSelection:()=>selectionHit,
  createTreeWalker:()=>({nextNode:()=>null}),createRange:()=>({selectNodeContents(){},getClientRects:()=>[]}),
  querySelectorAll:sel=>{
   if(sel.includes('data-text-interaction-surface'))return nativeSurfaceRects;
   if(sel.includes('data-menu-material'))return menuEls;
   if(sel.includes('data-conversation-content'))return [view];
   return [];
  }
 };
 chatEl.ownerDocument=view.ownerDocument=doc;
 const winListeners=new Map();
 const win={innerWidth:800,innerHeight:600,localStorage:storage,document:doc,
  addEventListener:(n,fn)=>{winListeners.set(n,fn);},removeEventListener:(n)=>{winListeners.delete(n);},
  setTimeout,clearTimeout,
  requestAnimationFrame:fn=>setTimeout(fn,0),cancelAnimationFrame:id=>clearTimeout(id),
  MutationObserver:class{observe(){}disconnect(){}},
  getComputedStyle:el=>el._style??{display:'block',visibility:'visible',opacity:'1',lineHeight:'20px'},
  __ModuleLoader__:{load:({factory})=>{win._plugin=factory(id=>{assert.equal(id,'react');return R;});}}
 };
 doc.defaultView=win;
 const priorGlobals={window:globalThis.window,document:globalThis.document,innerWidth:globalThis.innerWidth,innerHeight:globalThis.innerHeight};
 Object.assign(globalThis,{window:win,document:doc,innerWidth:800,innerHeight:600});
 try{
 vm.runInThisContext(readFileSync(new URL('../plugins/dsh-quote-annotate/lib/client.js',import.meta.url),'utf8'));
 const inputSubs=new Set(),sessionSubs=new Set(),eventSubs=new Set();
 const inputState={draft:'',draftRev:1,phase:'plain',occurrences:[]};
 const removedSpans=[];
 const syncFromLexical=()=>{
  let draft='',occurrences=[];
  for(const n of lexicalNodes){
   const txt=n.getTextContent?.()??'';
   if(n.getType?.()==='reference-chip')occurrences.push({source:n.__source,ref:n.__ref,clipboardText:txt,offset:draft.length,length:txt.length});
   draft+=txt;
  }
  inputState.draft=draft;inputState.occurrences=occurrences;
 };
 const inputActions={
  captureInsertion:()=>({start:0,end:0,draftRev:inputState.draftRev}),
  insertText:(txt,span)=>{if(inputState.phase!=='plain'&&inputState.phase!=='claimed')return false;removedSpans.push({txt,span});if(span.start>=0&&span.end<=lexicalNodes.length){lexicalNodes.splice(span.start,span.end-span.start,...(txt?[{getType:()=> 'text',getTextContent:()=>txt}]:[]));syncFromLexical();}return true;}
 };
 const entries=[],sessionSnap={promptError:null,pendingSubmissions:[]};
 const binding={
  sessionId:'S1',
  ctx:{bail(_s,name,{reference,span}){assert.equal(name,'slash/input-insert-reference');const chip={getType:()=> 'reference-chip',__source:reference.source,__ref:reference.ref,getTextContent:()=>reference.clipboardText,insertBefore(){}};lexicalNodes.splice(span.start,span.end-span.start,chip,{getType:()=> 'text',getTextContent:()=> ' '});syncFromLexical();chipEls=[{closest:s=>s.includes('chip')?chipEls[0]:view,getBoundingClientRect:()=>({left:20,top:420,right:120,bottom:444})}];return true;}},
  eventSource:{getSnapshot:()=>({entries}),subscribe:fn=>(eventSubs.add(fn),()=>eventSubs.delete(fn))},
  session:{getSnapshot:()=>sessionSnap,subscribe:fn=>(sessionSubs.add(fn),()=>sessionSubs.delete(fn)),projections:{faceOf:()=>({getSnapshot:()=>undefined})}}
 };
 let triggerSource;const seats=new Map(),effects=[];
 const dicts={};
 win._plugin.apply({
  effect(fn){const d=fn();if(d)effects.push(d);},
  logger:{warn(){}},
  get:()=>({userText:{register:()=>()=>{}}}),
  locale:{register:(ns,d)=>{dicts[ns]=d;return()=>{};},bind:ns=>(k,p={})=>(dicts[ns]?.en[k]??k).replace(/\{(\w+)\}/g,(_,n)=>p[n]??''),subscribe:()=>()=>{}},
  sessions:{binding:id=>id==='S1'?binding:undefined,list:{getSnapshot:()=>({phase:'ready',ids:['S1']}),subscribe:()=>()=>{}}},
  conversation:{input:{for:()=>({state:{getSnapshot:()=>inputState,subscribe:fn=>(inputSubs.add(fn),()=>inputSubs.delete(fn))},focus(){}})}},
  inputTriggers:{sessionOf:()=>({lexicon:{getSnapshot:()=>new Map()}}),registerSource:s=>{triggerSource=s;return()=>{};}},
  slots:{inject:(_n,fn)=>{effects.push(fn());},register:(spec,comp)=>{seats.set(spec.name,comp);return()=>seats.delete(spec.name);}}
 });
 const dockMount=R.mount();dockMount.hostView=view;
 const overlayMount=R.mount();
 const renderBoth=()=>{
  const dockTree=dockMount.render(seats.get('conversation.input.dock'),{sessionId:'S1',inputActions,useInput:sel=>sel(inputState)});
  const overlayTree=overlayMount.render(seats.get('shell.overlay'),{});
  return {dockTree,overlayTree};
 };
 renderBoth();
 assert.equal(inputState.occurrences.length,1);

 // 1. 'sending' phase preserves store items during in-flight clear and blocks removeItem + Clear All
 const savedOccurrences=[...inputState.occurrences],savedNodes=[...lexicalNodes];
 inputState.phase='sending';inputState.occurrences=[];
 for(const fn of inputSubs)fn();
 assert(JSON.parse(storage.getItem('juzi.quote-annotate.v1.S1')).items.length===1,'sending phase must not purge stored quotes');
 inputState.occurrences=savedOccurrences;lexicalNodes=savedNodes;removedSpans.length=0;
 let {dockTree}=renderBoth();
 const deleteBtnSending=R.findAll(dockTree,n=>n.type==='button'&&n.props['aria-label']==='Delete quote 1')[0];
 deleteBtnSending.props.onClick();
 ({dockTree}=renderBoth());
 assert(R.findAll(dockTree,n=>n.props?.className==='jq-alert')[0]?.children.includes('This conversation cannot edit a draft right now'));
 assert.equal(removedSpans.length,0);
 const clearBtnSending=R.findAll(dockTree,n=>n.type==='button'&&n.children?.includes('Clear all'))[0];
 clearBtnSending.props.onClick();
 assert.equal(JSON.parse(storage.getItem('juzi.quote-annotate.v1.S1')).items.length,1);

 // 2. Exact Lexical spanOf removal when a native QuoteNode precedes jq:q1
 inputState.phase='plain';removedSpans.length=0;
 const quoteText='> official line 1\n> official line 2';
 const nativeQuoteNode={getType:()=> 'quote',getTextContent:()=> quoteText};
 const spaceNode={getType:()=> 'text',getTextContent:()=> ' '};
 const jqChip=lexicalNodes[0];
 lexicalNodes=[nativeQuoteNode,spaceNode,jqChip];
 inputState.draft=`${quoteText} ⟦q1⟧`;
 inputState.occurrences=[{source:QUOTE_SOURCE,ref:'jq:q1',clipboardText:'⟦q1⟧',offset:quoteText.length+1,length:4}];
 ({dockTree}=renderBoth());
 const deleteBtnPlain=R.findAll(dockTree,n=>n.type==='button'&&n.props['aria-label']==='Delete quote 1')[0];
 deleteBtnPlain.props.onClick();
 assert(removedSpans.some(r=>r.span.start===2&&r.span.end===3),'removeChip must use Lexical spanOf (2..3) instead of occurrences clipboard offset');
 assert.equal(JSON.parse(storage.getItem('juzi.quote-annotate.v1.S1')).items.length,0);

 // 3. Native QuoteNode coexistence during serialize + observe confirmation
 const q2=createQuote('beta',{id:'q2',source:'assistant'},'c2');
 lexicalNodes=[nativeQuoteNode];inputState.draft=quoteText;inputState.occurrences=[];
 storage.setItem('juzi.quote-annotate.v1.S1',JSON.stringify({v:1,items:[q2]}));
 winListeners.get('storage')?.({key:'juzi.quote-annotate.v1.S1',newValue:storage.getItem('juzi.quote-annotate.v1.S1')});
 const sig=new AbortController().signal;
 const serialized=await triggerSource.codec.serialize('jq:q2',sig);
 const prefix=serializePrefix([q2]);
 assert.equal(serialized,prefix);
 // Host normalizeQuoteBoundaries turns trailing '\n' before QuoteNode into '\n\n> ...'
 entries.push({seq:1,type:'user/message',data:{content:[{type:'text',text:`${prefix.trimEnd()}\n\n${quoteText}`}]}});
 for(const fn of eventSubs)fn();
 assert.equal(JSON.parse(storage.getItem('juzi.quote-annotate.v1.S1')).items.length,0,'observe must confirm send when native QuoteNode reformats trailing boundary');

 // 4. Floating bubble avoids visible [data-text-interaction-surface], respects [data-menu-material], and sets data-window-drag-exclude
 const selText={nodeType:3,textContent:'Quoted chat text',parentElement:null,ownerDocument:doc};
 const rowEl={nodeType:1,dataset:{chatNodeKey:'row1',chatFlowKind:'assistant-step'},parentElement:chatEl,ownerDocument:doc,
  closest:sel=>sel.includes('data-chat-node-key')?rowEl:sel.includes('data-conversation-content')?view:null,
  querySelector:()=>null,getBoundingClientRect:()=>({left:20,top:120,right:180,bottom:140,width:160,height:20})};
 selText.parentElement=rowEl;
 doc.createTreeWalker=()=>({idx:0,nextNode(){return this.idx++===0?selText:null;}});
 const selRange={
  commonAncestorContainer:selText,startContainer:selText,startOffset:0,endContainer:selText,endOffset:selText.textContent.length,
  intersectsNode:()=>true,compareBoundaryPoints:()=>1,
  getClientRects:()=>[{left:40,top:120,right:160,bottom:140,width:120,height:20}],
  selectNodeContents(){},setStart(){},setEnd(){},toString:()=>selText.textContent,cloneRange(){return this;}
 };
 selectionHit={isCollapsed:false,rangeCount:1,toString:()=>selText.textContent,getRangeAt:()=>selRange};
 // Hidden native surface is ignored -> bubble sits at 'top' (x = 146..174, y = 84..112)
 nativeSurfaceRects=[{_style:{display:'block',visibility:'hidden',opacity:'1'},getBoundingClientRect:()=>({left:120,top:84,right:200,bottom:112,width:80,height:28})}];
 docListeners.get('pointerup')();await new Promise(r=>setTimeout(r,95));
 let {overlayTree}=renderBoth();
 let bubble=R.findAll(overlayTree,n=>n.props?.className?.includes('jq-bubble'))[0];
 assert(bubble);assert.equal(bubble.props['data-jq-side'],'top');
 assert.equal(bubble.props['data-window-drag-exclude'],'');
 const rootBox=R.findAll(overlayTree,n=>n.props?.className==='jq-root')[0];
 assert.equal(rootBox.props['data-window-drag-exclude'],undefined);
 // Visible native surface at top -> bubble steps aside off 'top'
 nativeSurfaceRects=[{_style:{display:'block',visibility:'visible',opacity:'1'},getBoundingClientRect:()=>({left:120,top:84,right:200,bottom:112,width:80,height:28})}];
 docListeners.get('pointerup')();await new Promise(r=>setTimeout(r,95));
 ({overlayTree}=renderBoth());
 bubble=R.findAll(overlayTree,n=>n.props?.className?.includes('jq-bubble'))[0];
 assert(bubble);assert.notEqual(bubble.props['data-jq-side'],'top');
 // Clicking bubble opens .jq-compose with data-window-drag-exclude
 bubble.props.onClick();
 ({overlayTree}=renderBoth());
 const compose=R.findAll(overlayTree,n=>n.props?.className?.includes('jq-compose'))[0];
 assert(compose);assert.equal(compose.props['data-window-drag-exclude'],'');
 // Escape closes compose; open preview via openReference and verify .jq-card has data-window-drag-exclude
 const q3=createQuote('gamma',{id:'q3',source:'assistant'},'c3');
 lexicalNodes=[];inputState.draft='';inputState.occurrences=[];
 storage.setItem('juzi.quote-annotate.v1.S1',JSON.stringify({v:1,items:[q3]}));
 winListeners.get('storage')?.({key:'juzi.quote-annotate.v1.S1',newValue:storage.getItem('juzi.quote-annotate.v1.S1')});
 compose.props.onKeyDown({key:'Escape',stopPropagation(){},preventDefault(){}});
 triggerSource.openReference({sessionId:'S1'},{ref:'jq:q3'});
 ({overlayTree}=renderBoth());
 const card=R.findAll(overlayTree,n=>n.props?.className?.includes('jq-card'))[0];
 assert(card);assert.equal(card.props['data-window-drag-exclude'],'');
 // Opening a 0.2.2 [data-menu-material] menu hides floating layers
 menuEls=[{closest:()=>null,getClientRects:()=>[{width:120,height:80}]}];
 docListeners.get('pointerup')();await new Promise(r=>setTimeout(r,95));
 ({overlayTree}=renderBoth());
 assert.equal(R.findAll(overlayTree,n=>n.props?.className?.includes('jq-card')).length,0);
 dockMount.unmount();overlayMount.unmount();for(const d of effects.reverse())d?.();
 }finally{Object.assign(globalThis,priorGlobals);}
});
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
   assert(document.querySelector('.jq-bubble').hasAttribute('data-window-drag-exclude'));
   await R.act(async()=>document.querySelector('.jq-bubble').click());assert(document.querySelector('.jq-comment'));
   assert(document.querySelector('.jq-compose').hasAttribute('data-window-drag-exclude'));
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
 const SlotCore=await loadSlotCore(process.env.DSH_SLOT_CORE_MODULE);const core=new SlotCore(),off=[];const seats=['conversation.input.dock','shell.overlay','conversation.chat.assistant-actions','conversation.user.text.node'];
 const root=core.register({name:'root',children:Object.fromEntries(seats.map(name=>[name,{kind:name==='conversation.user.text.node'?'keyed':'list',scope:name==='shell.overlay'?'root':'session'}]))},()=>null);
 let plugin;vm.runInNewContext(readFileSync(new URL('../plugins/dsh-quote-annotate/lib/client.js',import.meta.url),'utf8'),{crypto:globalThis.crypto,window:{addEventListener(){},__ModuleLoader__:{load:({factory})=>{plugin=factory(()=>({}));}}}});
 plugin.apply({effect(){},locale:{bind:()=>key=>key},logger:{warn(){}},slots:{inject:(name,fn)=>off.push(fn()),register:(spec,body)=>core.register(spec,body)}});
 for(const seat of seats)assert.equal(core.entries(seat).length,1);for(const dispose of off.toReversed())dispose();for(const seat of seats)assert.equal(core.entries(seat).length,0);root();
});
