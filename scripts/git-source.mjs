import {execFileSync} from 'node:child_process';

export const git = (cwd, args, options={}) => execFileSync('git', args, {
  cwd, encoding:'utf8', windowsHide:true, stdio:['pipe','pipe','pipe'], maxBuffer:32*1024*1024, ...options,
});

export function readTree(cwd, commit, paths=[]) {
  const rows=git(cwd,['ls-tree','-rz','--full-tree',commit,'--',...paths]).split('\0').filter(Boolean);
  return new Map(rows.map(row=>{
    const match=/^(\d{6}) (blob|commit) ([0-9a-f]{40})\t([\s\S]+)$/.exec(row);
    if(!match)throw Error('Unsupported Git tree row');
    return [match[4],{mode:match[1],type:match[2],sha:match[3],path:match[4]}];
  }));
}

export function readBlobs(cwd, objects) {
  const ids=[...new Set(objects)];
  if(ids.some(id=>!(/^[0-9a-f]{40}$/).test(id)))throw Error('Git blobs require full object IDs');
  if(!ids.length)return new Map();
  const bytes=git(cwd,['cat-file','--batch'],{input:ids.join('\n')+'\n',encoding:null});
  const blobs=new Map();let offset=0;
  for(const id of ids){
    const end=bytes.indexOf(10,offset),header=bytes.subarray(offset,end).toString();
    const match=/^([0-9a-f]{40}) blob (\d+)$/.exec(header);
    if(end<offset||!match||match[1]!==id)throw Error('Git blob batch mismatch');
    const size=Number(match[2]),start=end+1,next=start+size;
    if(!Number.isSafeInteger(size)||next>=bytes.length||bytes[next]!==10)throw Error('Truncated Git blob batch');
    blobs.set(id,bytes.subarray(start,next));offset=next+1;
  }
  if(offset!==bytes.length)throw Error('Unexpected Git blob batch data');
  return blobs;
}
