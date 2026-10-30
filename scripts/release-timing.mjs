import {randomUUID} from 'node:crypto';
import {appendFileSync} from 'node:fs';
import {mkdir, readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {step} from './release-core.mjs';

const print=({phase,status,elapsedMs,reused})=>console.log(JSON.stringify({phase,status,elapsedMs,...(typeof reused==='boolean'?{reused}:{})}));

export async function withTiming(directory, command, action, {report=print}={}) {
  await mkdir(directory,{recursive:true});
  const runId=randomUUID(),path=join(directory,'timing.jsonl');
  const measure=(scope,phase,task)=>{
    const stageId=randomUUID();
    return step(phase,task,{report:event=>{
      const row={version:1,runId,command,scope,stageId,at:new Date().toISOString(),...event};
      // Persist boundaries before advancing. A missing terminal event remains visibly incomplete.
      if(event.status!=='running')appendFileSync(path,JSON.stringify(row)+'\n');
      report(row);
    }});
  };
  return measure('command',command,()=>action((phase,task)=>measure('phase',phase,task)));
}

export function summarizeTimings(events) {
  const runs=new Map();
  for(const event of events){
    if(event.version!==1||!event.runId||!event.stageId||!event.command||!event.phase||
      !['command','phase'].includes(event.scope)||!['started','completed','failed'].includes(event.status)||
      !Number.isFinite(event.elapsedMs)||event.elapsedMs<0||!Number.isFinite(Date.parse(event.at)))throw Error('Invalid release timing event');
    let run=runs.get(event.runId);
    if(!run){run={runId:event.runId,command:event.command,stages:new Map()};runs.set(event.runId,run);}
    if(run.command!==event.command)throw Error('Release timing command changed within a run');
    const prior=run.stages.get(event.stageId);
    if(event.status==='started'?!!prior:!prior||prior.status!=='incomplete'||event.elapsedMs<prior.elapsedMs)throw Error('Invalid release timing sequence');
    run.stages.set(event.stageId,{scope:event.scope,phase:event.phase,status:event.status==='started'?'incomplete':event.status,
      startedAt:prior?.startedAt??event.at,finishedAt:event.status==='started'?null:event.at,elapsedMs:event.elapsedMs,
      ...(typeof event.reused==='boolean'?{reused:event.reused}:{})});
  }
  const result=[];
  for(const run of runs.values()){
    const stages=[...run.stages.values()],commands=stages.filter(s=>s.scope==='command');
    if(commands.length!==1)throw Error('Release timing run requires one command boundary');
    const current={runId:run.runId,command:run.command,...commands[0],stages:stages.filter(s=>s.scope==='phase')};
    const previous=result.at(-1),gap=previous?.finishedAt?Date.parse(current.startedAt)-Date.parse(previous.finishedAt):null;
    current.gapBeforeMs=gap!==null&&gap>=0?gap:null;
    result.push(current);
  }
  return {runs:result,measuredCommandMs:result.filter(r=>r.status!=='incomplete').reduce((sum,r)=>sum+r.elapsedMs,0),
    incompleteCommands:result.filter(r=>r.status==='incomplete').length,
    betweenCommandsMs:result.reduce((sum,r)=>sum+(r.gapBeforeMs??0),0)};
}

export async function timingReport(directory) {
  let text;
  try{text=await readFile(join(directory,'timing.jsonl'),'utf8');}
  catch(error){if(error.code!=='ENOENT')throw error;return summarizeTimings([]);}
  return summarizeTimings(text.split('\n').filter(line=>line.trim()).map((line,i)=>{
    try{return JSON.parse(line);}catch{throw Error(`Invalid release timing JSON at line ${i+1}; preserve the journal for inspection`);}
  }));
}
