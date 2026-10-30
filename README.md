# Neo Project Flow

A simple web system that runs the **Neo Project Management Flow Chart (AD001-F01-00)** from the first idea to final
dispatch: who is responsible, what is waiting, approvals, loops, files and notes – in one place.

Stack: **FastAPI** + **SQLite** (backend) · **Vite + React** (frontend).

## Run it

Windows: double-click **`start.bat`** (first start installs, builds the screens and loads demo data, about 30 seconds), then open
<http://localhost:8090>.

Manual:

```
cd frontend && npm install && npm run build
cd ../backend && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8090
```

Development with hot reload: run the backend as above, then `cd frontend && NEO_API=http://127.0.0.1:8090 npm run dev`.

Data lives in `backend/data/` (SQLite file + uploaded files). Delete that folder to reset to fresh demo data.
Set `NEO_AUTOSEED=0` to start empty (then create the first Office Admin yourself in the database).

## Demo sign-in

The sign-in page lists all demo people; click one. Password for all: `neo@123`.

| Person | Role | Reports to |
|---|---|---|
| Rajiv Khanna | Director – Neo Health OTC | – |
| Suresh Iyer | Director – Neo India Lifeline | – |
| Ananya Reddy, Rohit Malhotra | Project Initiator | Rajiv |
| Meera Joshi, Karthik Subramanian | Cross-Functional Team | Suresh |
| Pooja Bansal / Amit Deshmukh / Dr. Neha Kapoor | Legal / Quality / PV | Suresh |
| Dr. Sanjay Patel → Divya Menon, Harsh Vora | Regulatory Head → Regulatory Team | Suresh → Sanjay |
| Ritika Sen, Manish Pillai | Artwork Team | Rajiv |
| Arjun Bhatia, Sakshi Agarwal | Commercial Team | Rajiv |
| Rakesh Gowda | CMO (manufacturer) | – |
| Sneha Kulkarni | Office Admin (manages people, cannot approve) | – |

15 demo projects sit at different points of the flow. Each person sees only the projects that are theirs
(see AUDIT.md section 3) – sign in as different people to see the difference.

## Settings (environment variables)

| Variable | Meaning |
|---|---|
| `NEO_DATA_DIR` | Where the database and uploaded files are kept (default `backend/data`) |
| `NEO_AUTOSEED=0` | Start empty (no demo people/projects) |
| `NEO_DEMO_LOGIN=0` | Hide the demo account list on the sign-in page |
| `NEO_SMTP_HOST`, `NEO_SMTP_PORT`, `NEO_SMTP_USER`, `NEO_SMTP_PASSWORD`, `NEO_SMTP_FROM`, `NEO_SMTP_TLS`, `NEO_BASE_URL` | Send an e-mail copy of every notification |
| `NEO_SECRET` | Key for sign-in sessions (otherwise generated once into the data folder) |

If an older (version 1) database is found it is kept as `neo.old-<date>.db` and the app starts fresh.

## Tests

```
cd backend && python -m pytest          # 38 tests – flow, visibility, hierarchy, reminders, e-mail, security
NEO_URL=http://localhost:8090 python e2e/ui_journey.py   # 47 browser checks (Playwright + Edge, fresh database)
```

See **[AUDIT.md](AUDIT.md)** for the requirement-by-requirement check, and **[docs/WORKFLOW_RESEARCH.md](docs/WORKFLOW_RESEARCH.md)**
for the research.
