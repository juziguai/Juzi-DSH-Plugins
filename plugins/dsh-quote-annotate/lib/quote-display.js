import { INTRO, MAX_QUOTES, MAX_QUOTE_CHARS } from './quote-core.js';

const decodeQuoted = text => text.replace(/&(amp|lt|gt);/g, (_, entity) => ({amp:'&',lt:'<',gt:'>'})[entity]);
// Parse only our canonical wire prefix. The fixed INTRO itself contains a literal closing tag.
export function parseSentQuotes(text) {
  if(typeof text!=='string')return null;
  const header=text.match(/^<juzi-quotes version="1" count="([1-9]\d*)">\n/);
  if(!header||Number(header[1])>MAX_QUOTES)return null;
  let cursor=header[0].length;
  if(!text.startsWith(INTRO+'\n',cursor))return null;
  cursor+=INTRO.length+1;const quotes=[];
  const readBody=end=>{const at=text.indexOf(end,cursor);if(at<0)return null;const raw=text.slice(cursor,at);if(/[<>]|&(?!amp;|lt;|gt;)/.test(raw))return null;cursor=at+end.length;return decodeQuoted(raw);};
  for(let i=1;i<=Number(header[1]);i++){
    const open=text.slice(cursor).match(/^<quote ([^>\n]+)>\n<text>\n/);if(!open)return null;
    const attrs={},pairs=[...open[1].matchAll(/([a-z-]+)="([^"]*)"/g)];
    if(pairs.map(p=>p[0]).join(' ')!==open[1])return null;
    for(const [,key,value]of pairs){if(Object.hasOwn(attrs,key))return null;attrs[key]=value;}
    if(Object.keys(attrs).some(key=>!['index','source','message-id','turn','chars','truncated','kept-chars','kind'].includes(key)))return null;
    if(attrs.index!==String(i)||!['user','assistant','reasoning','tool','mixed','unknown'].includes(attrs.source)||!/^\d+$/.test(attrs.chars)||!Number.isSafeInteger(Number(attrs.chars))||!['true','false'].includes(attrs.truncated))return null;
    if(attrs['message-id']&&!/^[A-Za-z0-9_:.-]+$/.test(attrs['message-id'])||attrs.turn&&!/^[1-9]\d*$/.test(attrs.turn)||attrs.kind&&attrs.kind!=='code')return null;
    const truncated=attrs.truncated==='true';if(truncated?attrs['kept-chars']!==String(MAX_QUOTE_CHARS):attrs['kept-chars']!==undefined)return null;
    cursor+=open[0].length;const original=readBody('\n</text>\n');if(original===null)return null;
    let comment='';if(text.startsWith('<comment>',cursor)){cursor+=9;comment=readBody('</comment>\n');if(comment===null)return null;}
    if(!text.startsWith('</quote>\n',cursor))return null;cursor+=9;
    quotes.push({source:attrs.source,text:original,comment,truncated,chars:Number(attrs.chars),...(attrs.kind?{kind:attrs.kind}:{}),...(attrs.turn?{turn:Number(attrs.turn)}:{})});
  }
  const ending='</juzi-quotes>\n\n用户本轮要求：\n';
  if(!text.startsWith(ending,cursor))return null;
  return {quotes,end:cursor+ending.length};
}
