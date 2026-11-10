import { useEffect, useState } from 'react';
import {
  getDelivery, generateDeliveryDesign, decideDeliveryDesign,
  generateDeliveryPlan, decideDeliveryPlan, type DeliveryArtifacts,
} from './services/api';

type Props = { projectId: string; backlogId: string; role: string; onChanged?: () => void | Promise<void> };
export default function Phase7Delivery({projectId,backlogId,role,onChanged}: Props) {
  const [data,setData]=useState<DeliveryArtifacts|null>(null);
  const [note,setNote]=useState('Reviewed against source requirements, approved stories and traceability.');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [message,setMessage]=useState('');
  const canGenerate=['admin','product_owner','engineer'].includes(role);
  const canApprove=['admin','product_owner'].includes(role);
  const refresh=async()=>setData(await getDelivery(projectId,backlogId));
  useEffect(()=>{setData(null);setError('');refresh().catch(e=>setError(String(e)));},[projectId,backlogId]);
  async function act(fn:()=>Promise<unknown>,messageText:string) {
    setBusy(true);setError('');setMessage('');
    try {await fn();await refresh();await onChanged?.();setMessage(messageText);} catch(e){setError(String(e));}
    finally{setBusy(false);}
  }
  const design=data?.artifacts?.design;
  const plan=data?.artifacts?.plan;
  return <section className="result-card" aria-label="Phase 7 delivery orchestration">
    <p className="eyebrow">07B · UNIFIED DELIVERY ORCHESTRATION</p>
    <h3>Solution design → PO review → delivery tasks → PO review</h3>
    <p>Only source-supported, quality-cleared and PO-approved stories are included. Generated technical design and estimates are proposals until reviewed.</p>
    <p><strong>Design:</strong> {design?.status ?? 'not generated'} · <strong>Plan:</strong> {plan?.status ?? 'not generated'}</p>
    <button disabled={busy} onClick={()=>refresh().catch(e=>setError(String(e)))}>Refresh artifacts</button>{' '}
    <button disabled={busy||!canGenerate||design?.status==='approved'||Boolean(plan)} onClick={()=>act(()=>generateDeliveryDesign(projectId,backlogId),'Draft design generated. Review before approval.')}>Generate / regenerate draft design</button>
    {design&&<div>
      <h4>Proposed solution design</h4>
      <p>Stories: {design.artifact.scope.story_keys.join(', ')}</p>
      <p>Architecture: {design.artifact.architecture.flow.join(' → ')}</p>
      <details><summary>Review full draft (architecture, APIs, data model, assumptions)</summary><pre>{JSON.stringify(design.artifact,null,2)}</pre></details>
      <p><small>Authenticated Markdown export: GET /api/v1/projects/{projectId}/backlogs/{backlogId}/delivery/design.md (Swagger).</small></p>
      {design.status==='draft'&&canApprove&&<div>
        <label>Product Owner decision note<textarea rows={2} value={note} onChange={e=>setNote(e.target.value)}/></label>
        <button disabled={busy||note.trim().length<10} onClick={()=>act(()=>decideDeliveryDesign(projectId,backlogId,true,note),'Design approved.')}>Approve design</button>{' '}
        <button disabled={busy||note.trim().length<10} onClick={()=>act(()=>decideDeliveryDesign(projectId,backlogId,false,note),'Design rejected.')}>Reject design</button>
      </div>}
    </div>}
    <hr/>
    <button disabled={busy||!canGenerate||design?.status!=='approved'||Boolean(plan)} onClick={()=>act(()=>generateDeliveryPlan(projectId,backlogId),'Implementation tasks generated.')}>Generate implementation plan</button>
    {plan&&<div>
      <h4>Implementation plan · {plan.artifact.tasks.length} tasks</h4>
      <p>Story scope: {plan.artifact.story_keys.join(', ')}</p>
      <details><summary>Review tasks, estimates and dependencies</summary><pre>{JSON.stringify(plan.artifact,null,2)}</pre></details>
      {plan.status==='draft'&&canApprove&&<div>
        <label>Product Owner decision note<textarea rows={2} value={note} onChange={e=>setNote(e.target.value)}/></label>
        <button disabled={busy||note.trim().length<10} onClick={()=>act(()=>decideDeliveryPlan(projectId,backlogId,true,note),'Plan approved. Ready for delivery.')}>Approve plan</button>{' '}
        <button disabled={busy||note.trim().length<10} onClick={()=>act(()=>decideDeliveryPlan(projectId,backlogId,false,note),'Plan rejected.')}>Reject plan</button>
      </div>}
    </div>}
    {plan?.status==='approved'&&<p><strong>Delivery artifacts approved.</strong> Story-level publishing restrictions remain unchanged.</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  </section>;
}
