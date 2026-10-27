import { createQuote, quoteLabel, quoteBlock, serializeMessage, serializePrefix, plainDraft, referenceSpan, commentKey, placeFloating, createHoverClock, normalizeComment, normalizeLines, countChars, safeId, QUOTE_SOURCE, STORAGE_PREFIX, MAX_QUOTES } from '../lib/quote-core.js';
import { createQuoteStore } from '../lib/quote-store.js';
import { parseSentQuotes } from '../lib/quote-display.js';
import { DOM_ANCHORS, extractSelection, visibleTextRects, editorBridge } from '../lib/dom-anchors.js';
import { QUOTE_CSS } from './styles.mjs';
export const inject = ['slots','locale','conversation','inputTriggers','sessions'];
export function apply(ctx) {
  const R=require('react'),h=R.createElement;
  const NS='juzi.quote-annotate';
  const zh={add:'添加到对话',comment:'添加评论',optional:'评论（可选）',placeholder:'添加评论（可选），Enter 添加，Shift+Enter 换行',hint:'Enter 添加 · Esc 取消',confirm:'添加',cancel:'取消',preview:'引用预览',edit:'编辑评论',remove:'删除',clear:'全部清除',confirmClear:'确认清除',expand:'展开',collapse:'折叠',quotes:'条引用',total:'合计',chars:'字',truncated:'已截断',original:'原文',save:'保存',added:'已添加引用',deleted:'已删除引用',unavailable:'当前会话暂不能编辑草稿',limit:'最多 20 条引用',quota:'引用草稿未能保存，刷新后会丢失',corrupt:'引用草稿损坏，已安全忽略',locate:'无法定位该引用',invalid:'引用数据已失效，请删除这条引用',prefix:'引用需位于草稿开头，请在引用后填写要求',user:'我',assistant:'助手',reasoning:'推理',tool:'工具',mixed:'多条消息',unknown:'引用'};
  const en={add:'Add to conversation',comment:'Add a comment',optional:'Comment (optional)',placeholder:'Comment (optional), Enter to add, Shift+Enter for a new line',hint:'Enter to add · Esc to cancel',confirm:'Add',cancel:'Cancel',preview:'Quote preview',edit:'Edit comment',remove:'Delete',clear:'Clear all',confirmClear:'Confirm clear',expand:'Expand',collapse:'Collapse',quotes:'quotes',total:'Total',chars:'characters',truncated:'Truncated',original:'Original',save:'Save',added:'Quote added',deleted:'Quote removed',unavailable:'This conversation cannot edit a draft right now',limit:'Up to 20 quotes',quota:'Quote draft could not be saved; a reload will lose it',corrupt:'Invalid quote draft safely ignored',locate:'Unable to locate this quote',invalid:'Quote data is missing; delete this invalid quote',prefix:'Keep quotes at the start and enter your request after them',user:'Me',assistant:'Assistant',reasoning:'Reasoning',tool:'Tool',mixed:'Multiple messages',unknown:'Quote'};
  zh.removeNumber='删除引用 {n}';zh.editNumber='编辑引用 {n} 的评论';en.removeNumber='Delete quote {n}';en.editNumber='Edit comment for quote {n}';
  Object.assign(zh,{sent:'引用已随消息发送',commentLimit:'评论最多 1000 字',placeholder:'添加评论（可选）',sentQuotes:'引用 {n} 条',expandSent:'展开引用 {n} 条',collapseSent:'折叠引用 {n} 条'});Object.assign(en,{sent:'Quotes sent with the message',commentLimit:'Comments are limited to 1000 characters',placeholder:'Add a comment (optional)',sentQuotes:'{n} quotes',expandSent:'Expand {n} quotes',collapseSent:'Collapse {n} quotes'});
  const t=ctx.locale.bind(NS);
  ctx.effect(()=>ctx.locale.register(NS,{zh,en}));
  const warned=new Set();const warn=code=>{if(!warned.has(code)){warned.add(code);ctx.logger.warn(`quote-annotate: ${code}`);}};
  const listeners=new Set(),controls=new Map(),batches=new WeakMap();let active,disposed=false,selectionTimer,dismissedRange;
  let ui={bubble:null,comment:null,preview:null,live:'',notice:'',highlight:null};
  const emit=patch=>{if(disposed)return;ui={...ui,...patch};for(const f of listeners)f();};
  const subscribe=f=>{listeners.add(f);return()=>listeners.delete(f);};
  const storage=(()=>{try{return window.localStorage;}catch{return undefined;}})();
  const store=createQuoteStore({storage,events:window,warn:code=>{warn(code);emit({notice:t(code==='quota'||code==='storage'?'quota':'corrupt')});}});
  const refOf=q=>`jq:${q.id}`;
  const itemFor=(c,ref)=>store.items(c.id).find(q=>refOf(q)===ref);
  const sourceRefs=state=>state.occurrences.filter(o=>o.source===QUOTE_SOURCE);
  const currentView=c=>c?.view?.isConnected&&c.view.dataset.conversationSession===c.id;
  const bridge=c=>{if(!currentView(c))throw new Error('Conversation generation changed');return editorBridge(c.view,QUOTE_SOURCE);};
  const canEdit=c=>{if(!currentView(c)||c.input.state.getSnapshot().phase!=='plain')return false;try{bridge(c);return true;}catch{warn('composer anchors unavailable');return false;}};
  const stopLayers=()=>emit({bubble:null,preview:null,...(!ui.comment?.value?{comment:null}:{})});
  const menusOpen=()=>[...document.querySelectorAll(DOM_ANCHORS.menu)].some(el=>!el.closest('.jq-root')&&el.getClientRects().length>0);
  const removeChip=(c,ref)=>{try{const span=referenceSpan(c.input.state.getSnapshot(),QUOTE_SOURCE,ref);if(!span)return true;if(c.actions.insertText('',{...c.actions.captureInsertion(),...span})!==true)throw new Error('Reference removal refused');return true;}catch{warn('reference edit unavailable');emit({notice:t('locate')});return false;}};
  const insert=(c,q,index)=>{
    const state=c.input.state.getSnapshot(),tail=state.draft.startsWith(sourceRefs(state).map(o=>o.clipboardText).join(''))?plainDraft(state):state.draft;
    const span={...c.actions.captureInsertion(),start:index,end:index};
    const applied=c.binding.ctx.bail(c.binding.ctx,'slash/input-insert-reference',{reference:{source:QUOTE_SOURCE,ref:refOf(q),label:quoteLabel(q),clipboardText:`⟦${q.id}⟧`},span});
    if(applied!==true)throw new Error('Draft insertion refused');
    // Remove only the separator this official insertion just generated, never user whitespace.
    if(!tail.startsWith(' '))c.actions.insertText('',{...c.actions.captureInsertion(),start:index+1,end:index+2});
  };
  const reconcile=c=>{
    if(c.editing||disposed||!currentView(c))return;
    const state=c.input.state.getSnapshot();if(state.phase==='adjudicating'||state.phase==='submitting')return;
    c.editing=true;
    try{
      const refs=sourceRefs(state),items=store.items(c.id),plain=plainDraft(state);
      const names=ctx.inputTriggers.sessionOf(c.binding.ctx).lexicon.getSnapshot().get('/')??[];
      const token=plain.trimStart().match(/^\/(\S+)/)?.[1];
      const command=state.phase==='claimed'||token&&names.some(n=>n.replace(/^\//,'')===token);
      if(command){c.command=true;for(const o of refs)removeChip(c,o.ref);return;}
      c.pending=c.pending.filter(batch=>{const present=batch.refs.every(ref=>refs.some(o=>o.ref===ref));if(!present)batch.detached=true;return !(batch.detached&&present);});
      if(c.pending.length)return;
      if(c.command){c.command=false;c.repair=true;}
      const current=new Set(refs.map(o=>o.ref));
      if(!c.repair){const missing=[...c.known].filter(ref=>!current.has(ref)).map(ref=>ref.slice(3));if(missing.length)store.remove(c.id,missing);}
      const live=store.items(c.id);
      for(const o of refs)if(store.isRemoved(c.id,o.ref.slice(3)))removeChip(c,o.ref);
      for(const [i,q] of live.entries())if(!current.has(refOf(q)))insert(c,q,i);
      bridge(c).prefix(live.map(refOf));
      c.known=new Set(sourceRefs(c.input.state.getSnapshot()).map(o=>o.ref));c.repair=false;
    }catch{warn('composer anchors unavailable');}finally{c.editing=false;}
  };
  const eventText=value=>{if(!value||typeof value!=='object')return[];if(value.type==='text'&&typeof value.text==='string')return[value.text];return Object.values(value).flatMap(v=>Array.isArray(v)?v.flatMap(eventText):eventText(v));};
  const observe=c=>{
    const entries=c.binding.eventSource.getSnapshot().entries;
    const echoes=c.binding.session.getSnapshot().pendingSubmissions??[];
    for(const batch of c.pending)if(!batch.requestId){const echo=echoes.find(e=>!c.pending.some(b=>b.requestId===e.requestId)&&(batch.hasOtherRefs?e.text.startsWith(batch.prefix):e.text===batch.expected));if(echo)batch.requestId=echo.requestId;}
    for(const batch of [...c.pending]){
      const matches=row=>batch.requestId?row?.source?.rpcId===batch.requestId:!batch.hasOtherRefs&&eventText(row).some(text=>text===batch.expected);
      const durable=entries.some(entry=>{const e=entry.event??entry;return e.seq>batch.afterSeq&&e.type==='user/message'&&matches(e.data);});
      const inbox=c.binding.session.projections.faceOf('inbox').getSnapshot();
      const queued=(inbox?.['next-turn']??[]).some(matches);
      if(durable||queued){c.pending=c.pending.filter(b=>b!==batch);store.remove(c.id,batch.ids);c.known=new Set();c.repair=true;emit({live:t('sent')});}
    }
    const error=c.binding.session.getSnapshot().promptError;
    if(error&&error!==c.lastError&&c.pending.length){c.pending=[];c.repair=true;setTimeout(()=>reconcile(c),0);}c.lastError=error;
  };
  const attach=(id,view,props)=>{
    let c=controls.get(id);const binding=ctx.sessions.binding(id);if(!binding)return;
    if(!c||c.binding!==binding){
      const pending=c?.pending??[];if(c)for(const off of c.off)off();
      c={id,binding,input:ctx.conversation.input.for(binding.ctx),view,actions:props.inputActions,known:new Set(),pending,repair:true};controls.set(id,c);
      c.off=[c.input.state.subscribe(()=>reconcile(c)),binding.eventSource.subscribe(()=>observe(c)),binding.session.subscribe(()=>observe(c))];
    }
    c.view=view;c.actions=props.inputActions;active=c;observe(c);reconcile(c);return c;
  };
  const serialize=(ref,signal)=>{
    let batch=batches.get(signal);
    if(!batch){
      const c=[...controls.values()].find(c=>sourceRefs(c.input.state.getSnapshot()).some(o=>o.ref===ref));
      if(!c)throw new Error(t('invalid'));
      const state=c.input.state.getSnapshot(),refs=sourceRefs(state),items=refs.map(o=>itemFor(c,o.ref));
      if(items.some(q=>!q)||items.length!==store.items(c.id).length)throw new Error(t('invalid'));
      const prefix=refs.map(o=>o.clipboardText).join('');
      if(!state.draft.startsWith(prefix))throw new Error(t('prefix'));
      const request=plainDraft(state),entries=c.binding.eventSource.getSnapshot().entries;
      batch={refs:refs.map(o=>o.ref),ids:items.map(q=>q.id),items,request,prefix:serializePrefix(items),hasOtherRefs:state.occurrences.length!==refs.length,expected:serializeMessage(items,request).trim(),afterSeq:Math.max(0,...entries.map(row=>(row.event??row).seq??0))};
      c.pending.push(batch);batches.set(signal,batch);
    }
    if(!batch.refs.includes(ref))throw new Error(t('invalid'));
    return Promise.resolve(ref===batch.refs[0]?serializePrefix(batch.items)+(batch.request===''?'（用户未填写额外要求）':''):'');
  };
  const findChip=(c,ref)=>{if(!currentView(c))return;const nodes=[...c.view.querySelectorAll(DOM_ANCHORS.chip)],refs=sourceRefs(c.input.state.getSnapshot());return nodes.length===refs.length?nodes[refs.findIndex(o=>o.ref===ref)]:undefined;};
  const openPreview=(c,ref,element,focus=false)=>{if(!itemFor(c,ref)){emit({notice:t('locate')});return;}const anchor=element??findChip(c,ref);if(!anchor)return;emit({bubble:null,preview:{id:c.id,ref,rect:anchor.getBoundingClientRect(),focus},highlight:ref});};
  const hover=createHoverClock(v=>openPreview(v.c,v.ref,v.el),()=>emit({preview:null,highlight:null}));
  const locateChip=target=>{const el=target?.closest?.(DOM_ANCHORS.chip),view=el?.closest(DOM_ANCHORS.conversation),c=controls.get(view?.dataset.conversationSession);if(!c)return;const nodes=[...view.querySelectorAll(DOM_ANCHORS.chip)],refs=sourceRefs(c.input.state.getSnapshot());if(nodes.length!==refs.length){warn('chip mapping mismatch');return;}return {c,el,ref:refs[nodes.indexOf(el)]?.ref};};
  const selection=()=>{
    if(disposed)return;
    if(menusOpen()){emit({hidden:true,bubble:null,preview:null});return;}
    if(ui.hidden)emit({hidden:false});
    if(ui.comment||ui.preview||!active)return;
    if(document.getSelection()?.toString().trim()&&!active.view.querySelector(DOM_ANCHORS.chat)){warn('selection anchors unavailable');emit({bubble:null});return;}
    try{const hit=extractSelection(document.getSelection(),active.id);if(!hit){dismissedRange=null;emit({bubble:null});return;}if(dismissedRange&&hit.range.compareBoundaryPoints(0,dismissedRange)===0&&hit.range.compareBoundaryPoints(2,dismissedRange)===0){emit({bubble:null});return;}dismissedRange=null;if(!canEdit(active)){emit({bubble:null});return;}
      const obstacles=visibleTextRects(hit.view,hit.bounds),pos=placeFloating(hit.rects,{width:28,height:28},hit.bounds,8,{obstacles,sideBounds:hit.sideBounds});emit({bubble:pos?{...hit,pos}:null,preview:null});
    }catch{warn('selection anchors unavailable');emit({bubble:null});}
  };
  const schedule=delay=>{clearTimeout(selectionTimer);selectionTimer=setTimeout(selection,delay);};
  const onSelection=()=>schedule(150),onPointerUp=()=>schedule(80),onKeyUp=()=>schedule(150);
  const onScroll=()=>{if(ui.comment)return;if(ui.preview)emit({preview:null});schedule(50);};
  const onDown=e=>{if(e.target.closest?.('.jq-root,[data-jq]'))return;dismissedRange=null;if(ui.comment?.value)return;emit({bubble:null,comment:null,preview:null});};
  const onKey=e=>{if(e.key==='Escape'&&(!e.target.closest?.('.jq-root')||e.target.closest?.('.jq-bubble'))){dismissedRange=ui.bubble?.range;stopLayers();}if(e.key==='Q'&&e.ctrlKey&&e.shiftKey&&ui.bubble)emit({comment:{...ui.bubble,value:'',edit:false},bubble:null});};
  const onOver=e=>{const hit=locateChip(e.target);if(hit&&hit.ref)hover.enter(hit);else if(menusOpen())stopLayers();};
  const onOut=e=>{if(locateChip(e.target)&&!e.relatedTarget?.closest?.('.jq-card'))hover.leave();};
  const onFocus=e=>{const hit=locateChip(e.target);if(hit?.ref)openPreview(hit.c,hit.ref,hit.el);};
  const eventBindings=[['selectionchange',onSelection],['pointerup',onPointerUp],['keyup',onKeyUp],['pointerdown',onDown],['keydown',onKey],['pointerover',onOver],['pointerout',onOut],['focusin',onFocus],['scroll',onScroll]];
  const removeItem=(c,q)=>{c.editing=true;const ok=removeChip(c,refOf(q));if(ok)store.remove(c.id,[q.id]);c.editing=false;if(ok){emit({preview:null,live:`${t('deleted')} ${store.items(c.id).length+1}`});reconcile(c);c.input.focus();}};
  const addQuote=()=>{
    const form=ui.comment,c=controls.get(form?.sessionId??form?.id);if(!canEdit(c)||c!==active){emit({notice:t('unavailable'),comment:null});return;}
    try{
      if(form.edit){store.edit(c.id,form.quoteId,form.value);reconcile(c);}
      else{const q=createQuote(form.text,form.metadata,form.value);c.repair=true;store.add(c.id,q);reconcile(c);emit({live:`${t('added')} ${store.items(c.id).length}`});}
      emit({comment:null,bubble:null});c.input.focus();
    }catch(e){emit({notice:e instanceof RangeError?t('limit'):t('unavailable')});}
  };
  const editItem=(c,q,rect)=>emit({preview:null,comment:{sessionId:c.id,id:c.id,quoteId:q.id,text:q.text,metadata:q,rects:[rect],bounds:{left:0,top:0,right:innerWidth,bottom:innerHeight},value:q.comment,edit:true}});
  function Icon({kind='quote'}) {const d={quote:'M4 4h8a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H7l-4 2v-3a2 2 0 0 1-1-2V6a2 2 0 0 1 2-2m2 3v2m4-2v2',edit:'m3 11 8-8 2 2-8 8-3 1z',delete:'M3 5h10M6 5V3h4v2M5 7v6h6V7'}[kind];return h('svg',{className:'jq-icon',viewBox:'0 0 16 16','aria-hidden':true},h('path',{d}));}
  function Arrow(){return h('svg',{className:'jq-arrow',viewBox:'0 0 8 6','aria-hidden':true},h('path',{d:'M0 0 4 5 8 0'}));}
  const button=(label,fn,kind,extra={})=>h('button',{type:'button',className:`jq-button ${kind==='delete'?'jq-danger':''}`,'aria-label':label,onClick:fn,...extra},h(Icon,{kind}));
  function CommentForm(){const value=ui.comment;const node=R.useRef(null),panel=R.useRef(null);const [layout,setLayout]=R.useState(null);
    R.useLayoutEffect(()=>{
      const el=node.current,line=parseFloat(window.getComputedStyle(el).lineHeight)||20;
      const scrollTop=el.scrollTop;el.style.height=`${line}px`;el.style.height=`${Math.min(6,Math.max(1,Math.ceil(el.scrollHeight/line)))*line}px`;el.scrollTop=scrollTop;
      const position=()=>{
        const c=controls.get(value.sessionId??value.id),chat=c?.view.querySelector(DOM_ANCHORS.chat),viewport=c?.view.getBoundingClientRect(),scroll=chat?.closest(DOM_ANCHORS.scroll)?.getBoundingClientRect(),composer=c?.view.querySelector(DOM_ANCHORS.composer)?.getBoundingClientRect();
        const bounds={left:Math.max(0,viewport?.width?viewport.left:0),right:Math.min(window.innerWidth,viewport?.width?viewport.right:window.innerWidth),top:Math.max(0,scroll?.top??value.bounds.top),bottom:Math.min(window.innerHeight,composer?.top??window.innerHeight)};
        const rects=value.range?(value.range.commonAncestorContainer.isConnected?[...value.range.getClientRects()].filter(r=>r.width>0&&r.height>0):[]):value.rects;
        if(!rects.length){setLayout({position:null,rects:[]});return;}
        const anchor={left:Math.min(...rects.map(r=>r.left)),right:Math.max(...rects.map(r=>r.right)),top:Math.min(...rects.map(r=>r.top)),bottom:Math.max(...rects.map(r=>r.bottom))};
        const marks=value.range?rects.map(r=>({left:Math.max(r.left,bounds.left),top:Math.max(r.top,bounds.top),right:Math.min(r.right,bounds.right),bottom:Math.min(r.bottom,bounds.bottom)})).filter(r=>r.right>r.left&&r.bottom>r.top):[];
        const badgePosition=marks.length?placeFloating([anchor],{width:24,height:24},bounds,4,{align:'end'}):null,badge=badgePosition?{left:badgePosition.x,top:badgePosition.y}:null;
        const obstacles=value.range?[...c.view.querySelectorAll(DOM_ANCHORS.row)].filter(row=>['user','assistant-step'].includes(row.dataset.chatFlowKind)&&!value.range.intersectsNode(row)).map(row=>row.getBoundingClientRect()).filter(r=>r.width>0&&r.height>0&&r.bottom>bounds.top&&r.top<bounds.bottom):[];
        if(badge)obstacles.push({left:badge.left,right:badge.left+24,top:badge.top,bottom:badge.top+24});
        setLayout({position:placeFloating([anchor],{width:panel.current.offsetWidth||320,height:panel.current.offsetHeight||48},bounds,8,{align:'center',prefer:['top','bottom','right','left'],obstacles}),rects:marks,badge});
      };
      let frame;const schedulePosition=()=>{window.cancelAnimationFrame(frame);frame=window.requestAnimationFrame(position);};
      const c=controls.get(value.sessionId??value.id),observer=window.ResizeObserver?new window.ResizeObserver(schedulePosition):null;
      if(observer){observer.observe(c.view);const chat=c.view.querySelector(DOM_ANCHORS.chat);if(chat)observer.observe(chat);observer.observe(panel.current);}
      position();document.addEventListener('scroll',schedulePosition,{passive:true,capture:true});window.addEventListener('resize',schedulePosition,{passive:true});
      return()=>{window.cancelAnimationFrame(frame);observer?.disconnect();document.removeEventListener('scroll',schedulePosition,true);window.removeEventListener('resize',schedulePosition);};
    },[value]);
    R.useEffect(()=>{node.current?.focus();},[]);
    const key=e=>{e.stopPropagation();const action=commentKey(e);if(action==='confirm'){e.preventDefault();addQuote();}else if(action==='cancel'){e.preventDefault();emit({comment:null});active?.input.focus();}else if(e.key==='Tab'){const list=[...e.currentTarget.querySelectorAll('textarea,button')];const at=list.indexOf(document.activeElement),next=(at+(e.shiftKey?-1:1)+list.length)%list.length;e.preventDefault();list[next].focus();}};
    const pos=layout?.position??value.pos??{x:8,y:8,side:'bottom',arrow:16},items=store.items(value.sessionId??value.id),index=value.edit?items.findIndex(q=>q.id===value.quoteId)+1:items.length+1;
    return h(R.Fragment,null,layout?.position&&h('div',{className:'jq-selection','aria-hidden':true},layout.rects.map((r,i)=>h('span',{key:i,className:'jq-selection-mark',style:{left:r.left,top:r.top,width:r.right-r.left,height:r.bottom-r.top}})),layout.badge&&h('span',{className:'jq-selection-number',style:layout.badge},index)),
      h('div',{ref:panel,className:'jq-surface jq-compose',role:'dialog','aria-label':t('comment'),'aria-describedby':'jq-compose-help','data-jq-side':pos.side,style:{left:pos.x,top:pos.y,visibility:layout&&!layout.position?'hidden':undefined},onKeyDown:key},
      h('span',{className:'jq-sr',id:'jq-compose-help'},`${value.text} · ${t('hint')}`),
      h('div',{className:'jq-comment-field'},h('textarea',{ref:node,className:'jq-comment','aria-label':t('optional'),placeholder:t('placeholder'),value:value.value,onChange:e=>{const chars=Array.from(e.target.value);emit({comment:{...value,value:chars.slice(0,1000).join('')},...(chars.length>1000?{notice:t('commentLimit')}:{})});}})),
      countChars(value.value)>800&&h('span',{className:'jq-count','data-jq-limit':countChars(value.value)===1000||undefined,role:'status'},`${countChars(value.value)}/1000`),
      h('button',{type:'button',className:'jq-button jq-confirm','aria-label':value.edit?t('save'):t('confirm'),onClick:addQuote},h('svg',{className:'jq-icon',viewBox:'0 0 24 24','aria-hidden':true},h('path',{d:'M20 6 9 17l-5-5'})))));
  }
  function Preview(){const p=ui.preview,c=controls.get(p.id),q=itemFor(c,p.ref),node=R.useRef(null),[position,setPosition]=R.useState(null);
    R.useEffect(()=>{if(p.focus)node.current?.querySelector('button')?.focus();},[p.ref,p.focus]);
    R.useLayoutEffect(()=>{if(!node.current)return;const size={width:node.current.offsetWidth,height:node.current.offsetHeight};const anchor={left:p.rect.left,right:p.rect.right,top:p.rect.top,bottom:p.rect.bottom};setPosition(placeFloating([anchor],size,{left:0,top:0,right:innerWidth,bottom:innerHeight},6,{align:'start',prefer:['top','bottom']}));},[p.ref,q?.comment]);
    if(!q)return null;const pos=position??{x:Math.max(8,p.rect.left),y:Math.max(8,p.rect.top-160),side:'top'};
    return h('div',{ref:node,id:`jq-preview-${safeId(p.ref)}`,className:'jq-surface jq-card',role:'dialog','aria-label':t('preview'),'data-jq-side':pos.side,style:{left:pos.x,top:pos.y,'--jq-arrow':`${pos.arrow??16}px`},onPointerEnter:()=>hover.bridge(),onPointerLeave:()=>hover.leave(),onKeyDown:e=>{if(e.key==='Escape'){e.stopPropagation();emit({preview:null});c.input.focus();}}},
      h('div',{className:'jq-card-head'},h('span',null,t(q.source),q.turn?` · ${q.turn}`:''),h('div',{className:'jq-actions'},button(t('edit'),e=>editItem(c,q,e.currentTarget.getBoundingClientRect()),'edit'),button(t('remove'),()=>removeItem(c,q),'delete'))),
      h('blockquote',{className:`jq-text ${q.kind==='code'?'jq-code':''}`},q.text),q.truncated&&h('div',{className:'jq-meta'},`${t('truncated')} · ${t('original')} ${q.chars} ${t('chars')}`),q.comment&&h('div',{className:'jq-note'},q.comment),h(Arrow));
  }
  function Overlay(){R.useSyncExternalStore(subscribe,()=>ui);return h('div',{className:'jq-root','data-jq':'overlay'},
    !ui.hidden&&ui.bubble&&h('button',{type:'button',className:'jq-surface jq-button jq-bubble','aria-label':t('add'),'data-jq-side':ui.bubble.pos.side,style:{left:ui.bubble.pos.x,top:ui.bubble.pos.y,'--jq-arrow':`${ui.bubble.pos.arrow}px`},onClick:()=>emit({comment:{...ui.bubble,value:'',edit:false},bubble:null})},h(Icon),h(Arrow)),
    !ui.hidden&&ui.comment&&h(CommentForm),!ui.hidden&&ui.preview&&h(Preview),h('div',{className:'jq-sr','aria-live':'polite'},ui.live));}
  function Dock(props){const marker=R.useRef(null),[rev,rerender]=R.useReducer(x=>x+1,0),[expanded,setExpanded]=R.useState(false),[confirm,setConfirm]=R.useState(false);const state=props.useInput(s=>s);R.useSyncExternalStore(subscribe,()=>ui);
    R.useLayoutEffect(()=>{const view=marker.current?.closest(DOM_ANCHORS.conversation);if(!view||view.parentElement?.closest(DOM_ANCHORS.conversation))return;attach(props.sessionId,view,props);},[props.sessionId,state,rev]);
    R.useEffect(()=>store.subscribe(id=>{if(id===props.sessionId)rerender();}),[props.sessionId]);
    const items=store.items(props.sessionId),c=controls.get(props.sessionId);
    const highlightIndex=state.occurrences.filter(o=>o.source===QUOTE_SOURCE).findIndex(o=>o.ref===ui.highlight);
    const ownRefs=state.occurrences.filter(o=>o.source===QUOTE_SOURCE),chipRules=ownRefs.map((o,i)=>{const q=items.find(q=>refOf(q)===o.ref);return q?.comment?`[data-conversation-session="${safeId(props.sessionId)}"] [data-composer-chip="${QUOTE_SOURCE}"]:nth-of-type(${i+1})>span::after{content:"✎";flex:none;margin-left:4px}`:'';}).join('');
    return h(R.Fragment,null,h('span',{ref:marker,hidden:true,'data-jq':'controller'}),items.length>0&&h('section',{className:'jq-dock','data-jq':'dock','aria-label':t('preview')},
      chipRules&&h('style',{'data-jq':'comments'},chipRules),
      highlightIndex>=0&&h('style',{'data-jq':'highlight'},`[data-conversation-session="${safeId(props.sessionId)}"] [data-composer-chip="${QUOTE_SOURCE}"]:nth-of-type(${highlightIndex+1})>span{background:var(--dsw-alias-interactive-bg-hover,#2631480f)}`),
      h('div',{className:'jq-dock-head'},h('span',null,`${items.length} ${t('quotes')} · ${t('total')} ${items.reduce((n,q)=>n+q.chars,0)} ${t('chars')}`),h('div',null,h('button',{type:'button',className:'jq-button',onClick:()=>{if(!confirm){setConfirm(true);return;}for(const q of items)removeItem(c,q);setConfirm(false);}},confirm?t('confirmClear'):t('clear')),items.length>3&&h('button',{type:'button',className:'jq-button',onClick:()=>setExpanded(!expanded)},t(expanded?'collapse':'expand')))),
      h('div',{className:'jq-dock-list','data-jq-expanded':expanded||undefined},(expanded?items:items.slice(0,3)).map((q,i)=>h('div',{key:q.id,className:'jq-row','data-jq-active':ui.highlight===refOf(q)||undefined,onPointerEnter:()=>emit({highlight:refOf(q)}),onPointerLeave:()=>emit({highlight:null})},h(Icon),
        h('button',{type:'button',className:'jq-button jq-summary','aria-label':`${t('preview')} ${i+1}`,'aria-haspopup':'dialog','aria-expanded':ui.preview?.ref===refOf(q),'aria-controls':ui.preview?.ref===refOf(q)?`jq-preview-${safeId(refOf(q))}`:undefined,onClick:e=>openPreview(c,refOf(q),undefined,e.detail===0)},h('span',{className:'jq-ellipsis'},`${i+1}. ${q.text.replace(/\s+/g,' ')}`)),q.comment&&h(R.Fragment,null,h('span',{className:'jq-separator','aria-hidden':true},'·'),h('span',{className:'jq-row-comment'},q.comment)),q.truncated&&h('span',{className:'jq-badge'},t('truncated')),h('div',{className:'jq-actions'},button(t('editNumber',{n:i+1}),e=>editItem(c,q,e.currentTarget.getBoundingClientRect()),'edit'),button(t('removeNumber',{n:i+1}),()=>removeItem(c,q),'delete'))))),ui.notice&&h('div',{className:'jq-alert',role:'status'},ui.notice)));
  }
  function SentQuotes({node}){const [expanded,setExpanded]=R.useState(false),id=R.useId(),items=node.data.quotes;
    return h('span',{className:'jq-sent','data-jq':'sent-quotes','data-jq-expanded':expanded||undefined},h('button',{type:'button',className:'jq-button jq-sent-toggle','aria-expanded':expanded,'aria-controls':expanded?id:undefined,'aria-label':t(expanded?'collapseSent':'expandSent',{n:items.length}),onClick:()=>setExpanded(!expanded)},h(Icon),t('sentQuotes',{n:items.length}),h('span',{className:'jq-sent-chevron','aria-hidden':true},expanded?'⌃':'⌄')),
      expanded&&h('span',{id,className:'jq-sent-body'},items.map((q,i)=>h('span',{key:i,className:'jq-sent-item'},h('span',{className:'jq-meta'},`${i+1} · ${t(q.source)}${q.truncated?` · ${t('truncated')}`:''}`),h('span',{className:`jq-sent-original ${q.kind==='code'?'jq-code':''}`},q.text),q.comment&&h('span',{className:'jq-sent-note'},q.comment)))));
  }
  ctx.effect(()=>{try{const registry=ctx.get('uiConversation')?.userText;if(!registry?.register)throw new Error('User text registry unavailable');return registry.register({id:QUOTE_SOURCE,order:-100,match:(text,from)=>{if(from!==0)return;const parsed=parseSentQuotes(text);if(parsed)return {id:QUOTE_SOURCE,start:0,end:parsed.end,data:{quotes:parsed.quotes}};if(text.startsWith('<juzi-quotes version="1"'))warn('sent quote format not recognized');}});}catch{warn('sent quote renderer unavailable');}});
  ctx.slots.inject('conversation.user.text.node',()=>ctx.slots.register({name:'conversation.user.text.node',key:QUOTE_SOURCE,priority:150},SentQuotes));
  ctx.effect(()=>ctx.locale.subscribe(()=>emit({})));
  ctx.effect(()=>{const style=document.createElement('style');style.dataset.jq='styles';style.textContent=QUOTE_CSS;document.head.append(style);return()=>style.remove();});
  ctx.effect(()=>ctx.inputTriggers.registerSource({trigger:'@',name:QUOTE_SOURCE,showGroupTitle:false,candidates:async()=>[],onPick:()=>undefined,codec:{clipboardText:ref=>`⟦${ref.slice(3)}⟧`,serialize},openReference:(session,reference)=>{const c=controls.get(session.sessionId);if(!c)return false;openPreview(c,reference.ref);return true;}}));
  ctx.slots.inject('conversation.input.dock',()=>ctx.slots.register({name:'conversation.input.dock',id:'juzi-quote-annotate',order:10},Dock));
  ctx.slots.inject('shell.overlay',()=>ctx.slots.register({name:'shell.overlay',id:'juzi-quote-annotate',order:10},Overlay));
  ctx.slots.inject('conversation.chat.assistant-actions',()=>ctx.slots.register({name:'conversation.chat.assistant-actions',id:'juzi-quote-anchor',order:100},p=>h('span',{'data-jq':'anchor','data-jq-message':p.messageId,hidden:true})));
  ctx.effect(()=>{
    for(const [name,fn] of eventBindings)document.addEventListener(name,fn,{passive:true,capture:true});window.addEventListener('resize',onScroll,{passive:true});
    const offStore=store.subscribe(id=>{const c=controls.get(id);if(c){c.repair=true;reconcile(c);}});
    const clean=()=>{const list=ctx.sessions.list.getSnapshot();if(list.phase==='ready')store.cleanup(new Set(list.ids));};clean();const offList=ctx.sessions.list.subscribe(clean);
    return()=>{disposed=true;clearTimeout(selectionTimer);hover.dispose();offStore();offList();for(const c of controls.values()){for(const off of c.off)off();for(const o of sourceRefs(c.input.state.getSnapshot()).toReversed())removeChip(c,o.ref);}for(const [name,fn] of eventBindings)document.removeEventListener(name,fn,true);window.removeEventListener('resize',onScroll);store.dispose();controls.clear();listeners.clear();};
  });
}
