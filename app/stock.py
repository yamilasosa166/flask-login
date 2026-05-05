import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user
from sqlalchemy import asc, desc, or_, delete, func
from sqlalchemy.exc import IntegrityError
from . import db
from .models import Categoria, Producto, TipoPrecio, Movimiento
from .decorators import admin_required
from .time_filters import parse_range

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")


# ----------------------------------------------------------------------------
# Categorias
# ----------------------------------------------------------------------------

@stock_bp.route("/categorias")
@login_required
def categorias_list():
    categorias = db.session.execute(
        db.select(Categoria).order_by(asc(Categoria.nombre))
    ).scalars().all()
    return render_template("stock/categorias_list.html", categorias=categorias)


@stock_bp.route("/categorias/nueva", methods=["GET", "POST"])
@admin_required
def categoria_nueva():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        descripcion = (request.form.get("descripcion") or "").strip() or None
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return render_template("stock/categoria_form.html", categoria=None), 400
        cat = Categoria(nombre=nombre, descripcion=descripcion)
        db.session.add(cat)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe una categoria con ese nombre.", "danger")
            return render_template("stock/categoria_form.html", categoria=None), 409
        flash(f"Categoria '{cat.nombre}' creada.", "success")
        return redirect(url_for("stock.categorias_list"))
    return render_template("stock/categoria_form.html", categoria=None)


@stock_bp.route("/categorias/<int:cat_id>/editar", methods=["GET", "POST"])
@admin_required
def categoria_editar(cat_id: int):
    cat = db.session.get(Categoria, cat_id) or abort(404)
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        descripcion = (request.form.get("descripcion") or "").strip() or None
        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return render_template("stock/categoria_form.html", categoria=cat), 400
        cat.nombre = nombre
        cat.descripcion = descripcion
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe una categoria con ese nombre.", "danger")
            return render_template("stock/categoria_form.html", categoria=cat), 409
        flash("Categoria actualizada.", "success")
        return redirect(url_for("stock.categorias_list"))
    return render_template("stock/categoria_form.html", categoria=cat)


@stock_bp.route("/categorias/<int:cat_id>/eliminar", methods=["POST"])
@admin_required
def categoria_eliminar(cat_id: int):
    cat = db.session.get(Categoria, cat_id) or abort(404)
    if cat.productos.count() > 0:
        flash("No se puede eliminar: la categoria tiene productos asociados.", "danger")
        return redirect(url_for("stock.categorias_list"))
    db.session.delete(cat)
    db.session.commit()
    flash("Categoria eliminada.", "info")
    return redirect(url_for("stock.categorias_list"))


# ----------------------------------------------------------------------------
# Productos
# ----------------------------------------------------------------------------

@stock_bp.route("/productos")
@login_required
def productos_list():
    q = (request.args.get("q") or "").strip()
    only_low = request.args.get("low") == "1"

    stmt = db.select(Producto)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(
            Producto.nombre.ilike(like),
            Producto.sku.ilike(like),
        ))
    if only_low:
        stmt = stmt.where(Producto.stock_actual <= Producto.stock_min, Producto.activo.is_(True))
    stmt = stmt.order_by(asc(Producto.nombre))

    productos = db.session.execute(stmt).scalars().all()
    return render_template("stock/productos_list.html", productos=productos, q=q, only_low=only_low)


@stock_bp.route("/productos/nuevo", methods=["GET", "POST"])
@admin_required
def producto_nuevo():
    categorias = db.session.execute(db.select(Categoria).order_by(asc(Categoria.nombre))).scalars().all()
    if request.method == "POST":
        data = _read_producto_form(request.form)
        if data["error"]:
            flash(data["error"], "danger")
            return render_template("stock/producto_form.html", producto=None, categorias=categorias, form=request.form), 400

        prod = Producto(
            sku=data["sku"],
            nombre=data["nombre"],
            categoria_id=data["categoria_id"],
            stock_min=data["stock_min"],
            precio_costo=data["precio_costo"],
            stock_actual=data["stock_inicial"],
            activo=True,
        )
        db.session.add(prod)
        try:
            db.session.flush()
            _save_tipos_precio(prod.id, data["tipo_nombres"], data["tipo_precios"], data["tipo_unidades"])
            if data["stock_inicial"] > 0:
                db.session.add(Movimiento(
                    producto_id=prod.id,
                    usuario_id=current_user.id,
                    tipo="entrada",
                    cantidad=data["stock_inicial"],
                    stock_anterior=0,
                    stock_resultante=data["stock_inicial"],
                    motivo="Stock inicial al crear producto",
                ))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un producto con ese SKU.", "danger")
            return render_template("stock/producto_form.html", producto=None, categorias=categorias, form=request.form), 409
        flash(f"Producto '{prod.nombre}' creado.", "success")
        return redirect(url_for("stock.productos_list"))
    return render_template("stock/producto_form.html", producto=None, categorias=categorias, form=None)


@stock_bp.route("/productos/<int:prod_id>/editar", methods=["GET", "POST"])
@admin_required
def producto_editar(prod_id: int):
    prod = db.session.get(Producto, prod_id) or abort(404)
    categorias = db.session.execute(db.select(Categoria).order_by(asc(Categoria.nombre))).scalars().all()
    if request.method == "POST":
        data = _read_producto_form(request.form, edit=True)
        if data["error"]:
            flash(data["error"], "danger")
            return render_template("stock/producto_form.html", producto=prod, categorias=categorias, form=request.form), 400

        prod.sku = data["sku"]
        prod.nombre = data["nombre"]
        prod.categoria_id = data["categoria_id"]
        prod.stock_min = data["stock_min"]
        prod.precio_costo = data["precio_costo"]
        prod.activo = data["activo"]
        try:
            _save_tipos_precio(prod.id, data["tipo_nombres"], data["tipo_precios"], data["tipo_unidades"])
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ya existe un producto con ese SKU.", "danger")
            return render_template("stock/producto_form.html", producto=prod, categorias=categorias, form=request.form), 409
        flash("Producto actualizado.", "success")
        return redirect(url_for("stock.productos_list"))
    return render_template("stock/producto_form.html", producto=prod, categorias=categorias, form=None)


def _save_tipos_precio(producto_id: int, nombres: list, precios: list, unidades_list: list) -> None:
    db.session.execute(delete(TipoPrecio).where(TipoPrecio.producto_id == producto_id))
    for nombre, precio, unidades in zip(nombres, precios, unidades_list):
        db.session.add(TipoPrecio(producto_id=producto_id, nombre=nombre, precio=precio, unidades=unidades))


def _read_producto_form(form, edit: bool = False) -> dict:
    sku = (form.get("sku") or "").strip().upper()
    nombre = (form.get("nombre") or "").strip()
    categoria_id = form.get("categoria_id") or None
    if categoria_id in (None, "", "0"):
        categoria_id = None
    else:
        try:
            categoria_id = int(categoria_id)
        except ValueError:
            categoria_id = None
    try:
        stock_min = int(form.get("stock_min") or 0)
    except ValueError:
        stock_min = -1
    try:
        precio_costo = int(form.get("precio_costo") or 0)
    except ValueError:
        precio_costo = -1
    try:
        stock_inicial = int(form.get("stock_inicial") or 0)
    except ValueError:
        stock_inicial = -1
    activo = form.get("activo") == "on" if edit else True

    # Tipos de precio: arrays paralelos tipo_nombre[], tipo_precio[], tipo_unidades[]
    tipo_nombres_raw = form.getlist("tipo_nombre")
    tipo_precios_raw = form.getlist("tipo_precio")
    tipo_unidades_raw = form.getlist("tipo_unidades")
    tipo_nombres = []
    tipo_precios = []
    tipo_unidades = []
    for n, p, u in zip(tipo_nombres_raw, tipo_precios_raw, tipo_unidades_raw):
        n = n.strip()
        if not n:
            continue
        try:
            precio = int(p or 0)
        except ValueError:
            precio = -1
        try:
            u_int = max(1, int(u or 1))
        except ValueError:
            u_int = 1
        tipo_nombres.append(n)
        tipo_precios.append(precio)
        tipo_unidades.append(u_int)

    error = None
    if not sku:
        error = "El SKU es obligatorio."
    elif not nombre:
        error = "El nombre es obligatorio."
    elif not tipo_nombres:
        error = "Debe agregar al menos un tipo de precio."
    elif any(p < 0 for p in tipo_precios):
        error = "Los precios deben ser >= 0."
    elif stock_min < 0:
        error = "El stock minimo debe ser >= 0."
    elif precio_costo < 0:
        error = "El precio de costo debe ser >= 0."
    elif not edit and stock_inicial < 0:
        error = "El stock inicial debe ser >= 0."

    return {
        "sku": sku,
        "nombre": nombre,
        "categoria_id": categoria_id,
        "tipo_nombres": tipo_nombres,
        "tipo_precios": tipo_precios,
        "tipo_unidades": tipo_unidades,
        "stock_min": stock_min,
        "precio_costo": precio_costo,
        "stock_inicial": stock_inicial,
        "activo": activo,
        "error": error,
    }


# ----------------------------------------------------------------------------
# Movimientos
# ----------------------------------------------------------------------------

@stock_bp.route("/productos/export.csv")
@login_required
def productos_export_csv():
    productos = db.session.execute(
        db.select(Producto).order_by(asc(Producto.nombre))
    ).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SKU", "Nombre", "Categoria", "Stock actual", "Stock minimo", "Estado", "Precios"])
    for p in productos:
        precios = " | ".join(f"{t.nombre}: Gs. {t.precio:,}".replace(",", ".") for t in p.tipos_precio)
        w.writerow([
            p.sku,
            p.nombre,
            p.categoria.nombre if p.categoria else "",
            p.stock_actual,
            p.stock_min,
            "activo" if p.activo else "inactivo",
            precios,
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=inventario.csv"},
    )


@stock_bp.route("/productos/<int:prod_id>")
@login_required
def producto_detalle(prod_id: int):
    prod = db.session.get(Producto, prod_id) or abort(404)
    tipo = request.args.get("tipo") or ""
    page = request.args.get("page", 1, type=int)

    stmt = db.select(Movimiento).where(Movimiento.producto_id == prod_id)
    if tipo in {"entrada", "salida", "ajuste"}:
        stmt = stmt.where(Movimiento.tipo == tipo)
    stmt = stmt.order_by(desc(Movimiento.fecha))

    paginacion = db.paginate(stmt, page=page, per_page=50, error_out=False)

    stats_rows = db.session.execute(
        db.select(
            Movimiento.tipo,
            func.count(Movimiento.id).label("count"),
            func.sum(Movimiento.cantidad).label("total"),
        )
        .where(Movimiento.producto_id == prod_id)
        .group_by(Movimiento.tipo)
    ).all()
    stats = {row.tipo: {"count": row.count, "total": row.total} for row in stats_rows}

    return render_template(
        "stock/producto_detalle.html",
        prod=prod,
        paginacion=paginacion,
        tipo=tipo,
        stats=stats,
    )


@stock_bp.route("/movimientos")
@login_required
def movimientos_list():
    rng = parse_range(
        request.args.get("preset"),
        request.args.get("desde"),
        request.args.get("hasta"),
    )
    tipo = request.args.get("tipo") or ""

    stmt = db.select(Movimiento).where(
        Movimiento.fecha >= rng["desde"], Movimiento.fecha <= rng["hasta"]
    )
    if tipo in {"entrada", "salida", "ajuste"}:
        stmt = stmt.where(Movimiento.tipo == tipo)
    stmt = stmt.order_by(desc(Movimiento.fecha)).limit(500)

    movs = db.session.execute(stmt).scalars().all()
    return render_template("stock/movimientos_list.html", movimientos=movs, rng=rng, tipo=tipo)


@stock_bp.route("/movimientos/nuevo", methods=["GET", "POST"])
@login_required
def movimiento_nuevo():
    productos = db.session.execute(
        db.select(Producto).where(Producto.activo.is_(True)).order_by(asc(Producto.nombre))
    ).scalars().all()

    preselect_id = request.args.get("producto_id", type=int)

    if request.method == "POST":
        try:
            producto_id = int(request.form.get("producto_id") or 0)
        except ValueError:
            producto_id = 0
        tipo = (request.form.get("tipo") or "").strip()
        try:
            cantidad = int(request.form.get("cantidad") or 0)
        except ValueError:
            cantidad = 0
        motivo = (request.form.get("motivo") or "").strip() or None

        prod = db.session.get(Producto, producto_id) if producto_id else None
        error = None
        if prod is None:
            error = "Seleccione un producto valido."
        elif not prod.activo:
            error = "El producto esta inactivo."
        elif tipo not in {"entrada", "salida", "ajuste"}:
            error = "Tipo de movimiento invalido."
        elif cantidad <= 0:
            error = "La cantidad debe ser mayor a 0."

        if not error:
            stock_anterior = prod.stock_actual
            if tipo == "entrada":
                nuevo_stock = stock_anterior + cantidad
            elif tipo == "salida":
                if cantidad > stock_anterior:
                    error = f"Stock insuficiente (actual: {stock_anterior})."
                else:
                    nuevo_stock = stock_anterior - cantidad
            elif tipo == "ajuste":
                nuevo_stock = cantidad

        if error:
            flash(error, "danger")
            return render_template("stock/movimiento_form.html", productos=productos, preselect_id=preselect_id, form=request.form), 400

        prod.stock_actual = nuevo_stock
        db.session.add(Movimiento(
            producto_id=prod.id,
            usuario_id=current_user.id,
            tipo=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_resultante=nuevo_stock,
            motivo=motivo,
        ))
        db.session.commit()
        flash(f"Movimiento registrado. Stock actual: {nuevo_stock}.", "success")
        return redirect(url_for("stock.movimientos_list"))

    return render_template("stock/movimiento_form.html", productos=productos, preselect_id=preselect_id, form=None)
