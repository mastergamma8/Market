#!/usr/bin/env bash
# entrypoint.sh

set -e

if [ "$FLY_PROCESS" = "worker" ] || [ "$DO_PROCESS" = "worker" ]; then
  echo "🚀 Запуск aiogram воркера (polling + фоновые задачи)"
  python main.py
else
  echo "🌐 Запуск FastAPI (uvicorn) на порту 8080"
  uvicorn app:app --host 0.0.0.0 --port 8080
fi
