# flask-login — Contexto

## Objetivo actual
Sistema simple de gestion de inventario sobre el login: productos, categorias, movimientos (entrada/salida/ajuste) con auditoria de stock y permisos por rol.

## Completado
- Auth: registro, login, logout, dashboard protegido
- Hash con werkzeug, sesion con Flask-Login
- Roles `admin` / `operador` (primer registrado queda como admin)
- Decorador `@admin_required` para rutas de gestion de catalogo
- Modelos: `User` (con role), `Categoria`, `Producto`, `Movimiento`
- CRUD productos y categorias (admin) + registro de movimientos (cualquier user logueado)
- Movimientos con snapshot `stock_anterior` / `stock_resultante` (auditoria)
- Validaciones: stock no negativo, cantidad > 0, salida no excede stock
- Dashboard con metricas: productos activos, stock bajo, movimientos hoy, valor inventario
- Filtro Jinja `|pyg` para moneda Paraguay (sin decimales, separador miles)
- Migraciones con Alembic (Flask-Migrate) — schema versionado en `migrations/`
- Entrypoint del container corre `flask db upgrade` antes de gunicorn
- Adminer disponible via `docker compose --profile tools up adminer`

## Pendiente
- CSRF tokens en forms (Flask-WTF)
- Rate limiting en /login (Flask-Limiter)
- Tests con pytest
- Reset de password por email
- Export de inventario a CSV
- Edicion de stock_actual desde producto_form (hoy solo via Movimiento)
- Vista detalle de producto con su historial de movimientos
- Paginacion en listas (hoy lista completa, hard limit 200 en movimientos)
- Soft delete de productos (hoy `activo=false` lo oculta de movimientos pero no de listas)
- Reportes: top productos vendidos, valuacion historica, alertas configurables

## Blockers
- Ninguno
