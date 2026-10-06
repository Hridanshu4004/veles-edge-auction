# Full-Stack Live Architecture

```
Browser
  ↓ HTTP/JSON
Frontend (Static HTML/JS)
  ↓ REST API (http://localhost:8000/api)
Backend (FastAPI)
  ↓ Python Import
EdgeTruth (mechanisms/edgetruth.py)
  ↓ SQL
PostgreSQL (Database)
  ↓
Backend
  ↓
Frontend
```

## Feedback Loop
```
Task execution
  ↓
Observed outcome (POST /api/executions)
  ↓
Reliability evidence (Persisted in DB)
  ↓
Next auction (Evidence loaded from DB -> EdgeTruth -> Score)
```
