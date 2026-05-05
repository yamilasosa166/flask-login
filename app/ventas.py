from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from . import db
from .models import Producto, Movimiento, Venta, VentaItem
from .time_filters import parse_range

ventas_bp = Blueprint("ventas", __name__, url_prefix="/ventas")


@ventas_bp.route("")
@login_required
def ventas_list():
    rng = parse_range(
        request.args.get("preset"),
        request.args.get("desde"),
        request.args.get("hasta"),
    )

    ventas = db.session.execute(
        db.select(Venta)
        .where(Venta.fecha >= rng["desde"], Venta.fecha <= rng["hasta"])
        .order_by(desc(Venta.fecha))
    ).scalars().unique().all()

    total_periodo = sum(v.total for v in ventas)
    n_ventas = len(ventas)
    items_vendidos = sum(v.cantidad_items for v in ventas)
    ticket_promedio = (total_periodo // n_ventas) if n_ventas else 0

    return render_template(
        "ventas/list.html",
        ventas=ventas,
        rng=rng,
        total_periodo=total_periodo,
        n_ventas=n_ventas,
        items_vendidos=items_vendidos,
        ticket_promedio=ticket_promedio,
    )


@ventas_bp.route("/<int:venta_id>")
@login_required
def venta_detalle(venta_id: int):
    venta = db.session.get(Venta, venta_id) or abort(404)
    return render_template("ventas/detalle.html", venta=venta)


@ventas_bp.route("/nueva", methods=["GET", "POST"])
@login_required
def venta_nueva():
    productos = db.session.execute(
        db.select(Producto)
        .where(Producto.activo.is_(True), Producto.stock_actual > 0)
        .order_by(asc(Producto.nombre))
    ).scalars().all()

    # Mapa producto_id -> lista de tipos para el JS del formulario
    tipos_por_producto = {
        p.id: [{"nombre": t.nombre, "precio": t.precio} for t in p.tipos_precio]
        for p in productos
    }

    if request.method == "POST":
        cliente_nombre = (request.form.get("cliente_nombre") or "").strip() or None
        notas = (request.form.get("notas") or "").strip() or None

        # Arrays paralelos: producto_id[], tipo_precio_nombre[], cantidad[]
        producto_ids = request.form.getlist("producto_id")
        tipo_nombres = request.form.getlist("tipo_precio_nombre")
        cantidades = request.form.getlist("cantidad")

        items_validos = []
        error = None

        if not producto_ids:
            error = "Agrega al menos un producto a la venta."
        else:
            for pid_raw, tipo_nombre, cant_raw in zip(producto_ids, tipo_nombres, cantidades):
                if not pid_raw or not cant_raw:
                    continue
                try:
                    pid = int(pid_raw)
                    cant = int(cant_raw)
                except ValueError:
                    error = "Cantidad o producto invalido."
                    break
                if cant <= 0:
                    error = "Las cantidades deben ser mayores a 0."
                    break
                prod = db.session.get(Producto, pid)
                if prod is None or not prod.activo:
                    error = "Producto inexistente o inactivo en la venta."
                    break
                tipo = next((t for t in prod.tipos_precio if t.nombre == tipo_nombre), None)
                if tipo is None:
                    error = f"Tipo de precio '{tipo_nombre}' no existe para '{prod.nombre}'."
                    break
                if cant > prod.stock_actual:
                    error = f"Stock insuficiente de '{prod.nombre}' (disponible: {prod.stock_actual}, pedido: {cant})."
                    break
                items_validos.append((prod, cant, tipo))

            if not items_validos and not error:
                error = "Agrega al menos un producto valido."

            if not error:
                # Consolidar duplicados (mismo producto + mismo tipo)
                consolidated = {}
                for prod, cant, tipo in items_validos:
                    key = (prod.id, tipo.nombre)
                    if key in consolidated:
                        consolidated[key]["cant"] += cant
                    else:
                        consolidated[key] = {"prod": prod, "cant": cant, "tipo": tipo}
                # Re-validar stock total por producto
                stock_usado = {}
                for entry in consolidated.values():
                    pid = entry["prod"].id
                    stock_usado[pid] = stock_usado.get(pid, 0) + entry["cant"]
                for pid, total_cant in stock_usado.items():
                    prod = next(e["prod"] for e in consolidated.values() if e["prod"].id == pid)
                    if total_cant > prod.stock_actual:
                        error = f"Stock insuficiente de '{prod.nombre}' (disponible: {prod.stock_actual}, pedido total: {total_cant})."
                        break
                items_validos = [(e["prod"], e["cant"], e["tipo"]) for e in consolidated.values()]

        if error:
            flash(error, "danger")
            return render_template(
                "ventas/form.html",
                productos=productos,
                tipos_por_producto=tipos_por_producto,
                form=request.form,
            ), 400

        venta = Venta(
            cliente_nombre=cliente_nombre,
            notas=notas,
            usuario_id=current_user.id,
            total=0,
        )
        db.session.add(venta)
        db.session.flush()

        total_calc = 0
        for prod, cant, tipo in items_validos:
            precio_snap = tipo.precio
            subtotal = precio_snap * cant
            total_calc += subtotal

            db.session.add(VentaItem(
                venta_id=venta.id,
                producto_id=prod.id,
                tipo_precio_nombre=tipo.nombre,
                cantidad=cant,
                precio_unitario=precio_snap,
                subtotal=subtotal,
            ))

            stock_anterior = prod.stock_actual
            prod.stock_actual = stock_anterior - cant
            db.session.add(Movimiento(
                producto_id=prod.id,
                usuario_id=current_user.id,
                tipo="salida",
                cantidad=cant,
                stock_anterior=stock_anterior,
                stock_resultante=prod.stock_actual,
                motivo=f"Venta #{venta.id}" + (f" — {cliente_nombre}" if cliente_nombre else ""),
            ))

        venta.total = total_calc

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            flash(f"Error al guardar la venta: {e.orig}", "danger")
            return render_template("ventas/form.html", productos=productos, tipos_por_producto=tipos_por_producto, form=request.form), 500

        flash(f"Venta #{venta.id} registrada — {total_calc:,} Gs.".replace(",", "."), "success")
        return redirect(url_for("ventas.venta_detalle", venta_id=venta.id))

    return render_template("ventas/form.html", productos=productos, tipos_por_producto=tipos_por_producto, form=None)
