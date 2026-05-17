import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    abort,
)

app = Flask(__name__)
app.secret_key = "my-super-secret"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

BASE_PATH = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_PATH / "uploads"
DATA_FOLDER = BASE_PATH / "data"
DB_FILE = DATA_FOLDER / "filebase.json"

BLOCKED_EXTENSIONS = {".exe", ".sh", ".php", ".js"}


# ── Storage helpers ──────────────────────────────────────────────────────────

def _ensure_dirs():
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        DB_FILE.write_text(json.dumps({}, ensure_ascii=False, indent=4), encoding="utf-8")


def load_db() -> dict:
    _ensure_dirs()
    return json.loads(DB_FILE.read_text(encoding="utf-8"))


def save_db(records: dict) -> None:
    _ensure_dirs()
    DB_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=4), encoding="utf-8")


# ── File helpers ─────────────────────────────────────────────────────────────

def get_extension(name: str) -> str:
    return Path(name).suffix.lower()


def is_blocked(name: str) -> bool:
    return get_extension(name) in BLOCKED_EXTENSIONS


def md5_of_stream(file_obj) -> str:
    h = hashlib.md5()
    file_obj.stream.seek(0)
    while chunk := file_obj.stream.read(8192):
        h.update(chunk)
    file_obj.stream.seek(0)
    return h.hexdigest()


def build_save_path(file_id: str, ext: str):
    """Returns (relative_path, absolute_path) using first 4 hex chars as subdirs."""
    subdir = Path("uploads") / file_id[:2] / file_id[2:4]
    filename = f"{file_id}{ext}"
    rel = subdir / filename
    return rel, BASE_PATH / rel


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/files/<path:filepath>")
def download_file(filepath):
    target = (BASE_PATH / filepath).resolve()
    uploads_root = UPLOAD_FOLDER.resolve()

    if not target.exists():
        abort(404)
    if uploads_root not in target.parents and target != uploads_root:
        abort(403)

    return send_from_directory(BASE_PATH, filepath)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded = request.files.get("file")

        if not uploaded or uploaded.filename == "":
            flash("Файл не выбран.", "error")
            return redirect(url_for("index"))

        original_name = os.path.basename(uploaded.filename)
        ext = get_extension(original_name)

        if is_blocked(original_name):
            flash(
                f"Файлы с расширением {ext or '[без расширения]'} запрещены к загрузке.",
                "error",
            )
            return redirect(url_for("index"))

        digest = md5_of_stream(uploaded)
        records = load_db()

        if any(r["md5"] == digest for r in records.values()):
            flash("Этот файл уже загружен (совпадение по MD5).", "error")
            return redirect(url_for("index"))

        file_id = uuid.uuid4().hex
        rel_path, abs_path = build_save_path(file_id, ext)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        uploaded.save(abs_path)

        mime, _ = mimetypes.guess_type(original_name)

        records[file_id] = {
            "file_id": file_id,
            "original_name": original_name,
            "stored_name": f"{file_id}{ext}",
            "path": rel_path.as_posix(),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "ext": ext,
            "md5": digest,
            "mime": mime or "application/octet-stream",
        }

        save_db(records)
        flash("Файл успешно загружен!", "success")
        return redirect(url_for("index"))

    records = load_db()
    file_list = sorted(records.values(), key=lambda r: r["uploaded_at"], reverse=True)
    return render_template("upload.html", files=file_list)


@app.route("/delete/<file_id>", methods=["POST"])
def delete_file(file_id):
    records = load_db()

    if file_id not in records:
        flash("Файл не найден.", "error")
        return redirect(url_for("index"))

    abs_path = BASE_PATH / records[file_id]["path"]
    if abs_path.exists():
        abs_path.unlink()

    del records[file_id]
    save_db(records)
    flash("Файл удалён.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    _ensure_dirs()
    app.run(debug=True)
