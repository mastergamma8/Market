#!/usr/bin/env bash
set -e

# Fly.io передаёт переменную FLY_PROCESS, по ней различаем web и worker
if [ "$FLY_PROCESS" = "worker" ]; then
  echo "🚀 Запуск aiogram-воркера (polling + фоновые задачи)"
  python main.py
else
  echo "🌐 Запуск FastAPI (uvicorn) на порту 8080"
  uvicorn app:app --host 0.0.0.0 --port 8080
fi
