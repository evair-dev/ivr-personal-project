# IVR Modeling Service


## Creating a migration (revision in alembic terms)

To create a revision you need to run the `create_revision` command with a name 
for the revision you are creating

```
./create_migration.sh revision_name
```

Get up and running

1. Copy .env.example > .env
2. docker-compose build
3. docker-compose up