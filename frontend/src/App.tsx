import Phase7Readiness from "./Phase7Readiness";
import Phase7Delivery from "./Phase7Delivery";
import Phase61Clarifications from "./Phase61Clarifications";
import { useEffect, useState } from "react";
import { createProject, login, logout, setSessionToken, hasSessionToken, currentUser, type SessionUser, evaluateBacklog, getDocuments, getHealth, getProjects, getSystemInfo, searchRequirements, uploadDocument, analyzeProject, generateBacklog, getBacklog, getBacklogs, setStoryApproval, repairBacklog, previewPublication, publishApprovedStory, getPublications, type PublishRecord, type PublishPreview, type BacklogResult, type AnalysisResult, type DocRecord, type Project, type SearchResult, getAnalysis, getDelivery, type DeliveryArtifacts } from "./services/api";

export default function App() {
  const [user,setUser] = useState<SessionUser|null>(null);
  const [restoringSession,setRestoringSession] = useState(hasSessionToken());
  const [loginName,setLoginName]=useState('');
  const [loginPassword,setLoginPassword]=useState('');
  const [evaluationGold,setEvaluationGold]=useState('FR-001,FR-002,FR-003,FR-004,FR-005,NFR-001,NFR-002,NFR-003,NFR-004');
  const [evaluationOutput,setEvaluationOutput]=useState<Record<string,unknown>|null>(null);
  const [health, setHealth] = useState<{status: string} | null>(null);
  const [system, setSystem] = useState<Record<string, unknown> | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [documents, setDocuments] = useState<DocRecord[]>([]);
  const [projectName, setProjectName] = useState("Student Attendance Management");
  const [description, setDescription] = useState("BRD ingestion and requirements discovery");
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("What attendance alerts and reports are required?");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [backlog, setBacklog] = useState<BacklogResult | null>(null);
  const [deliverySummary, setDeliverySummary] = useState<DeliveryArtifacts|null>(null);
  const [previousBacklogs, setPreviousBacklogs] = useState<{id: string; created_at: string}[]>([]);
  const [publishProvider, setPublishProvider] = useState("github");
  const [publishPreview, setPublishPreview] = useState<PublishPreview | null>(null);
  const [publishRecords, setPublishRecords] = useState<PublishRecord[]>([]);
  const [publishStoryKey, setPublishStoryKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Revalidate the tab's cached token on every full page load.
  useEffect(() => {
    if (!hasSessionToken()) return;
    let cancelled = false;
    currentUser()
      .then((sessionUser) => { if (!cancelled) setUser(sessionUser); })
      .catch((err: Error) => {
        if (cancelled) return;
        // Invalid/expired token: clear it. Temporary network errors should
        // not silently revoke the client-side token.
        if (/\b(401|403)\b/.test(err.message)) setSessionToken('');
        else setError(`Unable to restore session: ${err.message}`);
      })
      .finally(() => { if (!cancelled) setRestoringSession(false); });
    return () => { cancelled = true; };
  }, []);

  async function refreshProjects() {
    const items = await getProjects(); setProjects(items);
    if (!projectId && items.length) setProjectId(items[0].id);
  }
  async function refreshDocuments(id = projectId) { if (id) setDocuments(await getDocuments(id)); }
  useEffect(() => {
    if (!user) return;
    Promise.all([getHealth(), getSystemInfo(), getProjects()]).then(([h, s, p]) => {
      setHealth(h); setSystem(s); setProjects(p); if (p.length) setProjectId(p[0].id);
    }).catch((err: Error) => setError(err.message));
  }, [user]);
  useEffect(() => {
    if (!projectId || !user) return;
    let cancelled = false;
    setAnalysis(null); setBacklog(null); setDeliverySummary(null); setPreviousBacklogs([]);
    refreshDocuments(projectId).catch((e: Error) => { if (!cancelled) setError(e.message); });
    getBacklogs(projectId).then(async saved => {
      if (cancelled) return;
      setPreviousBacklogs(saved);
      if (!saved.length) return;
      const latest = await getBacklog(projectId, saved[0].id);
      if (!cancelled) setBacklog(latest);
    }).catch(e => { if (!cancelled) setError((e as Error).message); });
    return () => {cancelled = true;};
  }, [projectId,user]);
  useEffect(() => {
    if (!projectId || !backlog?.analysis_id) { setAnalysis(null); return; }
    let cancelled = false;
    getAnalysis(projectId, backlog.analysis_id).then(a => {if (!cancelled) setAnalysis(a);})
      .catch(() => {if (!cancelled) setAnalysis(null);});
    return () => {cancelled = true;};
  }, [projectId,backlog?.analysis_id]);
  useEffect(() => {
    if (!projectId || !backlog?.backlog_id) {setDeliverySummary(null);return;}
    let cancelled = false;
    getDelivery(projectId, backlog.backlog_id).then(d => {if (!cancelled) setDeliverySummary(d);})
      .catch(() => {if (!cancelled) setDeliverySummary(null);});
    return () => {cancelled = true;};
  }, [projectId,backlog?.backlog_id]);
  useEffect(() => { setPublishPreview(null); setPublishStoryKey(""); setPublishRecords([]); }, [projectId, backlog?.backlog_id]);

  async function onCreateProject() {
    setBusy(true); setError(""); setMessage("");
    try { const p = await createProject(projectName, description); await refreshProjects(); setProjectId(p.id); setMessage(`Project created: ${p.name}`); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function onUpload() {
    if (!file || !projectId) return;
    setBusy(true); setError(""); setMessage("");
    try { const result = await uploadDocument(projectId, file); setMessage(`Indexed ${result.filename}: ${result.chunk_count} chunks created.`); setFile(null); await refreshDocuments(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function onAnalyze() {
    if (!projectId) return;
    setBusy(true); setError(""); setMessage("");
    try { const output = await analyzeProject(projectId); setAnalysis(output); setMessage(`Analysis completed using ${output.model}.`); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function onGenerateBacklog() {
    if (!projectId || !analysis?.analysis_id) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const output = await generateBacklog(projectId, analysis.analysis_id);
      setBacklog(await getBacklog(projectId, output.backlog_id));
      setPreviousBacklogs(await getBacklogs(projectId));
      setMessage(`Backlog generated: ${output.epics.length} epics and ${output.stories.length} stories.`);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function onSearch() {
    if (!projectId || !question.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try { setResults(await searchRequirements(projectId, question)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const eligibleStories = backlog?.stories.filter(s => s.approval_status === 'approved' && backlog.story_clearances?.[s.story_key]?.status === 'quality_cleared') ?? [];
  const design = deliverySummary?.artifacts?.design;
  const plan = deliverySummary?.artifacts?.plan;
  const analysisCount = analysis?.requirements?.length ?? backlog?.source_requirement_ids?.length ?? 0;
  const workflowStages = [
    {number:'01', title:'Analyze requirements', anchor:'#requirements-analysis', status:analysis ? 'Analysis loaded' : backlog ? 'Backlog source linked' : 'Awaiting analysis', summary:`${analysisCount} source requirements · ${analysis?.quality_findings?.length ?? 0} findings`, detail:analysis?.requirements.slice(0,6).map(r=>`${r.temporary_id} · ${r.statement}`) ?? (backlog?.source_requirement_ids ?? []).slice(0,6), available:Boolean(analysis || backlog)},
    {number:'02', title:'Generate user stories', anchor:'#story-generation', status:backlog ? 'Backlog loaded' : 'Awaiting backlog', summary:`${backlog?.stories.length ?? 0} stories · ${eligibleStories.length} cleared and approved`, detail:backlog?.stories.slice(0,6).map(s=>`${s.story_key} · ${s.title}`) ?? [], available:Boolean(backlog)},
    {number:'03', title:'Design the solution', anchor:'#delivery-orchestration', status:design?.status ?? 'Awaiting design', summary:design ? `${design.artifact.scope.story_keys.length} stories in design · ${design.artifact.architecture.flow.length} architecture layers` : 'Load a backlog to view saved design', detail:design ? [...design.artifact.architecture.flow, ...((design.artifact.components as {name:string}[]|undefined) ?? []).map(c=>c.name)] : [], available:Boolean(design)},
    {number:'04', title:'Plan delivery', anchor:'#delivery-orchestration', status:plan?.status ?? 'Awaiting plan', summary:plan ? `${plan.artifact.tasks.length} tasks · ${plan.artifact.story_keys.length} stories` : 'Generate a plan after design approval', detail:plan?.artifact.tasks.slice(0,6).map(t=>`${String(t.task_key ?? '')} · ${String(t.title ?? '')} · ${String(t.estimate_story_points ?? 'TBD')} pts`) ?? [], available:Boolean(plan)}
  ];
  if (restoringSession) return <main className="auth-screen"><section className="auth-card" aria-live="polite"><div className="auth-brand"><span className="brand-mark">R</span><div><strong>ReqFlow AI</strong><small>Agentic delivery workspace</small></div></div><h1>Restoring your session</h1><p>Checking your existing sign-in securely…</p></section></main>;
  if (!user) return <main className="auth-screen"><section className="auth-card">
    <div className="auth-brand"><span className="brand-mark">R</span><div><strong>ReqFlow AI</strong><small>Requirements to delivery-ready work</small></div></div>
    <p className="eyebrow">SECURE WORKSPACE</p><h1>Welcome back</h1>
    <p className="auth-description">Sign in to review requirements, user stories, solution designs and implementation plans.</p>
    <form className="auth-form" onSubmit={async e=>{e.preventDefault();setError('');try{const session=await login(loginName,loginPassword);setSessionToken(session.access_token);setUser(session.user);setLoginPassword('');}catch(err){setError((err as Error).message)}}}>
      <label htmlFor="reqflow-username">Username</label><input id="reqflow-username" autoComplete="username" required value={loginName} onChange={e=>setLoginName(e.target.value)} placeholder="Enter your username"/>
      <label htmlFor="reqflow-password">Password</label><input id="reqflow-password" type="password" autoComplete="current-password" required value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} placeholder="Enter your password"/>
      <button type="submit">Sign in to ReqFlow</button>
    </form>{error && <p className="auth-error" role="alert">{error}</p>}
    <p className="auth-footnote">Access is controlled by your organization's ReqFlow administrator.</p>
  </section></main>;
  return <main className="shell">
    <header className="topbar"><div className="brand-mark">R</div><div><div className="brand-name">ReqFlow AI</div><div className="brand-subtitle">Requirements to sprint-ready delivery</div></div><span className="phase-tag">PHASE 7 · CAPSTONE DEMO & EVALUATION</span></header>
    <section className="hero"><p className="eyebrow">AGENTIC SOFTWARE DELIVERY WORKSPACE</p><h1>Turn business requirements into <span>delivery-ready work.</span></h1><p className="intro">Upload a BRD, retrieve evidence and run a LangGraph multi-agent analysis powered by your local Ollama model.</p><div className="status-row"><span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />{health ? "Backend connected" : "Checking backend…"}</div></section>
    <div className="panel"><strong>Signed in:</strong> {user.username} · {user.role} <button onClick={async()=>{try{await logout();}catch{}setSessionToken('');setUser(null);setProjects([]);setProjectId('');setBacklog(null);}}>Sign out</button></div>
    <section className="workflow-overview" aria-label="Project workflow summary">
      <div className="workflow-overview-heading"><div><p className="eyebrow">LIVE PROJECT WORKFLOW</p><h2>From requirements to delivery</h2><p>Select a stage to view the full analysis, stories, solution design or plan below.</p></div><span className="workflow-project">{projects.find(p=>p.id===projectId)?.name ?? 'Select a project'}</span></div>
      <div className="workflow-grid">{workflowStages.map(stage=><article className="workflow-card" key={stage.number}>
        <div className="workflow-card-top"><span className="number">{stage.number}</span><span className={`workflow-status ${stage.available ? 'is-loaded' : ''}`}>{stage.status}</span></div>
        <h3>{stage.title}</h3><p className="workflow-summary">{stage.summary}</p>
        {stage.detail.length ? <ul className="workflow-preview">{stage.detail.map((line,i)=><li key={i}>{line}</li>)}</ul> : <p className="workflow-empty">No saved result loaded for this stage.</p>}
        {stage.number === '01' && analysis && <details className="workflow-expanded"><summary>All extracted requirements ({analysis.requirements.length})</summary><ul>{analysis.requirements.map((r,i)=><li key={i}><strong>{r.temporary_id}</strong> {r.statement}</li>)}</ul></details>}
        {stage.number === '02' && backlog && <details className="workflow-expanded"><summary>All backlog stories ({backlog.stories.length})</summary><ul>{backlog.stories.map(s=><li key={s.story_key}><strong>{s.story_key}</strong> {s.title} — {backlog.story_clearances?.[s.story_key]?.status ?? 'unverified'}</li>)}</ul></details>}
        {stage.number === '03' && design && <details className="workflow-expanded"><summary>Components, APIs and entities</summary>
          <strong>Components</strong><ul>{((design.artifact.components as {name:string;responsibility:string}[]|undefined) ?? []).map((c,i)=><li key={i}>{c.name}: {c.responsibility}</li>)}</ul>
          <strong>Proposed APIs</strong><ul>{((design.artifact.api_proposals as {operation:string;purpose:string}[]|undefined) ?? []).map((a,i)=><li key={i}>{a.operation} — {a.purpose}</li>)}</ul>
          <strong>Data entities</strong><ul>{((design.artifact.data_model_proposals as {entity:string}[]|undefined) ?? []).map((e,i)=><li key={i}>{e.entity}</li>)}</ul>
        </details>}
        {stage.number === '04' && plan && <details className="workflow-expanded"><summary>Tasks, estimates and dependencies</summary><ul>{plan.artifact.tasks.map((t,i)=><li key={i}><strong>{String(t.task_key ?? '')}</strong> {String(t.title ?? '')} · {String(t.estimate_story_points ?? 'TBD')} pts · Depends on: {Array.isArray(t.depends_on) && t.depends_on.length ? t.depends_on.join(', ') : 'none'}</li>)}</ul></details>}
        <a className="workflow-link" href={stage.anchor}>View full section ↓</a>
      </article>)}</div>
    </section>
    <section className="workspace">
      <div className="panel project-panel"><p className="eyebrow">01 · PROJECT</p><h2>Create a project</h2><p className="panel-description">Create a new workspace or switch to an existing project.</p><label>Project name<input value={projectName} onChange={e => setProjectName(e.target.value)} /></label><label>Description<input value={description} onChange={e => setDescription(e.target.value)} /></label><button disabled={busy || projectName.trim().length < 2} onClick={onCreateProject}>Create project</button><label className="project-select">Active project<select value={projectId} onChange={e => setProjectId(e.target.value)}><option value="">Select a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div>
      <div className="panel ingestion-panel"><p className="eyebrow">02 · INGESTION</p><h2>Upload requirements</h2><p>Supported: PDF, DOCX, Markdown, TXT · Maximum 15 MB</p><input className="file-input" type="file" accept=".pdf,.docx,.md,.txt" onChange={e => setFile(e.target.files?.[0] ?? null)} /><button disabled={busy || !file || !projectId} onClick={onUpload}>Upload and index document</button><div className="doc-list"><strong>Indexed documents</strong><span className="doc-count">{documents.length} indexed</span>{documents.length ? documents.map(d => <div className="doc-row" key={d.id}><span>{d.filename}</span><small>{d.processing_status} · {d.chunk_count} chunks</small></div>) : <p>No documents indexed for this project yet.</p>}</div></div>
      <div className="panel search-panel"><p className="eyebrow">03 · SEMANTIC RETRIEVAL</p><h2>Ask the requirements</h2><p className="panel-description">Find supporting passages in the indexed BRD before generating stories.</p><label>Question<textarea value={question} onChange={e => setQuestion(e.target.value)} rows={3} /></label><button disabled={busy || !projectId || !documents.length} onClick={onSearch}>Search indexed content</button>{results && <div className="results"><strong>{results.results.length} matching passages</strong>{results.results.map((r, i) => <article className="result-card" key={`${r.document_id}-${r.chunk_index}`}><div className="result-meta">{i + 1}. {r.filename} · Chunk {r.chunk_index} · Similarity {r.similarity}</div><p>{r.content}</p></article>)}</div>}</div>
      <div id="requirements-analysis" className="panel analysis-panel">
        <p className="eyebrow">04 · AGENTIC REQUIREMENTS ANALYSIS</p><h2>Analyze the BRD</h2>
        <p>Runs retrieval, extraction, classification, quality analysis and evidence validation through LangGraph agents using Ollama.</p>
        <button disabled={busy || !projectId || !documents.length} onClick={onAnalyze}>Run requirements analysis</button>
        {analysis && <div className="results">
          <strong>{analysis.requirements.length} requirements · {analysis.quality_findings.length} quality findings · {analysis.open_questions.length} open questions</strong>
          <p className="result-meta">Analysis {analysis.analysis_id} · Model {analysis.model}</p>
          {analysis.requirements.map((r, i) => <article className="result-card" key={`${r.temporary_id}-${i}`}>
            <div className="result-meta">{r.temporary_id} · {r.requirement_type || "type needs review"} · Priority: {r.priority ?? "undetermined"} · Evidence: {analysis.validation.requirements?.find(v => v.temporary_id === r.temporary_id)?.evidence_status ?? "not checked"}</div>
            <p><strong>{r.statement || "Requirement description missing — review this item before proceeding."}</strong></p>
            {r.source_refs?.map((source, j) => <small key={j}>{source.filename} · Chunk {source.chunk_index}: “{source.quote}”</small>)}
          </article>)}
          {analysis.quality_findings.map((f, i) => <article className="result-card" key={`finding-${i}`}>
            <div className="result-meta">{f.issue_type} · {f.severity}</div><p>{f.description}</p>{f.question_to_resolve && <small>Question: {f.question_to_resolve}</small>}
          </article>)}
          {!!analysis.open_questions.length && <div className="result-card"><strong>Open questions</strong>{analysis.open_questions.map((q, i) => <p key={i}>{typeof q === "string" ? q : q.question ?? JSON.stringify(q)}</p>)}</div>}
          {analysis.validation.overall_summary && <p>{analysis.validation.overall_summary}</p>}
        </div>}
      </div>
      <div id="story-generation" className="panel backlog-panel">
        <p className="eyebrow">05 · AGENTIC BACKLOG GENERATION</p><h2>Generate epics and user stories</h2>
        <p>Uses only evidence-supported requirements from the latest Phase 3 analysis. Priorities and estimates are AI recommendations pending team approval.</p>
        <button disabled={busy || !projectId || !analysis?.analysis_id || !analysis.requirements.some(r => analysis.validation.requirements?.some(v => v.temporary_id === r.temporary_id && v.evidence_status === "supported"))} onClick={onGenerateBacklog}>Generate sprint-ready backlog</button>
        {!analysis && <small>Run Phase 3 requirements analysis first, or load a previous backlog.</small>}
        <button disabled={busy || !projectId} onClick={async () => { try { setPreviousBacklogs(await getBacklogs(projectId)); } catch(e) { setError((e as Error).message); } }}>List saved backlogs</button>
        {previousBacklogs.length > 0 && <select defaultValue="" onChange={async e => { if (e.target.value) { try { setBacklog(await getBacklog(projectId, e.target.value)); } catch(err) { setError((err as Error).message); } } }}><option value="">Load a saved backlog</option>{previousBacklogs.map(b => <option key={b.id} value={b.id}>{b.created_at} · {b.id.slice(0, 8)}</option>)}</select>}
        {backlog && <div className="results">
          <strong>{backlog.epics.length} epics · {backlog.stories.length} stories · {backlog.acceptance_criteria.length} acceptance criteria</strong>
          <p className="result-meta">Backlog {backlog.backlog_id} · Model {backlog.model}</p>
          {backlog.repair_of_backlog_id && <p><strong>Repair version {backlog.repair_version}</strong> · Source backlog {backlog.repair_of_backlog_id} · Blocking findings {backlog.repair_audit?.before_blocking_findings} → {backlog.repair_audit?.after_blocking_findings}</p>}
          <button disabled={busy || backlog.validation.ready_for_approval} onClick={async () => {
            setBusy(true); setError(""); setMessage("");
            try {
              const repaired = await repairBacklog(projectId, backlog.backlog_id);
              setBacklog(await getBacklog(projectId, repaired.backlog_id));
              setPreviousBacklogs(await getBacklogs(projectId));
              setMessage(`Saved repair version ${repaired.repair_version}. Original backlog preserved.`);
            } catch (err) { setError((err as Error).message); }
            finally { setBusy(false); }
          }}>Repair flagged stories (Ollama) · Save new version</button>
          <p><strong>Quality gate:</strong> {backlog.validation.ready_for_approval ? "No high/critical findings (human review still required)" : "Review required — high/critical findings"} · Coverage: {backlog.validation.coverage?.covered ?? "?"}/{backlog.validation.coverage?.total ?? "?"}</p>
          {backlog.epics.map(epic => <section className="epic-card" key={epic.epic_key}>
            <div className="result-meta">{epic.epic_key} · Requirements: {epic.source_requirement_ids.join(", ")}</div>
            <h3>{epic.title}</h3><p>{epic.description}</p>
            {backlog.stories.filter(story => story.epic_key === epic.epic_key).map(story => <article className="result-card story-card" key={story.story_key}>
              <div className="result-meta">{story.story_key} · {story.priority_recommendation.toUpperCase()} (AI recommendation) · {story.story_points ?? "Estimate pending"} points · Approval: {story.approval_status ?? "pending"}</div>
              <h4>{story.title}</h4><p><strong>{story.story_text}</strong></p>
              <small>Traces to: {story.source_requirement_ids.join(", ")}</small>
              <p><strong>Quality clearance:</strong> {backlog.story_clearances?.[story.story_key]?.status === "quality_cleared" ? "Quality cleared" : backlog.story_clearances?.[story.story_key]?.status === "review_required" ? "Review required (assumptions)" : "Blocked / clearance unavailable"}</p>
              {backlog.story_clearances?.[story.story_key]?.reasons.map((reason, i) => <small key={i}>Quality note: {reason}</small>)}
              <label>Product-owner review <select value={story.approval_status ?? "pending"} onChange={async e => { try { await setStoryApproval(projectId, backlog.backlog_id, story.story_key, e.target.value); setBacklog(await getBacklog(projectId, backlog.backlog_id)); } catch(err) { setError((err as Error).message); } }}><option value="pending">Pending</option><option value="approved" disabled={!(["admin","product_owner"].includes(user.role)) || backlog.story_clearances?.[story.story_key]?.status !== "quality_cleared"}>Approved (requires quality clearance)</option><option value="needs_revision">Needs revision</option><option value="rejected">Rejected</option></select></label>
              <div className="criteria"><strong>Acceptance criteria</strong>{backlog.acceptance_criteria.filter(c => c.story_key === story.story_key).map(c => <p key={c.criterion_key}><small>{c.criterion_key} · {c.test_type}</small><br/>{c.criterion_text}</p>)}</div>
              {story.assumptions.length > 0 && <small>Review assumptions: {story.assumptions.join("; ")}</small>}
            </article>)}
          </section>)}
          <Phase61Clarifications projectId={projectId} backlog={backlog} user={user} onBacklog={async (newId:string)=>{setBacklog(await getBacklog(projectId,newId));setPreviousBacklogs(await getBacklogs(projectId));}} />
          {!!backlog.dependencies.length && <div className="result-card"><strong>Dependencies</strong>{backlog.dependencies.map((d, i) => <p key={i}>{d.story_key} {d.dependency_type} {d.depends_on_story_key}: {d.rationale}</p>)}</div>}
          {!!backlog.validation.issues.length && <div className="result-card"><strong>Quality review items</strong>{backlog.validation.issues.map((issue, i) => <p key={i}><small>{issue.story_key} · {issue.severity} · {issue.issue_type}</small><br/>{issue.description} — {issue.recommendation}</p>)}</div>}
          <p>{backlog.validation.summary}</p>
          <div className="result-card">
            <h3>06 · Jira / GitHub publishing (MCP)</h3>
            <p>Preview any quality-cleared story, even while product-owner approval is pending. Live publishing requires both clearance and approval. Preview performs no external write. Live publishing is disabled in the backend by default.</p>
            <label>Provider <select value={publishProvider} onChange={e => {setPublishProvider(e.target.value);setPublishPreview(null);}}><option value="github">GitHub Issues</option><option value="jira">Jira Cloud Tasks</option></select></label>
            <label>Quality-cleared story <select value={publishStoryKey} onChange={e => {setPublishStoryKey(e.target.value);setPublishPreview(null);}}><option value="">Select quality-cleared story</option>{backlog.stories.filter(story => backlog.story_clearances?.[story.story_key]?.status === "quality_cleared").map(story => <option key={story.story_key} value={story.story_key}>{story.story_key} · {story.title}</option>)}</select></label>
            <button disabled={busy || !publishStoryKey} onClick={async () => {setBusy(true);setError("");try{setPublishPreview(await previewPublication(projectId,backlog.backlog_id,publishStoryKey,publishProvider));}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}>Preview (dry-run, no remote writes)</button>
            {publishPreview && <div className="result-card"><strong>Preview: {publishPreview.provider} · {publishPreview.target}</strong><p>Quality: {publishPreview.quality_status} · Product-owner approval: {publishPreview.approval_status}. Preview does not publish.</p><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{publishPreview.body}</pre><button disabled={busy || !(["admin","product_owner"].includes(user.role)) || backlog.stories.find(s => s.story_key === publishStoryKey)?.approval_status !== "approved"} onClick={async () => {
              if (!window.confirm(`Publish ${publishStoryKey} to ${publishProvider}? This will create a real external issue.`)) return;
              const key = window.prompt("Enter the Phase 5 publishing key (not saved in browser)");if(!key)return;
              setBusy(true);setError("");try{const result=await publishApprovedStory(projectId,backlog.backlog_id,publishStoryKey,publishProvider,key);setMessage(`Published: ${result.external_url}`);setPublishPreview(null);setPublishRecords(await getPublications(projectId,backlog.backlog_id));}catch(e){setError((e as Error).message)}finally{setBusy(false)}
            }}>Publish approved story (live)</button></div>}
            <button disabled={busy} onClick={async () => {try{setPublishRecords(await getPublications(projectId,backlog.backlog_id));}catch(e){setError((e as Error).message)}}}>Refresh publication history</button>
            {publishRecords.map((r,i) => <p key={i}><small>{r.story_key} · {r.provider} · {r.state}</small> {r.external_url && <a href={r.external_url} target="_blank" rel="noreferrer">View external issue</a>} {r.error_note && <small>{r.error_note}</small>}</p>)}
          </div>
          <div className="result-card"><h3>Phase 6 · Golden-set evaluation</h3>
            <p>Enter human-verified expected requirement IDs (comma-separated). Coverage metrics do not verify semantic correctness.</p>
            <textarea rows={2} value={evaluationGold} onChange={e=>setEvaluationGold(e.target.value)}/>
            <button disabled={busy || !(["admin","engineer","product_owner"].includes(user.role))} onClick={async()=>{
              setBusy(true);setError('');try{const r=await evaluateBacklog(projectId,backlog.backlog_id,evaluationGold.split(',').map(x=>x.trim()).filter(Boolean));setEvaluationOutput(r.metrics)}catch(e){setError((e as Error).message)}finally{setBusy(false)}
            }}>Evaluate against gold IDs</button>{evaluationOutput&&<pre>{JSON.stringify(evaluationOutput,null,2)}</pre>}
          </div>
          <Phase7Readiness backlog={backlog} />
          <div id="delivery-orchestration"><Phase7Delivery projectId={projectId} backlogId={backlog.backlog_id} role={user.role} onChanged={async()=>{setDeliverySummary(await getDelivery(projectId,backlog.backlog_id));}} /></div>
          <button onClick={() => {
            const csv = ["story_key,epic_key,title,story_text,priority_recommendation,story_points,approval_status,source_requirement_ids", ...backlog.stories.map(s => [s.story_key,s.epic_key,s.title,s.story_text,s.priority_recommendation,s.story_points ?? "",s.approval_status ?? "pending",s.source_requirement_ids.join(";")].map(v => `"${String(v).replace(/"/g, '""')}"`).join(","))].join("\r\n");
            const blob = new Blob([csv], {type: "text/csv;charset=utf-8"});
            const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `reqflow-backlog-${backlog.backlog_id}.csv`; a.click(); URL.revokeObjectURL(url);
          }}>Export backlog CSV</button>
          <button onClick={() => {
            const blob = new Blob([JSON.stringify(backlog, null, 2)], {type: "application/json"});
            const url = URL.createObjectURL(blob); const a = document.createElement("a");
            a.href = url; a.download = `reqflow-backlog-${backlog.backlog_id}.json`; a.click(); URL.revokeObjectURL(url);
          }}>Export backlog JSON</button>
        </div>}
      </div>
      {(message || error) && <div className={`notice ${error ? "error" : "success"}`}>{error || message}</div>}
    </section>
    <section className="system-panel"><div><p className="eyebrow">FOUNDATION SERVICES</p><h2>Development environment</h2></div><pre>{JSON.stringify(system ?? {loading: true}, null, 2)}</pre></section>
    <footer>ReqFlow AI · Agentic AI Capstone · Phase 7 demo & release evidence · Existing quality gates preserved</footer>
  </main>;
}
