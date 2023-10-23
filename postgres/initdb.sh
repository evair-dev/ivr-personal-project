#!/usr/bin/env bash
set -e

psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" <<-EOSQL
	CREATE DATABASE ${POSTGRES_DB};
	CREATE DATABASE ${POSTGRES_DB}_test;
	CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  CREATE ROLE ${POSTGRES_DB}_rw;
  CREATE ROLE ${POSTGRES_DB}_ro;

  GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO ${POSTGRES_DB}_rw;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${POSTGRES_DB}_rw;

  CREATE USER ${POSTGRES_DB}_rw_app WITH IN ROLE ${POSTGRES_DB}_rw ENCRYPTED PASSWORD '${POSTGRES_PASSWORD}';
  CREATE USER ${POSTGRES_DB}_ro_app WITH IN ROLE ${POSTGRES_DB}_ro ENCRYPTED PASSWORD '${POSTGRES_PASSWORD}';

  GRANT ${POSTGRES_DB}_rw TO $POSTGRES_USER;
  GRANT ${POSTGRES_DB}_ro TO $POSTGRES_USER;
EOSQL

