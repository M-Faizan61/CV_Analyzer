@echo off
rem Double-click this file to start CV Analyzer.
cd /d "%~dp0"
echo Starting CV Analyzer...
echo Your browser will open at http://127.0.0.1:8520
echo Keep this window open while using the app. Press Ctrl+C to stop it.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 (
  echo.
  echo The app could not start. If port 8520 is in use, it may already be running:
  echo open http://127.0.0.1:8520 in your browser.
  pause
)
