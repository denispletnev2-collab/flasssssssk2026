import json
import os


def load_json(folder_name, file_name):
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
    full_path = os.path.join(folder_name, file_name)
    if not os.path.exists(full_path):
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(folder_name, file_name, data):
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
    full_path = os.path.join(folder_name, file_name)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    