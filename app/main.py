from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from sqlalchemy import func, desc, asc
from . import db
from .models import Producto, Movimiento, Venta, VentaItem, TipoPrecio, User
from .time_filters import parse_range

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_admin:
        return _dashboard_operador()
    return _dashboard_admin()


# ---------------------------------------------------------------------------
# Dashboard operador — solo sus propias ventas/movimientos del día
# ---------------------------------------------------------------------------

def _dashboard_operador():
    rng = parse_range(
        request.args.get("preset") or "hoy",
        request.args.get("desde"),
        request.args.get("hasta"),
    )
    desde, hasta = rng["desde"], rng["hasta"]
    uid = current_user.id

    ventas_total = db.session.execute(
        db.select(func.coalesce(func.sum(Venta.total), 0)).where(
            Venta.fecha >= desde, Venta.fecha <= hasta, Venta.usuario_id == uid
        )
    ).scalar_one()

    ventas_count = db.session.execute(
        db.select(func.count(Venta.id)).where(
            Venta.fecha >= desde, Venta.fecha <= hasta, Venta.usuario_id == uid
        )
    ).scalar_one()

    ventas_items = db.session.execute(
        db.select(func.coalesce(func.sum(VentaItem.cantidad), 0))
        .join(Venta, VentaItem.venta_id == Venta.id)
        .where(Venta.fecha >= desde, Venta.fecha <= hasta, Venta.usuario_id == uid)
    ).scalar_one()

    ticket_promedio = (ventas_total // ventas_count) if ventas_count else 0

    movimientos_count = db.session.execute(
        db.select(func.count(Movimiento.id)).where(
            Movimiento.fecha >= desde, Movimiento.fecha <= hasta, Movimiento.usuario_id == uid
        )
    ).scalar_one()

    mis_ventas = db.session.execute(
        db.select(Venta)
        .where(Venta.fecha >= desde, Venta.fecha <= hasta, Venta.usuario_id == uid)
        .order_by(desc(Venta.fecha))
        .limit(30)
    ).scalars().unique().all()

    mis_movimientos = db.session.execute(
        db.select(Movimiento)
        .where(Movimiento.fecha >= desde, Movimiento.fecha <= hasta, Movimiento.usuario_id == uid)
        .order_by(desc(Movimiento.fecha))
        .limit(30)
    ).scalars().all()

    return render_template(
        "dashboard_operador.html",
        rng=rng,
        ventas_total=ventas_total,
        ventas_count=ventas_count,
        ventas_items=ventas_items,
        ticket_promedio=ticket_promedio,
        movimientos_count=movimientos_count,
        mis_ventas=mis_ventas,
        mis_movimientos=mis_movimientos,
    )


# ---------------------------------------------------------------------------
# Dashboard admin — global + filtro por usuario
# ---------------------------------------------------------------------------

def _dashboard_admin():
    rng = parse_range(
        request.args.get("preset"),
        request.args.get("desde"),
        request.args.get("hasta"),
    )
    desde, hasta = rng["desde"], rng["hasta"]

    try:
        filtro_uid = int(request.args.get("usuario_id") or 0) or None
    except ValueError:
        filtro_uid = None

    users = db.session.execute(
        db.select(User).order_by(asc(User.username))
    ).scalars().all()
    filtro_usuario = next((u for u in users if u.id == filtro_uid), None)

    # KPIs de stock — siempre globales, no se filtran por usuario
    total_productos = db.session.execute(
        db.select(func.count(Producto.id)).where(Producto.activo.is_(True))
    ).scalar_one()

    productos_stock_bajo = db.session.execute(
        db.select(func.count(Producto.id)).where(
            Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min
        )
    ).scalar_one()

    precio_base_subq = (
        db.select(func.coalesce(func.min(TipoPrecio.precio), 0))
        .where(TipoPrecio.producto_id == Producto.id)
        .correlate(Producto)
        .scalar_subquery()
    )
    valor_inventario = db.session.execute(
        db.select(func.coalesce(func.sum(precio_base_subq * Producto.stock_actual), 0))
        .where(Producto.activo.is_(True))
    ).scalar_one()

    # Filtros de ventas y movimientos (con usuario opcional)
    v_where = [Venta.fecha >= desde, Venta.fecha <= hasta]
    m_where = [Movimiento.fecha >= desde, Movimiento.fecha <= hasta]
    if filtro_uid:
        v_where.append(Venta.usuario_id == filtro_uid)
        m_where.append(Movimiento.usuario_id == filtro_uid)

    ventas_total = db.session.execute(
        db.select(func.coalesce(func.sum(Venta.total), 0)).where(*v_where)
    ).scalar_one()

    ventas_count = db.session.execute(
        db.select(func.count(Venta.id)).where(*v_where)
    ).scalar_one()

    ventas_items = db.session.execute(
        db.select(func.coalesce(func.sum(VentaItem.cantidad), 0))
        .join(Venta, VentaItem.venta_id == Venta.id)
        .where(*v_where)
    ).scalar_one()

    ticket_promedio = (ventas_total // ventas_count) if ventas_count else 0

    movimientos_count = db.session.execute(
        db.select(func.count(Movimiento.id)).where(*m_where)
    ).scalar_one()

    # Serie diaria para el chart
    serie = db.session.execute(
        db.select(
            func.date(Venta.fecha).label("dia"),
            func.coalesce(func.sum(Venta.total), 0).label("monto"),
        )
        .where(*v_where)
        .group_by(func.date(Venta.fecha))
        .order_by(asc("dia"))
    ).all()
    chart_labels = [str(row.dia) for row in serie]
    chart_values = [int(row.monto) for row in serie]

    # Top productos
    top_stmt = (
        db.select(
            Producto.nombre.label("nombre"),
            Producto.sku.label("sku"),
            func.sum(VentaItem.cantidad).label("vendidos"),
            func.sum(VentaItem.subtotal).label("ingreso"),
        )
        .join(Venta, VentaItem.venta_id == Venta.id)
        .join(Producto, VentaItem.producto_id == Producto.id)
        .where(*v_where)
        .group_by(Producto.id, Producto.nombre, Producto.sku)
        .order_by(desc("vendidos"))
        .limit(5)
    )
    top_productos = db.session.execute(top_stmt).all()

    ventas_periodo = db.session.execute(
        db.select(Venta).where(*v_where).order_by(desc(Venta.fecha)).limit(10)
    ).scalars().unique().all()

    movs_periodo = db.session.execute(
        db.select(Movimiento).where(*m_where).order_by(desc(Movimiento.fecha)).limit(10)
    ).scalars().all()

    productos_criticos = db.session.execute(
        db.select(Producto)
        .where(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min)
        .order_by((Producto.stock_actual - Producto.stock_min).asc(), Producto.nombre.asc())
        .limit(8)
    ).scalars().all()

    return render_template(
        "dashboard.html",
        rng=rng,
        users=users,
        filtro_uid=filtro_uid,
        filtro_usuario=filtro_usuario,
        total_productos=total_productos,
        productos_stock_bajo=productos_stock_bajo,
        valor_inventario=valor_inventario,
        ventas_total=ventas_total,
        ventas_count=ventas_count,
        ventas_items=ventas_items,
        ticket_promedio=ticket_promedio,
        movimientos_count=movimientos_count,
        chart_labels=chart_labels,
        chart_values=chart_values,
        top_productos=top_productos,
        ventas_periodo=ventas_periodo,
        movs_periodo=movs_periodo,
        productos_criticos=productos_criticos,
    )


@main_bp.route("/health")
def health():
    return {"status": "ok"}, 200
