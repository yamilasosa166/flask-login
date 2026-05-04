# flask-login — Contexto

## Objetivo actual
MVP login: registro, login, logout, dashboard protegido. Hash con werkzeug, sesion via Flask-Login, datos en Postgres.

## Completado
- Estructura del proyecto inicializada (Flask 3 + blueprints `auth` y `main`)
- Modelo `User` con `username`/`email`/`password_hash`
- Templates Jinja con Bootstrap 5 (CDN)
- Dockerfile multi-stage (builder + runtime non-root + healthcheck)
- compose.yml con Postgres 16-alpine y healthchecks
- `db.create_all()` en startup — sin Alembic todavia

## Pendiente
- Validacion de complejidad de password mas estricta
- Rate limiting en /login (Flask-Limiter)
- CSRF (Flask-WTF) — formularios actualmente sin token
- Migrations (Alembic) cuando el schema crezca
- Tests (pytest + Flask test client)
- Email verification + reset password

## Blockers
- Ninguno
