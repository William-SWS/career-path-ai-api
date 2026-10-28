#!/bin/sh

# Script para aguardar o PostgreSQL estar acessível
# Uso: wait-for-postgres.sh host port

set -e

host="$1"
port="$2"

echo "Aguardando PostgreSQL estar acessível em $host:$port..."

until nc -z "$host" "$port" 2>/dev/null; do
  >&2 echo "PostgreSQL não está acessível ainda - aguardando..."
  sleep 1
done

>&2 echo "PostgreSQL está acessível!"

