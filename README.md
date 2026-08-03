# Fantasy Football Draft App - Base Scaffold

Bare-bones project: React frontend talking to a FastAPI backend. No database yet -
that's the next step once this is confirmed running end-to-end.

## Structure
```
ff-draft-base/
  backend/
    app/
      main.py       FastAPI app, CORS, health check
    requirements.txt
  frontend/
    src/
      main.jsx
      App.jsx        fetches /health from the backend to confirm connectivity
    package.json
    vite.config.js
```

## Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

Open the frontend - it should show "Backend status: ok", confirming the two sides
can talk to each other.

## Next step
Add the database layer (SQLAlchemy models, players table, draft state) once this
base is confirmed working.
