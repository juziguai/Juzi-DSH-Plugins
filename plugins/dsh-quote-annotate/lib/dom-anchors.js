export const DOM_ANCHORS = Object.freeze({
  conversation:'[data-conversation-content][data-conversation-session]',chat:'[data-chat-flow]',row:'[data-chat-node-key]',scroll:'[data-conversation-scroll]',
  composer:'[data-composer-seat]',editor:'[contenteditable="true"][role="textbox"]',chip:'[data-composer-chip="juzi.quote-annotate"]',
  reasoning:'[data-variant="think"]',tool:'[data-variant="others"]',
  excluded:'button,[role="button"],[role="status"][aria-live],[aria-hidden="true"],[hidden],[inert],[data-jq],.jq-root,[data-line-number],.line-number,[data-composer-seat],[data-clock],[data-code-block-banner],[data-chat-flow-kind="turn-tail"]',
  codeWrap:'[data-code-wrap]',codeBanner:'[data-code-block-banner]',
  menu:'[role="dialog"][aria-modal="true"],[role="menu"],[role="listbox"],[data-radix-popper-content-wrapper]'
});
export function visibleTextRects(view,bounds,roots) {
  const chat=view.querySelector(DOM_ANCHORS.chat);if(!chat)return [];
  const out=[],range=chat.ownerDocument.createRange();
  for(const root of roots??[chat]){
   const walker=chat.ownerDocument.createTreeWalker(root,4);let node;
   while((node=walker.nextNode())){
    if(!node.textContent.trim()||node.parentElement.closest(DOM_ANCHORS.excluded))continue;
    const parent=node.parentElement.getBoundingClientRect();if(parent.bottom<=bounds.top||parent.top>=bounds.bottom)continue;
    range.selectNodeContents(node);if(typeof range.getClientRects!=='function')continue;
    for(const rect of range.getClientRects())if(rect.width>0&&rect.height>0&&rect.bottom>bounds.top&&rect.top<bounds.bottom)out.push({left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom});
   }
  }
  return out;
}
/** Observe message visibility off the selection path; never retain an unmounted view. */
export function createVisibleTextIndex(view) {
  const win=view.ownerDocument.defaultView,rows=new Set(),visible=new Set();let observed=false;
  const intersection=win.IntersectionObserver?new win.IntersectionObserver(entries=>{
    observed=true;for(const entry of entries)if(rows.has(entry.target)){if(entry.isIntersecting)visible.add(entry.target);else visible.delete(entry.target);}
  }):null;
  const visit=(node,add)=>{
    if(node.nodeType!==1)return;
    const candidates=[...(node.matches(DOM_ANCHORS.row)?[node]:[]),...node.querySelectorAll(DOM_ANCHORS.row)];
    for(const row of candidates){if(add){if(rows.has(row)||!row.closest(DOM_ANCHORS.chat))continue;rows.add(row);intersection?.observe(row);}else{rows.delete(row);visible.delete(row);intersection?.unobserve(row);}}
  };
  visit(view,true);
  const mutation=new win.MutationObserver(records=>{for(const record of records){for(const node of record.removedNodes)visit(node,false);for(const node of record.addedNodes)visit(node,true);}});
  mutation.observe(view,{childList:true,subtree:true});
  return {
    rects(bounds){
      // Before the first visibility delivery (or on hosts without IO), prune by row once.
      const roots=rows.size?(intersection&&observed?[...visible]:[...rows].filter(row=>{const r=row.getBoundingClientRect();return r.bottom>bounds.top&&r.top<bounds.bottom;})):undefined;
      return visibleTextRects(view,bounds,roots);
    },
    dispose(){intersection?.disconnect();mutation.disconnect();rows.clear();visible.clear();}
  };
}
export function extractSelection(selection,sessionId) {
  if(!selection||selection.isCollapsed||selection.rangeCount!==1)return null;
  const range=selection.getRangeAt(0),node=range.commonAncestorContainer;
  const doc=node.ownerDocument,context=(node.nodeType===1?node:node.parentElement)?.closest(DOM_ANCHORS.conversation);
  const roots=context?[context]:[...doc.querySelectorAll(DOM_ANCHORS.conversation)];
  const view=roots.find(root=>root.dataset.conversationSession===sessionId&&range.intersectsNode(root));
  const chat=view?.querySelector(DOM_ANCHORS.chat);
  if(!chat||!range.intersectsNode(chat))return null;
  const rects=[...range.getClientRects()].filter(r=>r.width>0&&r.height>0).map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}));
  const contributedRows=new Map();
  let text='',lastRow=null,lastBlock=null;
  const root=chat.contains(node)?node:chat;
  if((root.nodeType===1?root:root.parentElement)?.closest(DOM_ANCHORS.excluded))return null;
  const walker=doc.createTreeWalker(root,5,{acceptNode(current){
    if((current.nodeType===1?current:current.parentElement)?.closest(DOM_ANCHORS.excluded)||!range.intersectsNode(current))return 2;
    return 1;
  }});
  let current=root.nodeType===3?root:walker.nextNode();
  for(;current;current=walker.nextNode()) {
    if(current.nodeType===1){if(current.tagName==='BR'&&!current.closest(DOM_ANCHORS.excluded)&&range.intersectsNode(current))text+='\n';continue;}
    if(!current.textContent||current.parentElement.closest(DOM_ANCHORS.excluded)||!range.intersectsNode(current))continue;
    const part=range.cloneRange();part.selectNodeContents(current);
    if(current===range.startContainer)part.setStart(current,range.startOffset);
    if(current===range.endContainer)part.setEnd(current,range.endOffset);
    if(typeof part.getClientRects==='function'&&![...part.getClientRects()].some(r=>r.width>0&&r.height>0))continue;
    const row=current.parentElement.closest(DOM_ANCHORS.row),block=current.parentElement.closest('p,pre,li,h1,h2,h3,h4,blockquote');
    if(part.toString()&&row)contributedRows.set(row.dataset.chatNodeKey,row);
    if(text&&row!==lastRow)text+='\n\n';else if(text&&block!==lastBlock)text+='\n';
    text+=part.toString();lastRow=row;lastBlock=block;
  }
  if(!text.trim())return null;
  const selectedRows=[...contributedRows.values()];
  const start=range.startContainer.nodeType===1?range.startContainer:range.startContainer.parentElement;
  const end=range.endContainer.nodeType===1?range.endContainer:range.endContainer.parentElement;
  const code=start.closest('pre code');
  let source=selectedRows.length>1?'mixed':start.closest(DOM_ANCHORS.reasoning)?'reasoning':start.closest(DOM_ANCHORS.tool)?'tool':'unknown';
  const anchor=selectedRows[0]?.querySelector('[data-jq-message]');
  const kind=selectedRows[0]?.dataset.chatFlowKind;
  if(source==='unknown')source=anchor||kind==='assistant-step'?'assistant':kind==='user'?'user':'unknown';
  const language=code?.closest(DOM_ANCHORS.codeWrap)?.querySelector(DOM_ANCHORS.codeBanner)?.firstElementChild?.textContent.trim();
  const metadata={source,...(anchor&&source!=='mixed'?{messageId:anchor.dataset.jqMessage}:{}),
    ...(source!=='mixed'&&Number(selectedRows[0]?.dataset.chatTurn)>0?{turn:Number(selectedRows[0].dataset.chatTurn)}:{}),
    ...(code&&code.contains(end)?{kind:'code',lang:language??[...code.classList].find(c=>c.startsWith('language-'))?.slice(9)??''}:{})};
  const bounds=chat.getBoundingClientRect(),scroll=chat.closest(DOM_ANCHORS.scroll)?.getBoundingClientRect(),composer=view.querySelector(DOM_ANCHORS.composer)?.getBoundingClientRect();
  const viewport=view.getBoundingClientRect(),vertical={top:Math.max(0,scroll?.top??bounds.top),bottom:Math.min(doc.defaultView.innerHeight,composer?.top??doc.defaultView.innerHeight)};
  return {text,metadata,rects,view,range:range.cloneRange(),bounds:{left:Math.max(0,bounds.left),right:Math.min(doc.defaultView.innerWidth,bounds.right),...vertical},sideBounds:{left:Math.max(0,viewport.width?viewport.left:bounds.left),right:Math.min(doc.defaultView.innerWidth,viewport.width?viewport.right:bounds.right),...vertical},sessionId};
}
export function editorBridge(view,source) {
  const element=view?.querySelector(DOM_ANCHORS.composer)?.querySelector(DOM_ANCHORS.editor);
  const editor=element?.__lexicalEditor;
  if(!editor||typeof editor.update!=='function'||!(editor.getEditorState()?._nodeMap instanceof Map))throw new Error('DSH editor bridge unavailable');
  const nodes=()=>[...editor.getEditorState()._nodeMap.values()].filter(n=>n.getType?.()==='reference-chip'&&n.__source===source);
  return {element,
    prefix(order){if(order?.length===0||nodes().length===0)return;editor.update(()=>{const map=editor.getEditorState()._nodeMap,root=map.get('root'),first=root?.getFirstChild();if(!first?.getChildren)return;const own=nodes(),refs=order?order.map(ref=>own.find(node=>node.__ref===ref)).filter(Boolean):own;for(const node of refs.toReversed()) {const head=first.getFirstChild();if(head!==node)head?head.insertBefore(node):first.append(node);}},{discrete:true});}
  };
}
