# Phase 3 test cases

| ID | Test | Expected result |
|---|---|---|
| P3-01 | Analyze a project with an indexed BRD | 201 response with analysis ID and source passages |
| P3-02 | Analyze a project with no indexed chunks | 400 with an actionable message |
| P3-03 | Use an unknown project UUID | 404 project not found |
| P3-04 | Stop Ollama and run analysis | 503 with Ollama connectivity guidance |
| P3-05 | Inspect extracted requirements | Each requirement includes source filename, chunk index and supporting quote |
| P3-06 | Review unsupported BRD capability (e.g. alerts) | It is not invented as an existing requirement; it may be raised as an open question only when justified |
| P3-07 | List prior analysis runs | Persisted run metadata is returned |
| P3-08 | Restart Compose services | Database, documents and pulled Ollama model remain available |
