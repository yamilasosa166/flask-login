# flask-login — Contexto

## Objetivo actual
Sistema simple de gestion de inventario sobre el login: productos, categorias, movimientos (entrada/salida/ajuste) con auditoria de stock, permisos por rol y registro de ventas multi-producto.

## Completado
- Auth: registro, login, logout, dashboard protegido
- Hash con werkzeug, sesion con Flask-Login
- Roles `admin` / `operador` (primer registrado queda como admin)
- Decorador `@admin_required` para rutas de gestion de catalogo
- Modelos: `User`, `Categoria`, `Producto`, `Movimiento`, `Venta`, `VentaItem`
- CRUD productos y categorias (admin) + registro de movimientos (cualquier user logueado)
- Movimientos con snapshot `stock_anterior` / `stock_resultante` (auditoria)
- Validaciones: stock no negativo, cantidad > 0, salida no excede stock
- Modulo de ventas completo:
  - `Venta` + `VentaItem` con snapshot de precio al momento de venta
  - Formulario multi-producto dinamico (JS — agregar/quitar filas, live total)
  - Consolidacion de items duplicados + re-validacion de stock agregado
  - Movimiento de salida automatico por cada item vendido
  - Lista de ventas con filtros de rango temporal (hoy/7d/30d/mes/anio/custom)
  - Vista detalle de venta con tabla de items
- Dashboard refactorizado con filtros de rango temporal:
  - KPIs de stock (productos activos, stock bajo, valor inventario, movimientos)
  - KPIs de ventas (count, total, items vendidos, ticket promedio)
  - Grafico de barras Chart.js (ventas Gs. por dia)
  - Top 5 productos vendidos
  - Ultimas 10 ventas + ultimos 10 movimientos
  - Stock critico con acceso rapido a ingreso
- Filtro Jinja `|pyg` para moneda Paraguay (sin decimales, separador miles)
- Migraciones con Alembic (Flask-Migrate) — schema versionado en `migrations/`
- Entrypoint del container corre `flask db upgrade` antes de gunicorn
- Fix CRLF en `docker/entrypoint.sh` via Dockerfile (`sed -i 's/\r//'`)

## Pendiente
- CSRF tokens en forms (Flask-WTF)
- Rate limiting en /login (Flask-Limiter)
- Tests con pytest
- Reset de password por email
- Export de inventario a CSV
- Vista detalle de producto con historial de movimientos
- Paginacion en listas (hoy lista completa, hard limit 200 en movimientos)
- Reportes: valuacion historica, alertas configurables

## Blockers
- Ninguno
