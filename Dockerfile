FROM public.ecr.aws/docker/library/python:3.7-buster

RUN apt-get update
RUN apt-get install -y postgresql-client
RUN apt-get install -y --no-install-recommends graphviz

COPY config/pip.conf  root/.pip/pip.conf
COPY Pipfile .
COPY Pipfile.lock .

RUN pip install -U pip && pip install pipenv

RUN pipenv install --system --ignore-pipfile

WORKDIR /usr/src/app/

ENV PORT 9000
EXPOSE $PORT

ENTRYPOINT ["bin/entrypoint.sh"]

COPY . /usr/src/app
