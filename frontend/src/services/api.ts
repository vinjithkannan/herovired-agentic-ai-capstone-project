const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
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
