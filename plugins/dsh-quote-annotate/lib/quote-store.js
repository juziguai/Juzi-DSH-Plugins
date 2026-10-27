import { STORAGE_PREFIX, MAX_QUOTES, MAX_QUOTE_CHARS, MAX_COMMENT_CHARS, DRAFT_TTL, normalizeComment, countChars } from './quote-core.js';
const emptyDocument = () => ({v:1,items:[],tombstones:{}});
const stamp = row => row?._stamp ?? [row?.createdAt ?? 0,''];
const newer = (a,b) => !b || stamp(a)[0] > stamp(b)[0] || stamp(a)[0] === stamp(b)[0] && stamp(a)[1] > stamp(b)[1];
export function mergeDocuments(a,b,now=Date.now()) {
  const rows=new Map(),tombstones={};
  for(const doc of [a,b]) {
    for(const [id,row] of Object.entries(doc?.tombstones??{})) if(now-row.createdAt < DRAFT_TTL && newer(row,tombstones[id])) tombstones[id]=row;
    for(const row of doc?.items??[]) if(now-row.createdAt < DRAFT_TTL && newer(row,rows.get(row.id))) rows.set(row.id,row);
  }
  return {v:1,items:[...rows.values()].filter(row=>!tombstones[row.id]||newer(row,tombstones[row.id])).sort((x,y)=>x.createdAt-y.createdAt||x.id.localeCompare(y.id)).slice(0,MAX_QUOTES),
    tombstones:Object.fromEntries(Object.entries(tombstones).sort(([x],[y])=>x.localeCompare(y)))};
}
export function decodeDocument(raw,now=Date.now()) {
  if(!raw)return emptyDocument();
  const v=JSON.parse(raw);
  if(v?.v!==1||!Array.isArray(v.items))throw new Error('Unsupported quote draft');
  const validStamp=s=>s===undefined||Array.isArray(s)&&s.length===2&&Number.isFinite(s[0])&&typeof s[1]==='string';
  for(const q of v.items)if(!q||typeof q.id!=='string'||typeof q.text!=='string'||!q.text.trim()||countChars(q.text)>MAX_QUOTE_CHARS||!Number.isSafeInteger(q.chars)||q.chars<countChars(q.text)||!['user','assistant','reasoning','tool','mixed','unknown'].includes(q.source)||typeof q.truncated!=='boolean'||!Number.isFinite(q.createdAt)||typeof q.comment!=='string'||countChars(q.comment)>MAX_COMMENT_CHARS)throw new Error('Invalid quote draft');
  if(v.items.some(q=>!validStamp(q._stamp))||Object.values(v.tombstones??{}).some(q=>!q||!Number.isFinite(q.createdAt)||!validStamp(q._stamp)))throw new Error('Invalid quote revisions');
  return mergeDocuments(emptyDocument(),v,now);
}
export function createQuoteStore({storage,events,actor=crypto.randomUUID(),warn=()=>{},now=Date.now}) {
  const docs=new Map(),listeners=new Set(),warned=new Set();let clock=0;
  const warnOnce=code=>{if(!warned.has(code)){warned.add(code);warn(code);}};
  const key=id=>STORAGE_PREFIX+id;
  if(!storage)warnOnce('storage');
  const read=id=>{let raw;try{raw=storage?.getItem(key(id));}catch{warnOnce('storage');return emptyDocument();}try{return decodeDocument(raw,now());}catch{warnOnce('corrupt');return emptyDocument();}};
  const get=id=>{if(!docs.has(id))docs.set(id,read(id));return docs.get(id);};
  const notify=id=>{for(const fn of listeners)fn(id);};
  const write=(id,doc)=>{
    const merged=mergeDocuments(mergeDocuments(get(id),read(id),now()),doc,now());docs.set(id,merged);
    try{const raw=JSON.stringify(merged);if(storage?.getItem(key(id))!==raw)storage?.setItem(key(id),raw);}catch{warnOnce('quota');}
    notify(id);return merged.items;
  };
  const tick=()=>[clock=Math.max(clock+1,now()),actor];
  const remove=(id,ids)=>{const doc=get(id),tombstones={...doc.tombstones};for(const x of ids)tombstones[x]={createdAt:now(),_stamp:tick()};return write(id,{...doc,items:doc.items.filter(q=>!ids.includes(q.id)),tombstones});};
  const onStorage=e=>{if(!e.key?.startsWith(STORAGE_PREFIX))return;const id=e.key.slice(STORAGE_PREFIX.length);try{write(id,decodeDocument(e.newValue,now()));}catch{warnOnce('corrupt');}};
  events?.addEventListener('storage',onStorage);
  return {
    items:id=>get(id).items,
    isRemoved:(id,quoteId)=>!!get(id).tombstones[quoteId]&&!get(id).items.some(q=>q.id===quoteId),
    add(id,q){if(get(id).items.length>=MAX_QUOTES)throw new RangeError('最多 20 条引用');write(id,{...get(id),items:[...get(id).items,{...q,_stamp:tick()}]});},
    edit(id,quoteId,value){const comment=normalizeComment(value);write(id,{...get(id),items:get(id).items.map(q=>q.id===quoteId?{...q,comment,_stamp:tick()}:q)});},
    remove, clear:id=>remove(id,get(id).items.map(q=>q.id)),
    subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},
    cleanup(validIds){try{for(let i=storage.length-1;i>=0;i--){const k=storage.key(i);if(!k?.startsWith(STORAGE_PREFIX))continue;const id=k.slice(STORAGE_PREFIX.length);if(!validIds.has(id)){storage.removeItem(k);docs.delete(id);}else write(id,get(id));}}catch{warnOnce('quota');}},
    dispose(){events?.removeEventListener('storage',onStorage);listeners.clear();docs.clear();}
  };
}
