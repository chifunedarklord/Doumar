import re

with open("d:\\python\\taskflow\\screens\\tasks_screen.py", "r", encoding="utf-8") as f:
    orig = f.read()

# Remove open_task_dialog block
orig = re.sub(r"(?m)^\s*# ── Add / Edit Bottom Sheet ───────────────────────────────[\s\S]*?(?=\s*# ── Delete confirm)", "", orig)

# Replace references
orig = orig.replace("open_task_dialog(tt)", "on_navigate(\"task_edit\", task=tt)")
orig = orig.replace("open_task_dialog()", "on_navigate(\"task_edit\")")

with open("d:\\python\\taskflow\\screens\\tasks_screen.py", "w", encoding="utf-8") as f:
    f.write(orig)
