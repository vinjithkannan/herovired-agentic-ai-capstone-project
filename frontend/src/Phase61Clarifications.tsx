import { useEffect, useState } from 'react';
import { listClarifications, proposeClarification, decideClarification, finalizeClarifications, supersedeClarification, previewClarificationQuality, type Clarification, type BacklogResult, type SessionUser } from './services/api';

type Props={projectId:string;backlog:BacklogResult;user:SessionUser;onBacklog:(id:string)=>Promise<void>};
export default function Phase61Clarifications({projectId,backlog,user,onBacklog}:Props){
  const [decisions,setDecisions]=useState<Clarification[]>([]);
  const [storyKey,setStoryKey]=useState('');
  const [title,setTitle]=useState('');
  const [storyText,setStoryText]=useState('');
  const [rationale,setRationale]=useState('');
  const [criterionText,setCriterionText]=useState('');
  const [testType,setTestType]=useState('functional');
  const [note,setNote]=useState('Reviewed against the source requirement and acceptance criteria.');
  const [notice,setNotice]=useState('');
  const [preview,setPreview]=useState<{ready_to_finalize:boolean;quality_cleared:number;total_stories:number;validation:{issues:{story_key:string;severity:string;description:string}[]}}|null>(null);
  const [busy,setBusy]=useState(false);
  const canPropose=['admin','product_owner','engineer'].includes(user.role);
  const canDecide=['admin','product_owner'].includes(user.role);
  const id=backlog.backlog_id;
  async function refresh(){setDecisions(await listClarifications(projectId,id));}
  useEffect(()=>{setStoryKey('');setDecisions([]);setPreview(null);refresh().catch(e=>setNotice(String(e)));},[projectId,id]);
  const toReview=backlog.stories.filter(s=>backlog.story_clearances?.[s.story_key]?.status!=='quality_cleared');
  const selected=backlog.stories.find(s=>s.story_key===storyKey);
  function pick(key:string){const s=backlog.stories.find(x=>x.story_key===key);setStoryKey(key);setTitle(s?.title||'');setStoryText(s?.story_text||'');setRationale('');setCriterionText(backlog.acceptance_criteria.filter(c=>c.story_key===key).map(c=>c.criterion_text).join('\n'));setTestType(s?.source_requirement_ids.includes('NFR-004')?'performance':'functional');}
  const active=decisions.find(d=>d.story_key===storyKey&&(d.status==='proposed'||d.status==='approved'));
  async function submit(){setBusy(true);setNotice('');try{const criteria=criterionText.split('\n').map(x=>x.trim()).filter(Boolean).map(x=>({criterion_text:x,test_type:testType}));await proposeClarification(projectId,id,storyKey,{title,story_text:storyText,rationale,acceptance_criteria:criteria});await refresh();setPreview(null);setNotice('Proposal saved. Product Owner decision required. No story has been approved.');}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
  async function decide(d:Clarification,approve:boolean){setBusy(true);setNotice('');try{await decideClarification(projectId,id,d.id,approve,note);await refresh();setPreview(null);setNotice('Clarification decision saved. Final story approval remains separate.')}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
  async function supersede(d:Clarification){setBusy(true);try{await supersedeClarification(projectId,id,d.id,note);await refresh();setPreview(null);setNotice('Prior approval superseded. Submit a corrected proposal.')}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
  async function finalize(){setBusy(true);setNotice('');try{const result=await finalizeClarifications(projectId,id);await onBacklog(result.backlog_id);setNotice('New validated backlog saved. All story approvals reset to pending.')}catch(e){setNotice((e as Error).message)}finally{setBusy(false)}}
  return <section className="result-card" style={{marginTop:20}}>
    <h3>Phase 6.1 · Product Owner clarifications</h3>
    <p>Clarify outstanding stories without bypassing the quality gate. Proposed performance targets must be agreed by the Product Owner. This does not authorize external publishing.</p>
    <p>{toReview.length} stories need review · {decisions.filter(d=>d.status==='approved').length} approved clarifications</p>
    <label>Story requiring clarification <select value={storyKey} onChange={e=>pick(e.target.value)}><option value="">Select story</option>{toReview.map(s=><option key={s.story_key} value={s.story_key}>{s.story_key} · {s.title}</option>)}</select></label>
    {selected&&<div>
      <p>Source requirements: {selected.source_requirement_ids.join(', ')}</p>
      <p>Existing assumptions: {selected.assumptions.join('; ') || 'none'}</p>
      <label>Revised title<input value={title} onChange={e=>setTitle(e.target.value)} disabled={!canPropose||!!active}/></label>
      <label>Revised story<textarea value={storyText} onChange={e=>setStoryText(e.target.value)} disabled={!canPropose||!!active} rows={3}/></label>
      <label>Approved business decision and rationale<textarea value={rationale} onChange={e=>setRationale(e.target.value)} disabled={!canPropose||!!active} rows={3} placeholder="Explain the proposed clarification and source/PO decision"/></label>
      <label>Acceptance criteria: one Given–When–Then criterion per line<textarea value={criterionText} onChange={e=>setCriterionText(e.target.value)} disabled={!canPropose||!!active} rows={5}/></label>
      <label>Criterion type<select value={testType} onChange={e=>setTestType(e.target.value)} disabled={!canPropose||!!active}>{['functional','security','audit','performance','availability','non_functional'].map(x=><option key={x} value={x}>{x}</option>)}</select></label>
      <button disabled={!canPropose||busy||!!active||!rationale.trim()||!criterionText.trim()} onClick={submit}>Submit clarification proposal</button>
    </div>}
    {canDecide&&<label>Product Owner decision note<input value={note} onChange={e=>setNote(e.target.value)}/></label>}
    {decisions.map(d=><div key={d.id} className="result-card"><strong>{d.story_key} · {d.status}</strong><p>{d.proposal.rationale}</p>{d.decision_note&&<p>Decision: {d.decision_note}</p>}{d.status==='proposed'&&canDecide&&<><button disabled={busy||note.length<10} onClick={()=>decide(d,true)}>Approve clarification</button> <button disabled={busy||note.length<10} onClick={()=>decide(d,false)}>Reject clarification</button></>}{d.status==='approved'&&canDecide&&<button disabled={busy||note.length<10} onClick={()=>supersede(d)}>Supersede approval and revise</button>}</div>)}
    <button disabled={busy} onClick={async()=>{try{setPreview(await previewClarificationQuality(projectId,id))}catch(e){setNotice((e as Error).message)}}}>Preview quality after approved clarifications</button>
    {preview&&<div className="result-card"><strong>{preview.quality_cleared}/{preview.total_stories} quality-cleared · {preview.ready_to_finalize?'Ready to finalize':'Further review needed'}</strong>{preview.validation.issues.map((issue,i)=><p key={i}>{issue.story_key} · {issue.severity}: {issue.description}</p>)}</div>}
    {canDecide&&<button disabled={busy||!preview?.ready_to_finalize} onClick={finalize}>Finalize revised backlog and revalidate</button>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
