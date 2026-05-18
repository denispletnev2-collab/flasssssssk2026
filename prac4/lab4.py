import secrets
import string
from datetime import datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import BooleanField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = "my-blog-secret-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_ENABLED"] = True

db = SQLAlchemy(app)


# ── Models ────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    posts = db.relationship("Post", backref="author", lazy=True)

    def check_password(self, pwd: str) -> bool:
        return check_password_hash(self.password_hash, pwd)


class Post(db.Model):
    __tablename__ = "posts"

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    is_private = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


# ── Session helpers ───────────────────────────────────────────────────────────

def get_current_user() -> User | None:
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            flash("Войдите в систему.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Войдите в систему.", "warning")
            return redirect(url_for("login"))
        if not user.is_admin:
            flash("Недостаточно прав.", "danger")
            return redirect(url_for("feed"))
        return view(*args, **kwargs)
    return wrapped


# ── Forms ─────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Укажите логин."),
            Length(min=3, max=50, message="Логин: от 3 до 50 символов."),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Укажите пароль.")],
    )
    submit = SubmitField("Войти")


class PostForm(FlaskForm):
    title = StringField(
        "Заголовок",
        validators=[
            DataRequired(message="Заголовок обязателен."),
            Length(min=3, max=200, message="Заголовок: от 3 до 200 символов."),
        ],
    )
    body = TextAreaField(
        "Текст",
        validators=[
            DataRequired(message="Текст обязателен."),
            Length(min=5, message="Текст должен быть не менее 5 символов."),
        ],
    )
    is_private = BooleanField("Скрыть от гостей")
    submit = SubmitField("Сохранить")


class RegisterForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Укажите логин."),
            Length(min=3, max=50, message="Логин: от 3 до 50 символов."),
            Regexp(r"^[A-Za-z0-9_.\-]+$", message="Логин: только латиница, цифры, _, . и -"),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Укажите пароль."),
            Length(min=6, message="Минимум 6 символов."),
        ],
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


class SignupForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Укажите логин."),
            Length(min=3, max=50, message="Логин: от 3 до 50 символов."),
            Regexp(r"^[A-Za-z0-9_.\-]+$", message="Логин: только латиница, цифры, _, . и -"),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Укажите пароль."),
            Length(min=6, message="Минимум 6 символов."),
        ],
    )
    password_confirm = PasswordField(
        "Повтор пароля",
        validators=[
            DataRequired(message="Повторите пароль."),
            EqualTo("password", message="Пароли не совпадают."),
        ],
    )
    submit = SubmitField("Зарегистрироваться")


# ── Startup ───────────────────────────────────────────────────────────────────

def _random_pwd() -> str:
    chars = string.ascii_letters + string.digits
    return "Aa1!" + "".join(secrets.choice(chars) for _ in range(8))


def seed_admin() -> None:
    if User.query.filter_by(username="admin").first():
        return

    pwd = _random_pwd()
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash(pwd),
        is_admin=True,
    ))
    db.session.commit()

    print("=" * 55)
    print("Создан администратор по умолчанию:")
    print("  логин:  admin")
    print(f"  пароль: {pwd}")
    print("Сохраните пароль!")
    print("=" * 55)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("feed"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("feed"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if not user or not user.check_password(form.password.data):
            flash("Неверный логин или пароль.", "danger")
        else:
            session.clear()
            session["user_id"] = user.id
            flash("Добро пожаловать!", "success")
            return redirect(url_for("feed"))

    return render_template("login.html", form=form, current_user=None)


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("feed"))


@app.route("/posts")
def feed():
    user = get_current_user()
    q = Post.query.order_by(Post.created_at.desc())
    if not user:
        q = q.filter_by(is_private=False)
    posts = q.all()
    return render_template("posts.html", posts=posts, current_user=user)


@app.route("/posts/new", methods=["GET", "POST"])
@login_required
def post_create():
    user = get_current_user()
    form = PostForm()
    if form.validate_on_submit():
        db.session.add(Post(
            title=form.title.data.strip(),
            body=form.body.data.strip(),
            is_private=bool(form.is_private.data),
            user_id=user.id,
        ))
        db.session.commit()
        flash("Пост опубликован.", "success")
        return redirect(url_for("feed"))
    return render_template("post_form.html", form=form, heading="Новый пост", current_user=user)


@app.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def post_edit(post_id):
    user = get_current_user()
    post = db.session.get(Post, post_id) or abort(404)

    if post.user_id != user.id:
        flash("Можно редактировать только свои посты.", "danger")
        return redirect(url_for("feed"))

    form = PostForm(obj=post)
    # map body field from model attribute
    if request_is_get():
        form.body.data = post.body

    if form.validate_on_submit():
        post.title      = form.title.data.strip()
        post.body       = form.body.data.strip()
        post.is_private = bool(form.is_private.data)
        db.session.commit()
        flash("Пост обновлён.", "success")
        return redirect(url_for("feed"))

    return render_template("post_form.html", form=form, heading="Редактировать пост", current_user=user)


def request_is_get():
    from flask import request
    return request.method == "GET"


@app.route("/users/create", methods=["GET", "POST"])
@admin_required
def user_create():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash(f"Пользователь «{username}» уже существует.", "danger")
        else:
            db.session.add(User(
                username=username,
                password_hash=generate_password_hash(form.password.data),
                is_admin=bool(form.is_admin.data),
            ))
            db.session.commit()
            flash(f"Пользователь «{username}» создан.", "success")
            return redirect(url_for("user_create"))

    users = User.query.order_by(User.username).all()
    return render_template("create_user.html", form=form, users=users, current_user=get_current_user())



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if get_current_user():
        return redirect(url_for("feed"))

    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash(f"Пользователь «{username}» уже существует.", "danger")
        else:
            db.session.add(User(
                username=username,
                password_hash=generate_password_hash(form.password.data),
                is_admin=False,
            ))
            db.session.commit()
            flash("Аккаунт создан! Войдите.", "success")
            return redirect(url_for("login"))

    return render_template("signup.html", form=form, current_user=None)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_admin()
    app.run(debug=True)
