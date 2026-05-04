# flask-login — Reglas del proyecto

> Hereda del CLAUDE.md global (`~/.claude/CLAUDE.md`). Solo se anota aqui lo especifico de este proyecto.

## Stack
- Python 3.12 · Flask 3.0 · Flask-Login 0.6 · Flask-SQLAlchemy 3.1
- PostgreSQL 16 (alpine) · driver `psycopg[binary]` 3.x
- Templates Jinja2 con Bootstrap 5 (CDN, sin build step)
- Gunicorn 23 como WSGI (2 workers)
- Sin frontend SPA, sin Flask-WTF (todavia), sin Alembic (todavia)

## Estructura
```
app/
  __init__.py    create_app() + extensiones
  models.py      User (UserMixin)
  routes.py      Blueprints: auth_bp, main_bp
  templates/     base.html, login.html, register.html, dashboard.html
wsgi.py          punto de entrada (gunicorn / dev server)
```

## Comandos
- Levantar: `docker compose up -d --build`
- Logs: `docker compose logs -f web`
- Bajar: `docker compose down` (mantiene volumen) · `docker compose down -v` (borra DB)
- Shell en container: `docker compose exec web python`
- Psql: `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB`

## Puertos (host)
- `5000` web (Flask) — variable `WEB_PORT` en `.env`
- `5432` db (Postgres) — variable `DB_PORT` en `.env`

Si colisionan, cambiar en `.env` antes de `up`.

## Decisiones del proyecto (no obvias)
- **`db.create_all()` en startup** — proto tier, no Alembic todavia. Cuando el schema cambie, migrar a Alembic antes de tocar tablas en prod.
- **`identifier` en login** — acepta username O email (case-insensitive en email).
- **Sin CSRF token** — formularios POST plain. Agregar Flask-WTF antes de exponer a internet.
- **`SECRET_KEY` obligatorio** — `create_app` falla rapido (KeyError) si falta. No usar default por seguridad.
- **psycopg v3, no psycopg2** — driver moderno. URL: `postgresql+psycopg://...` (no `postgresql://` ni `postgresql+psycopg2://`).

## Anti-patterns (no hacer)
- No reactivar `psycopg2-binary` — la URL ya esta atada a `psycopg` v3.
- No hardcodear `SECRET_KEY` ni passwords en codigo. Solo `.env` (no commiteado).
- No commitear `.env` — solo `.env.example`.
- No usar `flask run` en prod — gunicorn es el WSGI oficial del proyecto.
- No exponer puerto 5432 en prod — solo dev.

## Quality gates
- `docker compose ps` debe mostrar ambos servicios `healthy` antes de declarar OK.
- `curl http://localhost:5000/health` → `{"status":"ok"}` en <1s.
- Hash de password siempre via `werkzeug.security` — nunca comparar plaintext.
