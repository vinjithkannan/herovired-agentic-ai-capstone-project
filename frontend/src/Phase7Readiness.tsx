import { useState } from 'react';
import type { BacklogResult } from './services/api';

function summary(backlog: BacklogResult) {
  const counts = { quality_cleared: 0, review_required: 0, blocked: 0, unknown: 0 };
  let poApproved = 0;
  let eligible = 0;
  for (const story of backlog.stories) {
    const clearance = backlog.story_clearances?.[story.story_key]?.status;
    if (clearance === 'quality_cleared') counts.quality_cleared++;
    else if (clearance === 'review_required') counts.review_required++;
    else if (clearance === 'blocked') counts.blocked++;
    else counts.unknown++;
    if (story.approval_status === 'approved') poApproved++;
    if (clearance === 'quality_cleared' && story.approval_status === 'approved') eligible++;
  }
  return { ...counts, total: backlog.stories.length, po_approved: poApproved,
    eligible_for_live_publishing: eligible, requirement_ids: backlog.source_requirement_ids.length,
    acceptance_criteria: backlog.acceptance_criteria.length };
}

export default function Phase7Readiness({backlog}: {backlog:BacklogResult}) {
  const [note,setNote] = useState('Demo snapshot; unresolved stories remain subject to review and quality restrictions.');
  const stats=summary(backlog);
  const blockers=backlog.validation?.issues?.filter(x=>['high','critical'].includes(x.severity?.toLowerCase() ?? '')) ?? [];
  function exportReport() {
    const report={schema_version:'reqflow-phase7-demo-v1',generated_at:new Date().toISOString(),
      backlog_id:backlog.backlog_id,source_requirement_ids:backlog.source_requirement_ids,
      metrics:stats,high_critical_findings:blockers.map(x=>({story_key:x.story_key,issue_type:x.issue_type,severity:x.severity,description:x.description})),
      quality_clearances:backlog.story_clearances ?? {},
      story_approvals:backlog.stories.map(s=>({story_key:s.story_key,approval_status:s.approval_status ?? 'pending'})),
      operator_note:note,limitations:[
        'Requirement-ID coverage is not semantic accuracy.',
        'Quality clearance and product-owner approval are separate.',
        'Only quality-cleared AND product-owner-approved stories can be live-published.',
        'Export contains local backlog evidence, not live provider availability or performance benchmark results.'
      ]};
    const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);const a=document.createElement('a');
    a.href=url;a.download=`reqflow-phase7-report-${backlog.backlog_id}.json`;a.click();URL.revokeObjectURL(url);
  }
  return <section className="result-card" aria-label="Phase 7 capstone demo readiness">
    <h3>07 · Capstone demo &amp; release evidence</h3>
    <p>Read-only snapshot of the selected saved backlog. This dashboard never changes clearances or approvals.</p>
    <p><strong>{stats.total}</strong> stories · <strong>{stats.quality_cleared}</strong> quality-cleared · <strong>{stats.review_required}</strong> review required · <strong>{stats.blocked}</strong> blocked · <strong>{stats.unknown}</strong> unknown</p>
    <p><strong>{stats.po_approved}</strong> PO-approved · <strong>{stats.eligible_for_live_publishing}</strong> clearance-and-approval eligible · <strong>{stats.requirement_ids}</strong> source IDs · <strong>{stats.acceptance_criteria}</strong> criteria</p>
    {blockers.length > 0 && <p role="status">{blockers.length} high/critical quality findings remain. This is a partial capstone demonstration, not full backlog sign-off.</p>}
    {stats.review_required + stats.blocked + stats.unknown > 0 && <p role="status">Outstanding stories must not be presented as fully quality-cleared.</p>}
    <label>Demo evidence note<textarea rows={2} value={note} onChange={e=>setNote(e.target.value)} /></label>
    <button onClick={exportReport}>Export Phase 7 demo report (JSON)</button>
    <small>No changes to PostgreSQL, Jira, GitHub, approvals or quality gates.</small>
  </section>;
}
