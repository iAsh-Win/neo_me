@echo off
rem Starts Neo Project Flow on http://localhost:8090  (first start builds the screens and loads demo data)
cd /d "%~dp0"
if not exist frontend\node_modules ( cd frontend & call npm install & cd .. )
if not exist frontend\dist ( cd frontend & call npm run build & cd .. )
cd backend
python -m pip install -q -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
