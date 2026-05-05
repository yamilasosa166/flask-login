import os
from datetime import date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from flask_mail import Message
from sqlalchemy import func, asc
from . import db, mail
from .models import Producto, Movimiento, User
from .decorators import admin_required

reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")


@reportes_bp.route("/valuacion")
@admin_required
def valuacion():
    productos_activos = db.session.execute(
        db.select(Producto).where(Producto.activo.is_(True)).order_by(asc(Producto.nombre))
    ).scalars().all()

    con_costo = [p for p in productos_activos if p.precio_costo > 0]
    sin_costo = [p for p in productos_activos if p.precio_costo == 0]
    total_valor = sum(p.stock_actual * p.precio_costo for p in con_costo)

    # Desglose por categoría
    cat_map = {}
    for p in con_costo:
        cat_nombre = p.categoria.nombre if p.categoria else "Sin categoría"
        if cat_nombre not in cat_map:
            cat_map[cat_nombre] = {"count": 0, "valor": 0}
        cat_map[cat_nombre]["count"] += 1
        cat_map[cat_nombre]["valor"] += p.stock_actual * p.precio_costo
    por_categoria = sorted(cat_map.items(), key=lambda x: -x[1]["valor"])

    # Histórico: últimos 30 días
    hoy = date.today()
    desde = hoy - timedelta(days=29)
    all_days = [desde + timedelta(days=i) for i in range(30)]

    rows = db.session.execute(
        db.select(
            func.date(Movimiento.fecha).label("dia"),
            func.sum(
                (Movimiento.stock_resultante - Movimiento.stock_anterior) * Producto.precio_costo
            ).label("delta"),
        )
        .join(Producto, Movimiento.producto_id == Producto.id)
        .where(Producto.precio_costo > 0, func.date(Movimiento.fecha) >= desde)
        .group_by(func.date(Movimiento.fecha))
        .order_by(func.date(Movimiento.fecha))
    ).all()

    delta_by_day = {}
    for row in rows:
        d = row.dia if isinstance(row.dia, date) else date.fromisoformat(str(row.dia))
        delta_by_day[d] = int(row.delta or 0)

    # Reconstruir hacia atrás desde el valor actual
    running = total_valor
    day_values = {}
    for d in reversed(all_days):
        day_values[d] = running
        running -= delta_by_day.get(d, 0)

    labels = [d.strftime("%d/%m") for d in all_days]
    values = [day_values[d] for d in all_days]

    return render_template(
        "reportes/valuacion.html",
        con_costo=con_costo,
        sin_costo=sin_costo,
        total_valor=total_valor,
        por_categoria=por_categoria,
        labels=labels,
        values=values,
    )


@reportes_bp.route("/alertas")
@admin_required
def alertas():
    criticos = db.session.execute(
        db.select(Producto)
        .where(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min)
        .order_by(asc(Producto.nombre))
    ).scalars().all()
    return render_template("reportes/alertas.html", criticos=criticos)


@reportes_bp.route("/alertas/enviar", methods=["POST"])
@admin_required
def alertas_enviar():
    criticos = db.session.execute(
        db.select(Producto)
        .where(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_min)
        .order_by(asc(Producto.nombre))
    ).scalars().all()

    if not criticos:
        flash("No hay productos en stock crítico. No se envió ningún email.", "info")
        return redirect(url_for("reportes.alertas"))

    admin_user = db.session.execute(
        db.select(User).where(User.role == "admin").order_by(asc(User.id))
    ).scalar_one_or_none()

    if not admin_user:
        flash("No se encontró usuario admin para enviar el email.", "danger")
        return redirect(url_for("reportes.alertas"))

    store_name = os.environ.get("STORE_NAME", "stock")
    filas = "\n".join(
        f"  - {p.nombre} (SKU: {p.sku}) — stock: {p.stock_actual} / mínimo: {p.stock_min}"
        for p in criticos
    )
    body = (
        f"Alerta de stock crítico — {store_name}\n\n"
        f"{len(criticos)} producto(s) están por debajo del mínimo configurado:\n\n"
        f"{filas}\n\n"
        f"Accedé al sistema para registrar ingresos:\n"
        f"{os.environ.get('APP_BASE_URL', 'http://localhost:5000')}/stock/productos"
    )

    try:
        msg = Message(
            subject=f"[{store_name}] Alerta: {len(criticos)} producto(s) en stock crítico",
            recipients=[admin_user.email],
            body=body,
        )
        mail.send(msg)
        flash(f"Email de alerta enviado a {admin_user.email}.", "success")
    except Exception as e:
        flash(f"Error al enviar email: {e}", "danger")

    return redirect(url_for("reportes.alertas"))
