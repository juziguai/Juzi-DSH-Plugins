export const DOM_ANCHORS = Object.freeze({
  conversation:'[data-conversation-content][data-conversation-session]',chat:'[data-chat-flow]',row:'[data-chat-node-key]',scroll:'[data-conversation-scroll]',
  composer:'[data-composer-seat]',editor:'[contenteditable="true"][role="textbox"]',chip:'[data-composer-chip="juzi.quote-annotate"]',
  reasoning:'[data-variant="think"]',tool:'[data-variant="others"]',
  excluded:'button,[role="button"],[role="status"][aria-live],[aria-hidden="true"],[hidden],[inert],[data-jq],.jq-root,[data-line-number],.line-number,[data-composer-seat],[data-clock],[data-code-block-banner],[data-chat-flow-kind="turn-tail"]',
  codeWrap:'[data-code-wrap]',codeBanner:'[data-code-block-banner]',
  menu:'[role="dialog"][aria-modal="true"],[role="menu"],[role="listbox"],[data-radix-popper-content-wrapper]'
});
export function visibleTextRects(view,bounds) {
  const chat=view.querySelector(DOM_ANCHORS.chat);if(!chat)return [];
  const out=[],walker=chat.ownerDocument.createTreeWalker(chat,4),range=chat.ownerDocument.createRange();let node;
  while((node=walker.nextNode())){
    if(!node.textContent.trim()||node.parentElement.closest(DOM_ANCHORS.excluded))continue;
    const parent=node.parentElement.getBoundingClientRect();if(parent.bottom<=bounds.top||parent.top>=bounds.bottom)continue;
    range.selectNodeContents(node);if(typeof range.getClientRects!=='function')continue;
    for(const rect of range.getClientRects())if(rect.width>0&&rect.height>0&&rect.bottom>bounds.top&&rect.top<bounds.bottom)out.push({left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom});
  }
  return out;
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
  const walker=doc.createTreeWalker(chat,5);
  let current;
  while((current=walker.nextNode())) {
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
    prefix(order){editor.update(()=>{const map=editor.getEditorState()._nodeMap,root=map.get('root'),first=root?.getFirstChild();if(!first?.getChildren)throw new Error('DSH paragraph unavailable');const own=nodes(),refs=order?order.map(ref=>own.find(node=>node.__ref===ref)).filter(Boolean):own;for(const node of refs.toReversed()) {const head=first.getFirstChild();if(head!==node)head?head.insertBefore(node):first.append(node);}},{discrete:true});}
  };
}
