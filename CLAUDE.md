# flask-login — Reglas del proyecto

> Hereda del CLAUDE.md global (`~/.claude/CLAUDE.md`). Solo se anota aqui lo especifico de este proyecto.

## Stack
- Python 3.12 · Flask 3.0 · Flask-Login 0.6 · Flask-SQLAlchemy 3.1 · Flask-Migrate 4 (Alembic)
- PostgreSQL 16 (alpine) · driver `psycopg[binary]` 3.x
- Templates Jinja2 con Bootstrap 5 + Bootstrap Icons (CDN)
- Gunicorn 23 como WSGI (2 workers)
- Adminer 4 como UI de DB (opcional, profile `tools`)
- Sin frontend SPA, sin Flask-WTF (todavia), sin tests (todavia)

## Estructura
```
app/
  __init__.py        create_app() + extensiones (db, migrate, login)
  models.py          User (role admin/operador) + Categoria + Producto + Movimiento
  auth.py            Blueprint auth (register/login/logout) — primer user = admin
  main.py            Blueprint main (index/dashboard/health) con metricas
  stock.py           Blueprint stock (CRUD productos/categorias + movimientos)
  decorators.py      @admin_required
  filters.py         Filtro Jinja |pyg (moneda Paraguay)
  templates/
    base.html, login.html, register.html, dashboard.html
    stock/
      productos_list.html, producto_form.html
      categorias_list.html, categoria_form.html
      movimientos_list.html, movimiento_form.html
migrations/          Alembic (versionado en git)
docker/entrypoint.sh Corre `flask db upgrade` y lanza gunicorn
wsgi.py              Punto de entrada (gunicorn / dev server)
```

## Comandos
- Levantar: `docker compose up -d --build`
- Logs: `docker compose logs -f web`
- Bajar: `docker compose down` (mantiene volumen) · `docker compose down -v` (borra DB)
- Adminer: `docker compose --profile tools up -d adminer` → http://localhost:8080
- Shell: `docker compose exec web python`
- Psql: `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB`

### Migraciones (Alembic)
- **Generar nueva**: `docker compose exec web flask db migrate -m "mensaje"`
- **Aplicar**: `docker compose exec web flask db upgrade` (tambien corre auto al `up`)
- **Revertir 1**: `docker compose exec web flask db downgrade -1`
- **Ver historial**: `docker compose exec web flask db history`
- **Ver actual**: `docker compose exec web flask db current`

## Puertos (host)
- `5000` web — variable `WEB_PORT`
- `5432` db — variable `DB_PORT`
- `8080` adminer (profile tools) — variable `ADMINER_PORT`

## Decisiones del proyecto (no obvias)
- **Primer usuario registrado = admin**. El resto = operador. Bootstrap del sistema sin flag manual.
- **Roles**: `admin` gestiona productos y categorias; `operador` solo registra movimientos. Cualquier user logueado lee.
- **`stock_actual` denormalizado en `productos`** + actualizado dentro de la misma transaccion del Movimiento. No se calcula sumando movimientos (mas simple, suficiente para "pequeño").
- **Cada Movimiento guarda snapshot** `stock_anterior` y `stock_resultante` — auditoria completa, no se pierde historia ante cambios futuros.
- **Tipo `ajuste`** reemplaza el stock por el valor indicado (no suma ni resta). Util para conteos fisicos.
- **Tipo `salida`** valida que `cantidad <= stock_actual`. Si falla, rechaza.
- **`identifier` en login** acepta username O email (case-insensitive en email).
- **Moneda PYG sin decimales** (alineado con CLAUDE.md global "fiscal PY"). Filtro `|pyg` formatea con separador `.`.
- **Stock inicial al crear producto**: si > 0 se registra automaticamente como Movimiento de entrada (queda en historial).
- **Categoria con productos asociados**: no se puede eliminar (FK RESTRICT). Mensaje claro en UI.
- **psycopg v3, no psycopg2** — URL: `postgresql+psycopg://...`
- **Sin CSRF** — formularios POST plain. Agregar Flask-WTF antes de exponer a internet.
- **Migraciones obligatorias en arranque** — el entrypoint corre `flask db upgrade`. No se usa `db.create_all()`.

## Anti-patterns (no hacer)
- No reactivar `psycopg2-binary` — la URL ya esta atada a `psycopg` v3.
- No hardcodear `SECRET_KEY` ni passwords en codigo. Solo `.env` (no commiteado).
- No commitear `.env` — solo `.env.example`.
- No usar `flask run` en prod — gunicorn es el WSGI oficial del proyecto.
- No tocar `migrations/versions/*.py` ya commiteadas — generar una nueva con `flask db migrate`.
- No exponer puerto 5432 ni 8080 en prod — solo dev.
- No bajar permisos de admin del primer user en frio sin un seeding alternativo (te quedas sin admin).

## Quality gates
- `docker compose ps` debe mostrar ambos servicios `healthy` antes de declarar OK.
- `curl http://localhost:5000/health` → `{"status":"ok"}` en <1s.
- Hash de password siempre via `werkzeug.security` — nunca comparar plaintext.
- Cualquier cambio de schema requiere una migracion Alembic (nunca `alter table` manual).
- Movimientos siempre actualizan `productos.stock_actual` en la misma transaccion.
