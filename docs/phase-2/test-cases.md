# Phase 2 test checklist

- [ ] `GET /health` returns `{"status":"ok","service":"reqflow-api"}`.
- [ ] Migration creates `document_chunks` and HNSW index.
- [ ] Create project returns UUID.
- [ ] List projects includes the created project.
- [ ] Upload sample Markdown returns `completed` and a positive chunk count.
- [ ] List documents reports the same file and chunk count.
- [ ] RAG search returns ranked chunks and source filenames.
- [ ] Unsupported `.exe` or `.zip` upload returns HTTP 415.
- [ ] Upload without an API key returns HTTP 503 with configuration guidance.
- [ ] Uploading a scanned PDF returns a clear no-extractable-text error.
