from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_, func
from . import db
from .models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template("register.html"), 400

        if len(password) < 8:
            flash("La contrasena debe tener al menos 8 caracteres.", "danger")
            return render_template("register.html"), 400

        existing = db.session.execute(
            db.select(User).where(or_(User.username == username, User.email == email))
        ).scalar_one_or_none()
        if existing:
            flash("Usuario o email ya registrado.", "danger")
            return render_template("register.html"), 409

        # Primer usuario registrado queda como admin (bootstrap del sistema).
        user_count = db.session.execute(db.select(func.count(User.id))).scalar_one()
        role = "admin" if user_count == 0 else "operador"

        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        msg = "Cuenta creada como administrador." if role == "admin" else "Cuenta creada. Ya podes iniciar sesion."
        flash(msg, "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = db.session.execute(
            db.select(User).where(
                or_(User.username == identifier, User.email == identifier)
            )
        ).scalar_one_or_none()

        if user is None or not user.check_password(password):
            flash("Credenciales invalidas.", "danger")
            return render_template("login.html"), 401

        login_user(user, remember=remember)
        next_url = request.args.get("next")
        return redirect(next_url or url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesion cerrada.", "info")
    return redirect(url_for("auth.login"))
