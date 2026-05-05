from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint
from . import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="operador", server_default="operador")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    movimientos = db.relationship("Movimiento", back_populates="usuario", lazy="dynamic")

    __table_args__ = (
        CheckConstraint("role IN ('admin','operador')", name="users_role_check"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username} {self.role}>"


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False, index=True)
    descripcion = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    productos = db.relationship("Producto", back_populates="categoria", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Categoria {self.nombre}>"


class Producto(db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=True, index=True)
    stock_actual = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    stock_min = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    activo = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    categoria = db.relationship("Categoria", back_populates="productos")
    movimientos = db.relationship("Movimiento", back_populates="producto", lazy="dynamic", cascade="all, delete-orphan")
    tipos_precio = db.relationship(
        "TipoPrecio",
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="TipoPrecio.id",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("stock_actual >= 0", name="productos_stock_no_negativo"),
        CheckConstraint("stock_min >= 0", name="productos_stock_min_no_negativo"),
    )

    @property
    def stock_bajo(self) -> bool:
        return self.stock_actual <= self.stock_min

    @property
    def precio_base(self) -> int:
        """Primer tipo de precio disponible, para valuación de inventario."""
        return self.tipos_precio[0].precio if self.tipos_precio else 0

    def __repr__(self) -> str:
        return f"<Producto {self.sku} {self.nombre}>"


class TipoPrecio(db.Model):
    __tablename__ = "tipos_precio"

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = db.Column(db.String(60), nullable=False)
    precio = db.Column(db.Integer, nullable=False, default=0)

    producto = db.relationship("Producto", back_populates="tipos_precio")

    __table_args__ = (
        CheckConstraint("precio >= 0", name="tipos_precio_precio_no_negativo"),
        db.UniqueConstraint("producto_id", "nombre", name="tipos_precio_producto_nombre_uq"),
    )

    def __repr__(self) -> str:
        return f"<TipoPrecio {self.nombre} {self.precio}>"


class Movimiento(db.Model):
    __tablename__ = "movimientos"

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo = db.Column(db.String(16), nullable=False)  # entrada | salida | ajuste
    cantidad = db.Column(db.Integer, nullable=False)
    stock_anterior = db.Column(db.Integer, nullable=False)
    stock_resultante = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(255), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    producto = db.relationship("Producto", back_populates="movimientos")
    usuario = db.relationship("User", back_populates="movimientos")

    __table_args__ = (
        CheckConstraint("tipo IN ('entrada','salida','ajuste')", name="movimientos_tipo_check"),
        CheckConstraint("cantidad > 0", name="movimientos_cantidad_positiva"),
        CheckConstraint("stock_anterior >= 0", name="movimientos_stock_anterior_no_neg"),
        CheckConstraint("stock_resultante >= 0", name="movimientos_stock_resultante_no_neg"),
    )

    def __repr__(self) -> str:
        return f"<Movimiento {self.tipo} {self.cantidad} prod={self.producto_id}>"


class Venta(db.Model):
    __tablename__ = "ventas"

    id = db.Column(db.Integer, primary_key=True)
    cliente_nombre = db.Column(db.String(120), nullable=True)
    notas = db.Column(db.String(255), nullable=True)
    total = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    items = db.relationship(
        "VentaItem",
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="VentaItem.id",
    )
    usuario = db.relationship("User")

    __table_args__ = (
        CheckConstraint("total >= 0", name="ventas_total_no_negativo"),
    )

    @property
    def cantidad_items(self) -> int:
        return sum(i.cantidad for i in self.items)

    def __repr__(self) -> str:
        return f"<Venta #{self.id} total={self.total}>"


class VentaItem(db.Model):
    __tablename__ = "venta_items"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo_precio_nombre = db.Column(db.String(60), nullable=False, default="Unidad", server_default="Unidad")
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Integer, nullable=False)  # snapshot al momento de la venta
    subtotal = db.Column(db.Integer, nullable=False)

    venta = db.relationship("Venta", back_populates="items")
    producto = db.relationship("Producto")

    __table_args__ = (
        CheckConstraint("cantidad > 0", name="venta_items_cantidad_positiva"),
        CheckConstraint("precio_unitario >= 0", name="venta_items_precio_no_negativo"),
        CheckConstraint("subtotal >= 0", name="venta_items_subtotal_no_negativo"),
    )

    def __repr__(self) -> str:
        return f"<VentaItem v={self.venta_id} prod={self.producto_id} x{self.cantidad}>"
