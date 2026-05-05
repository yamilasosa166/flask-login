import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy import or_, func
from . import db, limiter, mail
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
@limiter.limit("10 per minute", methods=["POST"])
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


def _make_reset_token(email: str) -> str:
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps(email, salt="password-reset")


def _verify_reset_token(token: str, max_age: int = 3600):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="password-reset", max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    return email


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()

        # Siempre el mismo mensaje para no revelar si el email existe
        if user:
            token = _make_reset_token(user.email)
            base_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")
            reset_url = f"{base_url}{url_for('auth.reset_password', token=token)}"
            msg = Message(
                subject="Restablecer contraseña",
                recipients=[user.email],
                body=(
                    f"Hola {user.username},\n\n"
                    f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
                    f"Hacé clic en el siguiente enlace (válido por 1 hora):\n{reset_url}\n\n"
                    f"Si no solicitaste esto, ignorá este mensaje."
                ),
            )
            mail.send(msg)

        flash("Si el email está registrado, recibirás un enlace para restablecer tu contraseña.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    email = _verify_reset_token(token)
    if email is None:
        flash("El enlace es inválido o ya expiró. Solicitá uno nuevo.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "danger")
            return render_template("reset_password.html", token=token), 400

        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()

        if user is None:
            flash("Usuario no encontrado.", "danger")
            return redirect(url_for("auth.login"))

        user.set_password(password)
        db.session.commit()
        flash("Contraseña actualizada. Ya podés iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)
