#!/bin/sh
# wait_for_postgres.sh

set -e

until psql -c '\q' "$DATABASE_URL"; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"