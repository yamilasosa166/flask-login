from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from . import db
from .models import Producto, Movimiento

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    total_productos = db.session.execute(
        db.select(func.count(Producto.id)).where(Producto.activo.is_(True))
    ).scalar_one()

    productos_stock_bajo = db.session.execute(
        db.select(func.count(Producto.id)).where(
            Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min
        )
    ).scalar_one()

    valor_inventario = db.session.execute(
        db.select(func.coalesce(func.sum(Producto.precio * Producto.stock_actual), 0)).where(
            Producto.activo.is_(True)
        )
    ).scalar_one()

    movimientos_hoy = db.session.execute(
        db.select(func.count(Movimiento.id)).where(
            func.date(Movimiento.fecha) == func.current_date()
        )
    ).scalar_one()

    productos_criticos = db.session.execute(
        db.select(Producto)
        .where(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min)
        .order_by((Producto.stock_actual - Producto.stock_min).asc(), Producto.nombre.asc())
        .limit(10)
    ).scalars().all()

    ultimos_movs = db.session.execute(
        db.select(Movimiento).order_by(desc(Movimiento.fecha)).limit(8)
    ).scalars().all()

    return render_template(
        "dashboard.html",
        total_productos=total_productos,
        productos_stock_bajo=productos_stock_bajo,
        valor_inventario=valor_inventario,
        movimientos_hoy=movimientos_hoy,
        productos_criticos=productos_criticos,
        ultimos_movs=ultimos_movs,
    )


@main_bp.route("/health")
def health():
    return {"status": "ok"}, 200
