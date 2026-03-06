## Python+PostGIS backend for sensors
Based on: https://docs.docker.com/language/python/develop/

# git
This repo uses linting etc. Usage of the git UI will result in errors. Use:
```bash
git add -A
git commit -m "..."
```

# .env
Make an .env with:
```
# ./.env
# enviroments for docker-compose stack

# docker-compose & project settings
COMPOSE_PROJECT_NAME=xx
COMPOSE_HTTP_TIMEOUT=60
COMPOSE_CONVERT_WINDOWS_PATHS=1

# main user
MAIN_USER=xx
MAIN_PASSWORD=xx

# database settings
DB_HOST=xx
DB_NAME=xx
PGDATA=/var/lib/postgresql/pgdata
```

# Databases
postgres       → system
projectname    → app database
