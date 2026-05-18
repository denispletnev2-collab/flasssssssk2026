import json
import os
import re
import secrets
import string
from datetime import datetime
from functools import wraps
from threading import Lock

from flask import Flask, flash, redirect, render_template, session, url_for
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp
from werkzeug.security import check_password_hash, generate_password_hash


# ── Config ───────────────────────────────────────────────────────────────────

USER_DB = "users.json"
db_lock = Lock()

VALID_STATUSES = ["cancelled", "completed", "in_progress", "pending"]
VALID_PRIORITIES = ["high", "low", "medium"]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(256)
app.config["WTF_CSRF_ENABLED"] = True
csrf.init_app(app)


# ── JSON storage ─────────────────────────────────────────────────────────────

def _read_db() -> dict:
    with db_lock:
        if not os.path.exists(USER_DB):
            return {"users": []}
        with open(USER_DB, encoding="utf-8") as f:
            try:
                payload = json.load(f)
            except json.JSONDecodeError:
                return {"users": []}
        if not isinstance(payload.get("users"), list):
            return {"users": []}
        return payload


def _write_db(payload: dict) -> None:
    with db_lock:
        with open(USER_DB, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── User helpers ─────────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    return name.strip().lower()


def lookup_user(username: str) -> dict | None:
    target = _normalize(username)
    for u in _read_db()["users"]:
        if _normalize(u["username"]) == target:
            return u
    return None


def touch_login(username: str) -> None:
    payload = _read_db()
    target = _normalize(username)
    for u in payload["users"]:
        if _normalize(u["username"]) == target:
            u["last_login_at"] = _now()
            break
    _write_db(payload)


def logged_in_user() -> dict | None:
    name = session.get("username")
    return lookup_user(name) if name else None


# ── Password rules ────────────────────────────────────────────────────────────

def check_password_strength(pwd: str, username: str = "") -> list[str]:
    issues = []
    if len(pwd) < 8:
        issues.append("Пароль должен содержать минимум 8 символов.")
    if not re.search(r"[A-ZА-Я]", pwd):
        issues.append("Пароль должен содержать хотя бы одну заглавную букву.")
    if not re.search(r"[a-zа-я]", pwd):
        issues.append("Пароль должен содержать хотя бы одну строчную букву.")
    if not re.search(r"\d", pwd):
        issues.append("Пароль должен содержать хотя бы одну цифру.")
    if not re.search(r"[^\w\s]", pwd):
        issues.append("Пароль должен содержать хотя бы один спецсимвол.")
    if re.search(r"\s", pwd):
        issues.append("Пароль не должен содержать пробелы.")
    if username and _normalize(username) in pwd.lower():
        issues.append("Пароль не должен содержать имя пользователя.")
    return issues


def _random_password() -> str:
    pool = string.ascii_letters + string.digits
    tail = "".join(secrets.choice(pool) for _ in range(10))
    return f"Aa1!{tail}"


# ── Startup ───────────────────────────────────────────────────────────────────

def init_admin() -> None:
    payload = _read_db()
    if payload["users"]:
        return

    pwd = "Jostkiy_Chips_2026" 
    payload["users"].append({
        "username": "admin",
        "password_hash": generate_password_hash(pwd),
        "is_admin": True,
        "registered_at": _now(),
        "last_login_at": None,
    })
    _write_db(payload)

    print("=" * 55)
    print("Первый запуск — создан аккаунт администратора:")
    print("  логин:  admin")
    print(f"  пароль: {pwd}")
    print("Сохраните пароль перед входом!")
    print("=" * 55)


# ── Access control ────────────────────────────────────────────────────────────

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = logged_in_user()
        if user is None:
            flash("Войдите в систему.", "warning")
            return redirect(url_for("login_page"))
        if not user.get("is_admin"):
            flash("Недостаточно прав.", "danger")
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped


# ── Forms ─────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Укажите логин."),
            Length(min=3, max=32, message="Логин: от 3 до 32 символов."),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Укажите пароль."), check_password_strength],
    )
    submit = SubmitField("Войти")


class CreateUserForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Укажите логин."),
            Length(min=3, max=32, message="Логин: от 3 до 32 символов."),
            Regexp(
                r"^[A-Za-z0-9_.\-]+$",
                message="Логин: только латиница, цифры, _, . и -",
            ),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Укажите пароль.")],
    )
    password_confirm = PasswordField(
        "Повтор пароля",
        validators=[
            DataRequired(message="Повторите пароль."),
            EqualTo("password", message="Пароли не совпадают."),
        ],
    )
    is_admin = BooleanField("Права администратора")
    submit = SubmitField("Создать")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    user = logged_in_user()
    if user and user.get("is_admin"):
        return redirect(url_for("create_user_page"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        user = lookup_user(username)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Неверный логин или пароль.", "danger")
        else:
            session.clear()
            session["username"] = user["username"]
            touch_login(user["username"])
            flash("Добро пожаловать!", "success")
            return redirect(url_for("create_user_page"))
    return render_template("login.html", form=form)


@app.route("/logout")
def logout_page():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("login_page"))


@app.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user_page():
    form = CreateUserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        if lookup_user(username):
            flash(f"Пользователь «{username}» уже существует.", "danger")
        else:
            issues = check_password_strength(password, username)
            if issues:
                for msg in issues:
                    flash(msg, "danger")
            else:
                payload = _read_db()
                payload["users"].append({
                    "username": username,
                    "password_hash": generate_password_hash(password),
                    "is_admin": bool(form.is_admin.data),
                    "registered_at": _now(),
                    "last_login_at": None,
                })
                _write_db(payload)
                flash(f"Пользователь «{username}» создан.", "success")
                return redirect(url_for("create_user_page"))

    payload = _read_db()
    users = sorted(payload["users"], key=lambda u: u["username"].lower())
    return render_template(
        "create_user.html",
        form=form,
        users=users,
        current_user=logged_in_user(),
    )



@app.route("/users/delete/<username>", methods=["POST"])
@csrf.exempt
@admin_required
def delete_user_page(username):
    current = logged_in_user()

    # Нельзя удалить главного админа никому
    if _normalize(username) == "admin":
        flash("Пользователя «admin» удалить невозможно.", "danger")
        return redirect(url_for("create_user_page"))

    # Нельзя удалить самого себя
    if _normalize(username) == _normalize(current["username"]):
        flash("Нельзя удалить самого себя.", "danger")
        return redirect(url_for("create_user_page"))

    # Только главный admin может удалять других администраторов
    target = lookup_user(username)
    if target and target.get("is_admin") and _normalize(current["username"]) != "admin":
        flash("Только главный администратор может удалять других администраторов.", "danger")
        return redirect(url_for("create_user_page"))

    payload = _read_db()
    before = len(payload["users"])
    payload["users"] = [u for u in payload["users"] if _normalize(u["username"]) != _normalize(username)]

    if len(payload["users"]) == before:
        flash(f"Пользователь «{username}» не найден.", "danger")
    else:
        _write_db(payload)
        flash(f"Пользователь «{username}» удалён.", "success")

    return redirect(url_for("create_user_page"))


if __name__ == "__main__":
    init_admin()
    app.run(debug=True)
