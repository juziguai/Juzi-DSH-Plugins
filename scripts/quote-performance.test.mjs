import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { createQuote, serializeMessage, QUOTE_SOURCE } from '../plugins/dsh-quote-annotate/lib/quote-core.js';
import { extractSelection, createVisibleTextIndex } from '../plugins/dsh-quote-annotate/lib/dom-anchors.js';
const anchor = process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;

test('unmounted quote views release subscriptions; pending sends retain only acknowledgement observers', { skip: !anchor }, async t => {
  const req = createRequire(pathToFileURL(resolve(anchor))), R = req('react'), { JSDOM, VirtualConsole } = req('jsdom');
  const vc = new VirtualConsole(); vc.on('jsdomError', e => { if(e.type !== 'css parsing') throw e; });
  const dom = new JSDOM('<html><head></head><body></body></html>', { url: 'http://fixture.invalid', pretendToBeVisual: true, virtualConsole: vc });
  const prior = {window: globalThis.window, document: globalThis.document, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT};
  Object.assign(globalThis, {window: dom.window, document: dom.window.document, IS_REACT_ACT_ENVIRONMENT: true});
  const { createRoot } = req('react-dom/client');
  const effects = [], registered = new Map(), bindings = new Map(); let module, source, subscriptions = 0;
  const observable = getSnapshot => {
    const listeners = new Set();
    return { getSnapshot, emit: () => { for(const fn of [...listeners])fn(); }, subscribe: fn => { subscriptions++; listeners.add(fn); return () => { if(listeners.delete(fn))subscriptions--; }; } };
  };
  window.__ModuleLoader__ = {load: ({factory}) => { module = factory(() => R); }};
  vm.runInThisContext(readFileSync(new URL('../plugins/dsh-quote-annotate/lib/client.js', import.meta.url), 'utf8'));
  module.apply({
    effect(fn) { const off=fn(); if(off)effects.push(off); }, logger: {warn(){}},
    get: () => ({userText: {register: () => () => {}}}),
    locale: {register: () => () => {}, bind: () => key => key, subscribe: () => () => {}},
    sessions: {binding: id => bindings.get(id), list: observable(() => ({phase: 'ready', ids: [...bindings.keys()]}))},
    conversation: {input: {for: context => context.facade}},
    inputTriggers: {sessionOf: () => ({lexicon: observable(() => new Map())}), registerSource: value => {source=value;return()=>{};}},
    slots: {inject: (_name, fn) => fn(), register: (spec, component) => { registered.set(spec.name, component); return () => registered.delete(spec.name); }}
  });
  t.after(() => { for(const off of effects.reverse())off(); assert.equal(subscriptions,0);dom.window.close();Object.assign(globalThis,prior); });
  const baseline = subscriptions;
  const mount = async (id, quote) => {
    let b=bindings.get(id);
    if(!b){
      const ref=quote?{source:QUOTE_SOURCE,ref:`jq:${quote.id}`,clipboardText:`⟦${quote.id}⟧`,offset:0,length:`⟦${quote.id}⟧`.length}:undefined;
      const state={draft:ref?ref.clipboardText+'request':'',occurrences:ref?[ref]:[],phase:'submitting'},entries=[];
      const facade={state:observable(()=>state),focus(){}};
      b={ctx:{facade},state,entries,eventSource:observable(()=>({entries})),session:{...observable(()=>({promptError:null})),projections:{faceOf:()=>observable(()=>undefined)}}};bindings.set(id,b);
      if(quote)window.localStorage.setItem(`juzi.quote-annotate.v1.${id}`,JSON.stringify({v:1,items:[quote]}));
    }
    const view=document.createElement('main');view.dataset.conversationContent='';view.dataset.conversationSession=id;
    const seat=document.createElement('div');view.append(seat);document.body.append(view);const root=createRoot(seat);
    await R.act(async()=>root.render(R.createElement(registered.get('conversation.input.dock'),{sessionId:id,useInput:fn=>fn(b.state),inputActions:{}})));
    return async()=>{await R.act(async()=>root.unmount());view.remove();};
  };
  for(let i=0;i<10;i++){const unmount=await mount(`fixture-${i}`);await unmount();assert.equal(subscriptions,baseline);}
  const one=await mount('shared'),two=await mount('shared');
  assert.equal(subscriptions-baseline,3);await one();assert.equal(subscriptions-baseline,3);await two();assert.equal(subscriptions,baseline);
  const quote=createQuote('source',{id:'pending-quote'}),unmount=await mount('pending',quote);
  await source.codec.serialize(`jq:${quote.id}`,new AbortController().signal);
  await unmount();assert.equal(subscriptions-baseline,2);
  const b=bindings.get('pending');b.entries.push({seq:1,type:'user/message',data:{type:'text',text:serializeMessage([quote],'request').trim()}});
  b.eventSource.emit();assert.equal(subscriptions,baseline);
  assert.equal(JSON.parse(window.localStorage.getItem('juzi.quote-annotate.v1.pending')).items.length,0);
});

test('small selection and visible-message obstacles do not traverse hidden conversation text', {skip:!anchor}, () => {
  const req=createRequire(pathToFileURL(resolve(anchor))),{JSDOM}=req('jsdom');
  const dom=new JSDOM('<main data-conversation-content data-conversation-session="A"><div data-chat-flow>'+Array.from({length:1000},(_,i)=>`<p data-chat-node-key="${i}">message ${i}</p>`).join('')+'</div></main>');
  const {document,HTMLElement,Range}=dom.window;const rect={left:0,right:500,top:0,bottom:20,width:500,height:20};
  let reads=0,visits=0,deliver,disconnected=false;
  HTMLElement.prototype.getBoundingClientRect=()=>{reads++;return rect;};Range.prototype.getClientRects=()=>[rect];
  const create=document.createTreeWalker.bind(document);document.createTreeWalker=(...args)=>{const w=create(...args),next=w.nextNode.bind(w);w.nextNode=()=>{const n=next();if(n)visits++;return n;};return w;};
  dom.window.IntersectionObserver=class{constructor(callback){deliver=callback;}observe(){}unobserve(){}disconnect(){disconnected=true;}};
  const view=document.querySelector('main'),rows=[...document.querySelectorAll('p')],index=createVisibleTextIndex(view);
  deliver(rows.map((target,i)=>({target,isIntersecting:i===0})));
  const range=document.createRange();range.selectNodeContents(rows[0]);const hit=extractSelection({isCollapsed:false,rangeCount:1,getRangeAt:()=>range},'A');
  assert.equal(hit.text,'message 0');assert.equal(index.rects(hit.bounds).length,1);
  assert.ok(visits<=3,`visited ${visits}`);assert.ok(reads<=4,`layout reads ${reads}`);
  index.dispose();assert.equal(disconnected,true);dom.window.close();
});
