#!/usr/bin/env bash

set -ea
set +x

if [ "$1" = 'web' ]; then
  export GUNICORN_WEBSERVER_ENABLED="true"
  exec gunicorn -t 60 -w 2 --logger-class=ivr_gateway.logger.BearerLogger --log-level="$LOG_LEVEL" --access-logfile=- --error-logfile=- -b 0.0.0.0:9000 ivr_gateway.app:app --reload
elif [ "$1" = 'prod_web' ]; then
  export GUNICORN_WEBSERVER_ENABLED="true"
  # exec gunicorn -t 60 -w 2 --worker-class=gevent --worker-connections=500 --log-level=info --access-logfile=- --error-logfile=- -b 0.0.0.0:9000 ivr_gateway.app:app
  exec gunicorn -t 60 -w 3 --logger-class=ivr_gateway.logger.BearerLogger --log-level="$LOG_LEVEL" --access-logfile=- --error-logfile=- -b 0.0.0.0:9000 ivr_gateway.app:app
elif [ "$1" = 'test' ]; then
  pipenv install --dev
  pipenv run tox .env.test
elif [ "$1" = 'celery' ]; then
  exec celery -A ivr_gateway.celery_app:app worker -l info -Q default --concurrency=4
elif [ "$1" = 'flower' ]; then
  exec celery -A ivr_gateway.celery_app:app flower --port=5555 --broker="$REDIS_URL"
elif [ "$1" = 'create_revision' ]; then
  bin/wait_for_postgres.sh
  PYTHONPATH=. alembic upgrade head
  PYTHONPATH=. exec alembic revision --autogenerate -m "$2"
elif [ "$1" = 'db_migrate' ]; then
  bin/wait_for_postgres.sh
  PYTHONPATH=. exec alembic upgrade head
elif [ "$1" = 'db_downgrade' ]; then
  revision=${2:-"-1"}
  bin/wait_for_postgres.sh
  PYTHONPATH=. exec alembic downgrade "$revision"
else
  PYTHONPATH=.
  exec "$@"
fi
