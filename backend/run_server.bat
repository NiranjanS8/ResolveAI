@echo off
cd /d C:\Users\Niranjan\Desktop\AI-Projects\ResolveAI\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio --log-level debug