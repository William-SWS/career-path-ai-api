#!/bin/bash
# Script para executar o servidor usando o ambiente virtual

cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


