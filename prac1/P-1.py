import sys
import io
import contextlib
from itertools import cycle
import datetime
from flask import Flask, jsonify, request

status_lst = ["cancelled", "completed", "in_progress", "pending"]
priority_lst = ["high", "low", "medium"]

def get_task_list():
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        import this
    text = f.getvalue()
    status_cycle = cycle(status_lst)
    priority_cycle = cycle(priority_lst)
    tasks_lst = []
    num = 0
    for line in text.splitlines():
        if not line:
            continue
        num += 1
        tasks_lst.append({
            "id": num,
            "title": "Zen of Python",
            "description": line,
            "status": next(status_cycle),
            "priority": next(priority_cycle),
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "deleted_at": None,
        })
    return tasks_lst

tasks_lst = get_task_list()


"""  """





app = Flask(__name__)

@app.route("/api/v1/tasks", methods=["GET"])
def get_tasks():
    query = request.args.get("query", "").lower()
    order = request.args.get("order", "id")
    offset = int(request.args.get("offset", 0))

    result = tasks_lst
    if query:
        result = [t for t in result if query in t["title"].lower() or query in t["description"].lower()]

    reverse = False
    if order.startswith("-"):
        reverse = True
        order = order[1:]

    result = sorted(result, key=lambda x: x[order], reverse=reverse)
    result = result[offset:offset + 10]

    return jsonify({"tasks": result})


@app.route("/api/v1/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = next((t for t in tasks_lst if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404
    return jsonify(task)


@app.route("/api/v1/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Отсутствуют данные JSON"}), 400
    if "title" not in data:
        return jsonify({"error": "Пропущен обязательный параметр `title`"}), 400
    if "description" not in data:
        return jsonify({"error": "Пропущен обязательный параметр `description`"}), 400
    if "status" in data and data["status"] not in status_lst:
        return jsonify({"error": "Поле `status` невалидно"}), 400
    if "priority" in data and data["priority"] not in priority_lst:
        return jsonify({"error": "Поле `priority` невалидно"}), 400

    now = datetime.datetime.now().isoformat()
    task = {
        "id": len(tasks_lst) + 1,
        "title": data["title"],
        "description": data["description"],
        "status": data.get("status", "pending"),
        "priority": data.get("priority", "medium"),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    tasks_lst.append(task)
    return jsonify(task)


@app.route("/api/v1/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = next((t for t in tasks_lst if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404
    task["status"] = "cancelled"
    task["deleted_at"] = datetime.datetime.now().isoformat()
    task["updated_at"] = datetime.datetime.now().isoformat()
    return jsonify(task)


@app.route("/api/v1/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    task = next((t for t in tasks_lst if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Отсутствуют данные JSON"}), 400
    if "status" in data and data["status"] not in status_lst:
        return jsonify({"error": "Поле `status` невалидно"}), 400
    if "priority" in data and data["priority"] not in priority_lst:
        return jsonify({"error": "Поле `priority` невалидно"}), 400

    for field in ("title", "description", "status", "priority"):
        if field in data:
            task[field] = data[field]
    task["updated_at"] = datetime.datetime.now().isoformat()
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)