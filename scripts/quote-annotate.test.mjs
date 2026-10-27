import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
import {createQuote,quoteLabel,serializeMessage,plainDraft,referenceSpan,countChars,normalizeComment,commentKey,placeFloating,createHoverClock,INTRO,MAX_QUOTES,DRAFT_TTL,QUOTE_SOURCE} from '../plugins/dsh-quote-annotate/lib/quote-core.js';
import {createQuoteStore,mergeDocuments,decodeDocument} from '../plugins/dsh-quote-annotate/lib/quote-store.js';
import {extractSelection,editorBridge} from '../plugins/dsh-quote-annotate/lib/dom-anchors.js';
import {parseSentQuotes} from '../plugins/dsh-quote-annotate/lib/quote-display.js';
const q=(text,metadata={},comment='')=>createQuote(text,{id:'q1',source:'assistant',...metadata},comment,1);
test('quote format: golden single quote, empty requirements, and zero quotes',()=>{
 assert.equal(serializeMessage([],' raw\r\ntext '),' raw\ntext ');
 assert.equal(serializeMessage([q('原文',{messageId:'msg_01',turn:12},'很好')],'本轮要求'),`<juzi-quotes version="1" count="1">\n${INTRO}\n<quote index="1" source="assistant" message-id="msg_01" turn="12" chars="2" truncated="false">\n<text>\n原文\n</text>\n<comment>很好</comment>\n</quote>\n</juzi-quotes>\n\n用户本轮要求：\n本轮要求`);
 assert(serializeMessage([q('x')]).endsWith('用户本轮要求：\n（用户未填写额外要求）'));
});
test('multiple quote format and no-comment element omission',()=>{
 const s=serializeMessage([q('A'),q('B',{source:'user',id:'q2'})],' x\ny ');
 assert(s.includes('count="2"'));assert(s.includes('</quote>\n<quote index="2" source="user"'));
 assert(!s.includes('<comment>'));assert(s.endsWith(' x\ny '));
});
test('XML escapes are one-pass; source text cannot close a quote or execute markup',()=>{
 const s=serializeMessage([q('</quote></juzi-quotes>&lt;<script>',{messageId:'msg"<>&'},'< > &')]);
 assert(s.includes('&lt;/quote&gt;&lt;/juzi-quotes&gt;&amp;lt;&lt;script&gt;'));
 assert(s.includes('<comment>&lt; &gt; &amp;</comment>'));assert(s.includes('message-id="msg"'));
 assert.equal(s.split('</juzi-quotes>').length-1,2); // fixed explanatory sentence + actual closing tag
});
test('golden two-quote message includes truncation and preserves the request byte for byte',()=>{
 const items=[q('原文',{turn:12},'很好'),q('中'.repeat(4001),{id:'q2',source:'user',turn:11})];
 const expected=`<juzi-quotes version="1" count="2">\n${INTRO}\n<quote index="1" source="assistant" turn="12" chars="2" truncated="false">\n<text>\n原文\n</text>\n<comment>很好</comment>\n</quote>\n<quote index="2" source="user" turn="11" chars="4001" truncated="true" kept-chars="4000">\n<text>\n${'中'.repeat(4000)}\n[已截断：原文共 4001 字，仅保留前 4000 字]\n</text>\n</quote>\n</juzi-quotes>\n\n用户本轮要求：\n  <保留要求>\n原样结尾 `;
 assert.equal(serializeMessage(items,'  <保留要求>\n原样结尾 '),expected);
});
for(const size of [3999,4000,4001,10000])test(`Unicode truncation at ${size} characters`,()=>{
 const original='中'.repeat(size-1)+'😀',item=q(original);
 assert.equal(item.chars,size);assert.equal(item.truncated,size>4000);assert.equal(countChars(item.text),Math.min(size,4000));
 assert(!/[\uD800-\uDBFF]$/.test(item.text));
 if(size>4000){const s=serializeMessage([item]);assert(s.includes('kept-chars="4000"'));assert(s.includes(`[已截断：原文共 ${size} 字，仅保留前 4000 字]`));}
});
test('comments trim only edges, retain newlines, limit by code points',()=>{
 assert.equal(normalizeComment('  很好\r\n继续  '),'很好\n继续');assert.equal(normalizeComment(' \n '),'');
 assert.equal(countChars(normalizeComment('😀'.repeat(1000))),1000);assert.throws(()=>normalizeComment('x'.repeat(1001)),RangeError);
 assert.equal(quoteLabel(q('x',{},'好')),quoteLabel(q('x'))); // The nonshrinking comment adornment belongs to the source-scoped dock style.
});
test('code fences preserve indentation and cannot collide with quoted backticks',()=>{
 const s=serializeMessage([q('  print("```code")\n\tend',{kind:'code',lang:'python'})]);
 assert(s.includes('kind="code"'));assert(s.includes('````python\n  print("```code")\n\tend\n````'));
});
const memory=()=>{const data=new Map();return {get length(){return data.size;},key:i=>[...data.keys()][i],getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k),data};};
test('store: duplicate selections remain independent, cap, delete, edit and session isolation',()=>{
 const storage=memory(),s=createQuoteStore({storage,now:()=>10,actor:'a'});
 for(let i=0;i<MAX_QUOTES;i++)s.add('A',q('same',{id:`q${i}`}));
 assert.equal(s.items('A').length,20);assert.equal(s.items('B').length,0);assert.throws(()=>s.add('A',q('last',{id:'last'})),RangeError);
 s.remove('A',['q0']);s.edit('A','q1','  评论  ');assert.equal(s.items('A')[0].comment,'评论');
 const restored=createQuoteStore({storage,now:()=>11});assert.equal(restored.items('A').length,19);s.dispose();restored.dispose();
});
test('damaged JSON and unknown versions never escape store boundary; quota keeps memory',()=>{
 for(const raw of ['{','{"v":2,"items":[]}','{"v":1,"items":[{}]}']){
  const storage=memory();storage.setItem('juzi.quote-annotate.v1.A',raw);const warnings=[];const s=createQuoteStore({storage,warn:v=>warnings.push(v)});
  assert.deepEqual(s.items('A'),[]);assert.doesNotThrow(()=>s.items('A'));assert.equal(warnings.length,1);s.dispose();
 }
 const warnings=[],s=createQuoteStore({storage:{getItem(){throw Error('quota');}},warn:v=>warnings.push(v),now:()=>2});s.add('A',q('x'));assert.equal(s.items('A').length,1);s.dispose();
});
test('multi-writer merge retains concurrent adds and deletion dominates an older item',()=>{
 const a={v:1,items:[{...q('a',{id:'a'}),_stamp:[2,'A']}],tombstones:{}},b={v:1,items:[{...q('b',{id:'b'}),_stamp:[2,'B']}],tombstones:{}};
 assert.deepEqual(mergeDocuments(a,b,3),mergeDocuments(b,a,3));assert.equal(mergeDocuments(a,b,3).items.length,2);
 const del={v:1,items:[],tombstones:{a:{createdAt:3,_stamp:[3,'B']}}};assert.deepEqual(mergeDocuments(a,del,4).items,[]);
});
test('storage event merges rather than replacing another tab, sends synchronize clear',()=>{
 const storage=memory(),events=new EventTarget(),a=createQuoteStore({storage,events,actor:'a',now:()=>10}),b=createQuoteStore({storage,actor:'b',now:()=>11});
 a.add('A',q('a',{id:'a'}));b.add('A',q('b',{id:'b'}));const e=new Event('storage');Object.assign(e,{key:'juzi.quote-annotate.v1.A',newValue:storage.getItem('juzi.quote-annotate.v1.A')});events.dispatchEvent(e);
 assert.equal(a.items('A').length,2);a.clear('A');const fresh=createQuoteStore({storage,now:()=>12});assert.equal(fresh.items('A').length,0);a.dispose();b.dispose();fresh.dispose();
});
test('only a deletion tombstone permits automatic chip removal, missing/corrupt data does not',()=>{
 const storage=memory(),s=createQuoteStore({storage,now:()=>10});s.add('A',q('x'));
 assert.equal(s.isRemoved('A','q1'),false);assert.equal(s.isRemoved('A','missing'),false);
 s.remove('A',['q1']);assert.equal(s.isRemoved('A','q1'),true);s.dispose();
 const other=createQuoteStore({storage,now:()=>11});assert.equal(other.isRemoved('A','q1'),true);other.dispose();
});
test('30 day expiration and deleted-session cleanup',()=>{
 const storage=memory(),s=createQuoteStore({storage,now:()=>DRAFT_TTL+2});s.add('A',q('expired'));assert.equal(s.items('A').length,0);
 s.add('B',createQuote('alive',{id:'live'},'',DRAFT_TTL+1));s.cleanup(new Set(['A']));assert.equal(storage.getItem('juzi.quote-annotate.v1.B'),null);s.dispose();
 assert.throws(()=>decodeDocument('{"v":8}'));
});
test('editing a draft performs no automatic send',()=>{
 const calls={conversation:0,inputActions:0,sessionInput:0};const forbidden={conversation:{send(){calls.conversation++;}},inputActions:{submit(){calls.inputActions++;}},SessionInput:{submit(){calls.sessionInput++;}}};
 const s=createQuoteStore({storage:memory(),now:()=>2});s.add('A',q('x'));s.edit('A','q1','很好');s.remove('A',['q1']);s.add('A',q('y'));s.clear('A');
 assert.deepEqual(calls,{conversation:0,inputActions:0,sessionInput:0});assert(forbidden);s.dispose();
 const client=readFileSync(new URL('../plugins/dsh-quote-annotate/src/client.mjs',import.meta.url),'utf8');assert(!/\.submit\(|sendSession\(|\.prompt\(|conversation\.send\(/.test(client));
});
test('comment keyboard: IME, Shift+Enter, ordinary Enter and Escape',()=>{
 assert.equal(commentKey({key:'Enter',isComposing:true}),'compose');assert.equal(commentKey({key:'Enter',keyCode:229}),'compose');
 assert.equal(commentKey({key:'Enter',shiftKey:true}),'text');assert.equal(commentKey({key:'Enter'}),'confirm');assert.equal(commentKey({key:'Escape'}),'cancel');
});
test('positioning: multiline avoidance, top flip, right clamp, offscreen',()=>{
 const bounds={left:0,top:0,right:400,bottom:400},r={left:20,right:120,top:100,bottom:120};
 const top=placeFloating([r],{width:28,height:28},bounds);assert.equal(top.side,'top');assert.equal(top.y,64);
 const flip=placeFloating([{...r,top:10,bottom:30}],{width:28,height:28},bounds);assert.equal(flip.side,'right');
 const clamp=placeFloating([{...r,left:370,right:395}],{width:28,height:28},bounds);assert.equal(clamp.x,364);assert(clamp.arrow<=20);
 const multi=[{left:0,right:400,top:60,bottom:90},r];const pos=placeFloating(multi,{width:28,height:28},bounds);assert.equal(pos.side,'right');
 assert.equal(placeFloating([{...r,top:500,bottom:520}],{width:28,height:28},bounds),null);
});
test('floating bubble avoids unselected continuation/next lines, including a shifted lower gap',()=>{
 const selected={left:20,right:395,top:10,bottom:30},next={left:20,right:395,top:35,bottom:55};
 const p=placeFloating([selected],{width:28,height:28},{left:0,top:0,right:400,bottom:400},8,{obstacles:[next]});assert.equal(p.side,'bottom');assert(p.y>=next.bottom+8);
 const wide=placeFloating([selected],{width:28,height:28},{left:0,top:0,right:600,bottom:400},8,{obstacles:[next]});assert.equal(wide.side,'right');assert(wide.x>=next.right+8);
 const card=placeFloating([{left:100,right:200,top:100,bottom:120}],{width:300,height:100},{left:0,top:0,right:600,bottom:500},6,{prefer:['bottom'],align:'start'});assert.equal(card.x,100);assert.equal(card.y,126);assert.equal(card.arrow,50);
});
test('sent quote display parses the canonical prefix without confusing the INTRO closing tag',()=>{
 const items=[q('<script>&lt;😀',{},'很好\n</quote>&'),q('  x = 1\n\tprint(x)',{id:'q2',kind:'code',lang:'python'})],wire=serializeMessage(items,'本轮要求原样\n 保留 '),parsed=parseSentQuotes(wire);
 assert.equal(parsed.quotes.length,2);assert.equal(parsed.quotes[0].text,items[0].text);assert.equal(parsed.quotes[0].comment,items[0].comment);assert.equal(parsed.quotes[1].kind,'code');assert(parsed.quotes[1].text.includes('```python\n  x = 1\n\tprint(x)\n```'));assert.equal(wire.slice(parsed.end),'本轮要求原样\n 保留 ');
 const long=parseSentQuotes(serializeMessage([q('中'.repeat(4501))]));assert.equal(long.quotes[0].truncated,true);assert(long.quotes[0].text.endsWith('[已截断：原文共 4501 字，仅保留前 4000 字]'));
});
test('malformed or foreign quote messages remain raw instead of being partially hidden',()=>{
 const raw=serializeMessage([q('safe')],'request');for(const invalid of [raw.replace('version="1"','version="2"'),raw.replace('count="1"','count="2"'),raw.replace('source="assistant"','source="other"'),raw.replace('index="1"','index="1" index="1"'),raw.replace('safe','<script>'),raw.replace('</quote>',''),raw.replace('用户本轮要求：','other'),raw.slice(0,-30),'prefix '+raw])assert.equal(parseSentQuotes(invalid),null);
});
test('hover delays and card bridge cancel hiding',t=>{
 t.mock.timers.enable({apis:['setTimeout','Date'],now:1000});let visible=null;
 const clock=createHoverClock(v=>{visible=v;},()=>{visible=null;});clock.enter('A');t.mock.timers.tick(299);assert.equal(visible,null);t.mock.timers.tick(1);assert.equal(visible,'A');
 clock.leave();t.mock.timers.tick(149);clock.bridge();t.mock.timers.tick(100);assert.equal(visible,'A');clock.enter('B');t.mock.timers.tick(0);assert.equal(visible,'B');clock.leave();t.mock.timers.tick(150);assert.equal(visible,null);clock.dispose();
});
test('plain draft retains text and other official references',()=>{
 const state={draft:'⟦a⟧Hello @file',occurrences:[{source:QUOTE_SOURCE,offset:0,length:3}]};assert.equal(plainDraft(state),'Hello @file');
});
test('reference removal uses official detect coordinates and includes other chip widths',()=>{
 const state={occurrences:[{source:'reference',ref:'file',offset:2,length:12},{source:QUOTE_SOURCE,ref:'jq:a',offset:16,length:38},{source:QUOTE_SOURCE,ref:'jq:b',offset:54,length:38}]};
 assert.deepEqual(referenceSpan(state,QUOTE_SOURCE,'jq:a'),{start:5,end:6});assert.deepEqual(referenceSpan(state,QUOTE_SOURCE,'jq:b'),{start:6,end:7});assert.equal(referenceSpan(state,QUOTE_SOURCE,'missing'),null);
});
const anchor=process.env.DSH_ULTRA_UI_RUNTIME_ANCHOR;
test('actual DOM selection extraction excludes controls, preserves code, and isolates session', {skip:!anchor},()=>{
 const req=createRequire(pathToFileURL(resolve(anchor))),{JSDOM}=req('jsdom');
 const dom=new JSDOM('<main data-conversation-content data-conversation-session="A"><div data-chat-flow><div data-chat-node-key="assistant-a"><pre><code class="language-python">  x = 1\n\tprint(x)</code></pre><button>复制</button><span role="status" aria-live="polite">已完成</span><span hidden>不可见</span><span data-jq-message="msgA" data-jq hidden></span></div><div data-chat-node-key="user-b"><p>下一条</p></div></div></main>');
 const d=dom.window.document,code=d.querySelector('code'),range=d.createRange();range.selectNodeContents(code);range.getClientRects=()=>[{left:10,top:100,right:100,bottom:140,width:90,height:40}];d.querySelector('[data-chat-flow]').getBoundingClientRect=()=>({left:0,top:0,right:400,bottom:400});
 const selection={rangeCount:1,isCollapsed:false,getRangeAt:()=>range};const result=extractSelection(selection,'A');assert.equal(result.text,'  x = 1\n\tprint(x)');assert.equal(result.metadata.kind,'code');assert.equal(result.metadata.lang,'python');assert.equal(extractSelection(selection,'B'),null);
 range.selectNodeContents(d.querySelector('[data-chat-flow]'));const mixed=extractSelection(selection,'A');assert.equal(mixed.metadata.source,'mixed');assert(!mixed.text.includes('复制'));assert(!mixed.text.includes('已完成'));assert(!mixed.text.includes('不可见'));assert(mixed.text.includes('下一条'));dom.window.close();
});
test('missing editor anchor fails closed before any mutation',()=>assert.throws(()=>editorBridge({querySelector:()=>null},QUOTE_SOURCE),/unavailable/));
