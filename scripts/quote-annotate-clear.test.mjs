import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {editorBridge} from '../plugins/dsh-quote-annotate/lib/dom-anchors.js';
const viewOf=editor=>({querySelector:()=>({querySelector:()=>({__lexicalEditor:editor})})});
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
 const start=source.indexOf('//#region ../../../node_modules/.pnpm/lexical@');
 const end=source.indexOf('//#endregion',start);
 assert(start>=0&&end>start);
 const L=vm.runInThisContext('(function(){'+source.slice(start,end)+';return {create:ys,root:nl,paragraph:es,text:Go};})()');
 for(const nested of [false,true]){
  const editor=L.create({namespace:'clear-regression',onError:e=>{throw e;}});
  editor.update(()=>L.root().append(L.paragraph().append(L.text('sent text'))),{discrete:true});
  editor.update(()=>{L.root().clear();if(nested)editorBridge(viewOf(editor),'juzi.quote-annotate').prefix([]);},{discrete:true});
  assert.equal(editor.getEditorState().read(()=>L.root().getTextContent()),'');
  editor.update(()=>L.root().append(L.paragraph().append(L.text('next draft'))),{discrete:true});
  editorBridge(viewOf(editor),'juzi.quote-annotate').prefix([]);
  assert.equal(editor.getEditorState().read(()=>L.root().getTextContent()),'next draft');
 }
});
