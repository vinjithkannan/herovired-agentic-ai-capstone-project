import { useEffect, useState } from "react";
import { createProject, getDocuments, getHealth, getProjects, getSystemInfo, searchRequirements, uploadDocument, analyzeProject, type AnalysisResult, type DocRecord, type Project, type SearchResult } from "./services/api";

export default function App() {
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
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refreshProjects() {
    const items = await getProjects(); setProjects(items);
    if (!projectId && items.length) setProjectId(items[0].id);
  }
  async function refreshDocuments(id = projectId) { if (id) setDocuments(await getDocuments(id)); }
  useEffect(() => {
    Promise.all([getHealth(), getSystemInfo(), getProjects()]).then(([h, s, p]) => {
      setHealth(h); setSystem(s); setProjects(p); if (p.length) setProjectId(p[0].id);
    }).catch((err: Error) => setError(err.message));
  }, []);
  useEffect(() => { if (projectId) refreshDocuments(projectId).catch((e: Error) => setError(e.message)); }, [projectId]);

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

  async function onSearch() {
    if (!projectId || !question.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try { setResults(await searchRequirements(projectId, question)); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  const cards = [
    ["01", "Analyze requirements", "Extract functional and non-functional requirements and identify gaps."],
    ["02", "Generate user stories", "Create epics, stories and Given-When-Then acceptance criteria."],
    ["03", "Design the solution", "Produce architecture, API and data design recommendations."],
    ["04", "Plan delivery", "Break stories into development and testing tasks with estimates."]
  ];
  return <main className="shell">
    <header className="topbar"><div className="brand-mark">R</div><div><div className="brand-name">ReqFlow AI</div><div className="brand-subtitle">Requirements to sprint-ready delivery</div></div><span className="phase-tag">PHASE 3 · REQUIREMENTS ANALYSIS</span></header>
    <section className="hero"><p className="eyebrow">AGENTIC SOFTWARE DELIVERY WORKSPACE</p><h1>Turn business requirements into <span>delivery-ready work.</span></h1><p className="intro">Upload a BRD, retrieve evidence and run a LangGraph multi-agent analysis powered by your local Ollama model.</p><div className="status-row"><span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />{health ? "Backend connected" : "Checking backend…"}</div></section>
    <section className="workspace">
      <div className="panel"><p className="eyebrow">01 · PROJECT</p><h2>Create a project</h2><label>Project name<input value={projectName} onChange={e => setProjectName(e.target.value)} /></label><label>Description<input value={description} onChange={e => setDescription(e.target.value)} /></label><button disabled={busy || projectName.trim().length < 2} onClick={onCreateProject}>Create project</button><label className="project-select">Active project<select value={projectId} onChange={e => setProjectId(e.target.value)}><option value="">Select a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div>
      <div className="panel"><p className="eyebrow">02 · INGESTION</p><h2>Upload requirements</h2><p>Supported: PDF, DOCX, Markdown, TXT · Maximum 15 MB</p><input className="file-input" type="file" accept=".pdf,.docx,.md,.txt" onChange={e => setFile(e.target.files?.[0] ?? null)} /><button disabled={busy || !file || !projectId} onClick={onUpload}>Upload and index document</button><div className="doc-list"><strong>Indexed documents</strong>{documents.length ? documents.map(d => <div className="doc-row" key={d.id}><span>{d.filename}</span><small>{d.processing_status} · {d.chunk_count} chunks</small></div>) : <p>No documents indexed for this project yet.</p>}</div></div>
      <div className="panel search-panel"><p className="eyebrow">03 · SEMANTIC RETRIEVAL</p><h2>Ask the requirements</h2><label>Question<textarea value={question} onChange={e => setQuestion(e.target.value)} rows={3} /></label><button disabled={busy || !projectId || !documents.length} onClick={onSearch}>Search indexed content</button>{results && <div className="results"><strong>{results.results.length} matching passages</strong>{results.results.map((r, i) => <article className="result-card" key={`${r.document_id}-${r.chunk_index}`}><div className="result-meta">{i + 1}. {r.filename} · Chunk {r.chunk_index} · Similarity {r.similarity}</div><p>{r.content}</p></article>)}</div>}</div>
      <div className="panel analysis-panel">
        <p className="eyebrow">04 · AGENTIC REQUIREMENTS ANALYSIS</p><h2>Analyze the BRD</h2>
        <p>Runs retrieval, extraction, classification, quality analysis and evidence validation through LangGraph agents using Ollama.</p>
        <button disabled={busy || !projectId || !documents.length} onClick={onAnalyze}>Run requirements analysis</button>
        {analysis && <div className="results">
          <strong>{analysis.requirements.length} requirements · {analysis.quality_findings.length} quality findings · {analysis.open_questions.length} open questions</strong>
          <p className="result-meta">Analysis {analysis.analysis_id} · Model {analysis.model}</p>
          {analysis.requirements.map((r, i) => <article className="result-card" key={`${r.temporary_id}-${i}`}>
            <div className="result-meta">{r.temporary_id} · {r.requirement_type} · Priority: {r.priority ?? "undetermined"} · Evidence: {analysis.validation.requirements?.find(v => v.temporary_id === r.temporary_id)?.evidence_status ?? "not checked"}</div>
            <p><strong>{r.statement}</strong></p>
            {r.source_refs?.map((source, j) => <small key={j}>{source.filename} · Chunk {source.chunk_index}: “{source.quote}”</small>)}
          </article>)}
          {analysis.quality_findings.map((f, i) => <article className="result-card" key={`finding-${i}`}>
            <div className="result-meta">{f.issue_type} · {f.severity}</div><p>{f.description}</p>{f.question_to_resolve && <small>Question: {f.question_to_resolve}</small>}
          </article>)}
          {!!analysis.open_questions.length && <div className="result-card"><strong>Open questions</strong>{analysis.open_questions.map((q, i) => <p key={i}>{typeof q === "string" ? q : q.question ?? JSON.stringify(q)}</p>)}</div>}
          {analysis.validation.overall_summary && <p>{analysis.validation.overall_summary}</p>}
        </div>}
      </div>
      {(message || error) && <div className={`notice ${error ? "error" : "success"}`}>{error || message}</div>}
    </section>
    <section className="grid">{cards.map(([n, title, description]) => <article className="feature-card" key={n}><span className="number">{n}</span><h2>{title}</h2><p>{description}</p><span className="coming-soon">NEXT IMPLEMENTATION PHASES</span></article>)}</section>
    <section className="system-panel"><div><p className="eyebrow">FOUNDATION SERVICES</p><h2>Development environment</h2></div><pre>{JSON.stringify(system ?? {loading: true}, null, 2)}</pre></section>
    <footer>ReqFlow AI · Agentic AI Capstone · Phase 3 LangGraph requirements analysis</footer>
  </main>;
}
