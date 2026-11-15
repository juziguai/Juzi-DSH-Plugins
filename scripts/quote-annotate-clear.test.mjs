import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {editorBridge} from '../plugins/dsh-quote-annotate/lib/dom-anchors.js';
const viewOf=editor=>({querySelector:()=>({querySelector:()=>({__lexicalEditor:editor})})});
function extractHostLexical(source){
 const regionStart=source.indexOf('//#region ../../../node_modules/.pnpm/lexical@');
 if(regionStart>=0){
  const regionEnd=source.indexOf('//#endregion',regionStart);
  assert(regionEnd>regionStart);
  return source.slice(regionStart,regionEnd);
 }
 const minStart=/function \w+\([^)]*\)\{const \w+=new URL\(["'`]https:\/\/lexical\.dev\/docs\/error["'`]\)/.exec(source)?.index??-1;
 const minEnd=minStart>=0?(source.indexOf('const EMPTY_LABELS=',minStart)>minStart?source.indexOf('const EMPTY_LABELS=',minStart):source.indexOf('var QuoteNode=class',minStart)):-1;
 assert(minStart>=0&&minEnd>minStart,'Unable to locate Lexical runtime in DSH_CONVERSATION_BUNDLE');
 return source.slice(minStart,minEnd);
}
test('quote prefix leaves plain drafts completely outside editor transactions',()=>{
 let updates=0;
 const editor={getEditorState:()=>({_nodeMap:new Map()}),update(){updates++;throw Error('unexpected transaction');}};
 editorBridge(viewOf(editor),'juzi.quote-annotate').prefix([]);
 editorBridge(viewOf(editor),'juzi.quote-annotate').prefix();
 assert.equal(updates,0);
});
test('quote prefix tolerates a root being cleared in an outer transaction',()=>{
 const node={getType:()=> 'reference-chip',__source:'juzi.quote-annotate',__ref:'q1'};
 const editor={getEditorState:()=>({_nodeMap:new Map([['root',{getFirstChild:()=>null}],['q',node]])}),update:fn=>fn()};
 assert.doesNotThrow(()=>editorBridge(viewOf(editor),'juzi.quote-annotate').prefix(['q1']));
});
test('host Lexical keeps committed clear and subsequent typing with nested quote reconciliation',
 {skip:!process.env.DSH_CONVERSATION_BUNDLE},()=>{
 const source=readFileSync(process.env.DSH_CONVERSATION_BUNDLE,'utf8');
 const slice=extractHostLexical(source);
 const L=vm.runInThisContext(`(function(){${slice};return {create:ys,root:nl,paragraph:typeof es$1==='function'?es$1:es,text:Go};})()`);
 for(const nested of [false,true]){
  const editor=L.create({namespace:'clear-regression',onError:e=>{throw e;}});
  editor.update(()=>L.root().append(L.paragraph().append(L.text('sent text'))),{discrete:true});
  editor.update(()=>{L.root().clear();if(nested)editorBridge(viewOf(editor),'juzi.quote-annotate').prefix([]);},{discrete:true});
  assert.equal(editor.getEditorState().read(()=>L.root().getTextContent()),'');
  editor.update(()=>L.root().append(L.paragraph().append(L.text('next draft'))),{discrete:true});
  editorBridge(viewOf(editor),'juzi.quote-annotate').prefix([]);
  assert.equal(editor.getEditorState().read(()=>L.root().getTextContent()),'next draft');
 }
 if(source.includes('var QuoteNode=class')&&source.includes('const HISTORY_MERGE_DELAY_MS=')){
  const start=/function \w+\([^)]*\)\{const \w+=new URL\(["'`]https:\/\/lexical\.dev\/docs\/error["'`]\)/.exec(source).index;
  const end=source.indexOf('const HISTORY_MERGE_DELAY_MS=',start);
  const C=vm.runInNewContext(`(function(){const react_jsx_runtime={jsx:()=>null,jsxs:()=>null};const _deepseek_ai_dsh_client_ui_primitives={QuotePreview:()=>null,ReferenceIconRegular:()=>null,formatQuoteText:t=>'> '+t.split('\\n').join('\\n> ')};${source.slice(start,end)};return {create:ys,root:nl,paragraph:es$1,text:Go,ReferenceChipNode,CommandChipNode,QuoteNode,$createReferenceChipNode,$createQuoteNode,$replaceDetectSpanWithText};})()`,{URL,URLSearchParams,Error,console,Map,Set,WeakMap,WeakSet,Object,Array,Math,Number,String,Symbol,RegExp,queueMicrotask});
  const editor=C.create({namespace:'quote-coexist',nodes:[C.ReferenceChipNode,C.CommandChipNode,C.QuoteNode],onError:e=>{throw e;}});
  editor.update(()=>{const p=C.paragraph();p.append(C.$createQuoteNode('official quoted line'),C.text(' '),C.$createReferenceChipNode({source:'juzi.quote-annotate',ref:'jq:q1',label:'❝ test',clipboardText:'⟦q1⟧'}),C.text('hello'));C.root().append(p);},{discrete:true});
  const b=editorBridge(viewOf(editor),'juzi.quote-annotate');
  assert.equal(b.hasQuotes(),true);
  assert.deepEqual(b.spanOf('jq:q1'),{start:2,end:3});
  let removed=false;editor.update(()=>{removed=C.$replaceDetectSpanWithText(b.spanOf('jq:q1'),'');},{discrete:true});
  assert.equal(removed,true);
  assert.equal(b.spanOf('jq:q1'),null);
 }
});
