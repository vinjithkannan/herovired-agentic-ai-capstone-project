// Keep the bearer token for this browser tab only. The backend remains the
// authority for expiry and revocation; never treat this cache as authentication.
const SESSION_KEY = 'reqflow.session.access_token';
let accessToken = (() => {
  try { return sessionStorage.getItem(SESSION_KEY) ?? ''; }
  catch { return ''; }
})();
export function hasSessionToken(): boolean { return Boolean(accessToken); }
export function setSessionToken(token: string) {
  accessToken = token;
  try {
    if (token) sessionStorage.setItem(SESSION_KEY, token);
    else sessionStorage.removeItem(SESSION_KEY);
  } catch { /* Browser storage may be disabled; keep in-memory fallback. */ }
}
export type SessionUser={id:string;username:string;role:'admin'|'product_owner'|'engineer'|'viewer'};
export const login = (username:string,password:string) => request<{access_token:string;user:SessionUser;expires_at:string}>('/api/v1/auth/login',{
  method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})
});
export const logout=()=>request<{revoked:boolean}>('/api/v1/auth/logout',{method:'POST'});
export const currentUser=()=>request<SessionUser>('/api/v1/auth/me');
export const getMetrics=()=>request<Record<string,unknown>>('/api/v1/operations/metrics');
export const getEvaluations=(projectId:string,backlogId:string)=>request<Array<{id:string;metrics:Record<string,unknown>}>>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/evaluations`);
export const evaluateBacklog=(projectId:string,backlogId:string,expected_requirement_ids:string[])=>request<{evaluation_id:string;metrics:Record<string,unknown>}>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/evaluate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_requirement_ids})});

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers=new Headers(init?.headers ?? {});
  if (accessToken) headers.set('Authorization',`Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE}${path}`, {...init,headers});
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `API returned ${response.status}`);
  }
  return response.json();
}

export const getHealth = () => request<{status: string; service: string}>("/health");
export const getSystemInfo = () => request<Record<string, unknown>>("/api/v1/system/info");
export const getProjects = () => request<Project[]>("/api/v1/projects");
export const createProject = (name: string, description: string) => request<Project>("/api/v1/projects", {
  method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({name, description})
});
export const getDocuments = (projectId: string) => request<DocRecord[]>(`/api/v1/projects/${projectId}/documents`);
export async function uploadDocument(projectId: string, file: File) {
  const form = new FormData(); form.append("file", file);
  return request<UploadResult>(`/api/v1/projects/${projectId}/documents`, {method: "POST", body: form});
}
export const searchRequirements = (project_id: string, question: string) => request<SearchResult>("/api/v1/rag/search", {
  method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({project_id, question, top_k: 5})
});

export type Project = {id: string; name: string; description?: string; status: string};
export type DocRecord = {id: string; filename: string; processing_status: string; chunk_count: number; created_at: string};
export type UploadResult = {id: string; filename: string; processing_status: string; character_count: number; chunk_count: number};
export type SearchResult = {question: string; results: {document_id: string; filename: string; chunk_index: number; content: string; similarity: number}[]};

export const getAnalysis = (projectId:string, analysisId:string) => request<AnalysisResult>(`/api/v1/projects/${projectId}/analyses/${analysisId}`);
export const analyzeProject = (project_id: string, question?: string) => request<AnalysisResult>(`/api/v1/projects/${project_id}/analyze`, {
  method: "POST", headers: {"Content-Type": "application/json"},
  body: JSON.stringify({question: question || null, top_k: 12})
});

export type AnalysisResult = {
  analysis_id: string; model: string;
  requirements: {temporary_id: string; statement: string; requirement_type: string; priority?: string; category?: string; ambiguity?: string; testability?: string; source_refs?: {filename: string; chunk_index: number; quote: string}[]}[];
  quality_findings: {issue_type: string; severity: string; description: string; question_to_resolve?: string; related_requirement_ids?: string[]}[];
  open_questions: (string | {question?: string; rationale?: string})[];
  validation: {requirements?: {temporary_id: string; evidence_status: string; validation_note?: string}[]; overall_summary?: string};
  source_passages: {filename: string; chunk_index: number; similarity: number}[];
};


export type BacklogResult = {
  backlog_id: string;
  story_clearances?: Record<string, {status: "quality_cleared" | "review_required" | "blocked"; reasons: string[]; blocking_findings: number; review_findings: number}>;
  repair_of_backlog_id?: string;
  repair_version?: number;
  repair_audit?: {changed_story_keys: string[]; preserved_story_keys: string[]; before_blocking_findings: number; after_blocking_findings: number; notes: string[]};
  analysis_id: string;
  model: string;
  epics: {epic_key: string; title: string; description: string; business_value?: string; source_requirement_ids: string[]}[];
  stories: {story_key: string; epic_key: string; title: string; story_text: string; description: string; source_requirement_ids: string[]; priority_recommendation: string; priority_rationale: string; story_points: number | null; estimate_rationale: string; assumptions: string[]; approval_status?: string}[];
  acceptance_criteria: {story_key: string; criterion_key: string; criterion_text: string; test_type: string}[];
  dependencies: {story_key: string; depends_on_story_key: string; dependency_type: string; rationale: string}[];
  validation: {issues: {story_key: string; severity: string; issue_type: string; description: string; recommendation: string}[]; summary: string; approval_blocked_story_keys?: string[]; ready_for_approval?: boolean; quality_gate_version?: string; coverage?: {covered:number;total:number;missing_requirement_ids:string[]}};
  source_requirement_ids: string[];
  open_questions: (string | {question?: string; description?: string})[];
};
export const generateBacklog = (projectId: string, analysisId: string) => request<BacklogResult>(`/api/v1/projects/${projectId}/backlogs/generate`, {
  method: "POST", headers: {"Content-Type": "application/json"},
  body: JSON.stringify({analysis_id: analysisId, include_partial_evidence: false})
});
export const getBacklogs = (projectId: string) => request<{id: string; analysis_id: string; model: string; status: string; created_at: string}[]>(`/api/v1/projects/${projectId}/backlogs`);

export const getBacklog = (projectId: string, backlogId: string) => request<BacklogResult>(`/api/v1/projects/${projectId}/backlogs/${backlogId}`);
export const setStoryApproval = (projectId: string, backlogId: string, storyKey: string, status: string) => request<{story_key: string; approval_status: string}>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/stories/${storyKey}/approval`, {
  method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({status})
});

export const repairBacklog = (projectId: string, backlogId: string, useOllama = true) => request<BacklogResult>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/repair`, {
  method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({use_ollama: useOllama})
});


// Phase 5: dry run is default; server separately enforces live publishing gate.
export type PublishPreview = {mode: string; eligible: boolean; provider: string; target: string; story_key: string; title: string; body: string; writes_performed: boolean; approval_status?: string; quality_status?: string};
export type PublishRecord = {story_key: string; provider: string; target: string; state: string; external_id?: string; external_url?: string; created_at: string; error_note?: string};
export const previewPublication = (projectId: string, backlogId: string, storyKey: string, provider: string) => request<PublishPreview>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/publish`, {
  method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({provider, story_key: storyKey, dry_run: true})
});
export const publishApprovedStory = (projectId: string, backlogId: string, storyKey: string, provider: string, publishKey: string) => request<{state: string; external_url: string}>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/publish`, {
  method: "POST", headers: {"Content-Type": "application/json", "X-Reqflow-Publish-Key": publishKey}, body: JSON.stringify({provider, story_key: storyKey, dry_run: false})
});
export const getPublications = (projectId: string, backlogId: string) => request<PublishRecord[]>(`/api/v1/projects/${projectId}/backlogs/${backlogId}/publications`);

// Phase 6.1 clarification decisions are separate from story approval.
export type Clarification = {id:string;story_key:string;proposal:{title:string;story_text:string;rationale:string;acceptance_criteria:{criterion_text:string;test_type:string}[]};status:'proposed'|'approved'|'rejected'|'superseded';decision_note?:string};
const clarificationPath=(p:string,b:string)=>`/api/v1/projects/${p}/backlogs/${b}/clarifications`;
export const listClarifications=(p:string,b:string)=>request<Clarification[]>(clarificationPath(p,b));
export const proposeClarification=(p:string,b:string,key:string,proposal:Clarification['proposal'])=>request<{id:string;status:string}>(`/api/v1/projects/${p}/backlogs/${b}/stories/${encodeURIComponent(key)}/clarifications`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(proposal)});
export const decideClarification=(p:string,b:string,id:string,approve:boolean,note:string)=>request<{status:string}>(`${clarificationPath(p,b)}/${id}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve,note})});
export const finalizeClarifications=(p:string,b:string)=>request<{backlog_id:string;quality_status:string;approved_clarifications:number}>(`${clarificationPath(p,b)}/finalize`,{method:'POST'});

export const supersedeClarification=(p:string,b:string,id:string,note:string)=>request<{status:string}>(`${clarificationPath(p,b)}/${id}/supersede`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve:false,note})});

export const previewClarificationQuality=(p:string,b:string)=>request<{approved_clarifications:number;quality_cleared:number;total_stories:number;ready_to_finalize:boolean;story_clearances:Record<string,{status:string;reasons:string[]}>;validation:{issues:{story_key:string;severity:string;description:string}[]}}>(`${clarificationPath(p,b)}/quality-preview`);

// Phase 7 scope completion: persisted design and planning artifacts.
export type DeliveryArtifacts={
  project_id:string;backlog_id:string;
  artifacts:{
    design?:{status:string;artifact:{title:string;scope:{story_keys:string[];requirement_ids:string[]};architecture:{flow:string[]};[key:string]:unknown}};
    plan?:{status:string;artifact:{story_keys:string[];tasks:Record<string,unknown>[];[key:string]:unknown}}
  }
};
const deliveryPath=(p:string,b:string)=>`/api/v1/projects/${p}/backlogs/${b}/delivery`;
export const getDelivery=(p:string,b:string)=>request<DeliveryArtifacts>(deliveryPath(p,b));
export const generateDeliveryDesign=(p:string,b:string)=>request<unknown>(`${deliveryPath(p,b)}/design`,{method:'POST'});
export const generateDeliveryPlan=(p:string,b:string)=>request<unknown>(`${deliveryPath(p,b)}/plan`,{method:'POST'});
export const decideDeliveryDesign=(p:string,b:string,approve:boolean,note:string)=>request<unknown>(`${deliveryPath(p,b)}/design/approval`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve,note})});
export const decideDeliveryPlan=(p:string,b:string,approve:boolean,note:string)=>request<unknown>(`${deliveryPath(p,b)}/plan/approval`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approve,note})});
