# Live Deployment

## Local Deployment
To run the full-stack live application:
```bash
docker compose up --build -d
```

Then seed the database with initial nodes and tasks:
```bash
docker compose exec backend python web/backend/seed.py
```

### URLs
- **Frontend Dashboard**: `http://localhost:8080`
- **Backend API**: `http://localhost:8000/api/health`

## Important Note
The offline scientific dashboard (`dashboard.html`) and the live application database are separate. 
The live application uses the backend API (`web/backend/main.py`), which persists data to PostgreSQL, and invokes the frozen `mechanisms/edgetruth.py` directly for allocations.
