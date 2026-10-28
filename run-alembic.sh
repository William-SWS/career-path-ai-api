#!/bin/bash
# Script para executar alembic usando o ambiente virtual

cd "$(dirname "$0")"
source .venv/bin/activate
alembic "$@"


