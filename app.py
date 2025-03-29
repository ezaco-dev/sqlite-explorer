from flask import Flask, request, render_template_string, redirect, url_for, flash, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "lws25_secret"

DB_FOLDER = "databases"
os.makedirs(DB_FOLDER, exist_ok=True)

def get_db():
    db_name = session.get("DATABASE")
    if not db_name:
        return None
    db_path = os.path.join(DB_FOLDER, db_name)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

STYLE = """
    <style>
        body { font-family: Arial, sans-serif; background: #1e1e1e; color: white; text-align: center; display: grid; place-items: center; height: 100vh;}
        .container { width: 90%; max-width: 600px; margin: auto; padding: 20px; background: #2e2e2e; border-radius: 20px}
        .card { background: #1E1E1E; padding: 15px; margin: 10px 0; border-radius: 8px; }
        input, button { padding: 10px; margin: 5px; border: none; border-radius: 4px; }
        input { background: #333; color: white; }
        button { background: #00adb5; color: white; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border: 1px solid white; text-align: center; }
        a { color: #00C3CC; text-decoration: none; }
        li {list-style-type: none;}
    </style>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        db_name = request.form.get("db_name")
        if db_name:
            session["DATABASE"] = f"{db_name}.db"
            return redirect(url_for("home"))

    databases = [f for f in os.listdir(DB_FOLDER) if f.endswith(".db")]
    current_db = session.get("DATABASE")

    tables = []
    if current_db:
        db = get_db()
        tables = [row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    return render_template_string(STYLE + """
        <div class="container">
            <h1>SQLite Explorer</h1>
            <form method="post">
                <input type="text" name="db_name" required placeholder="Database name">
                <button type="submit">Set Database</button>
            </form>
            <h2>Databases</h2>
            <ul>
                {% for db in databases %}
                    <li><a href="{{ url_for('switch_db', db_name=db) }}">{{ db }}</a></li>
                {% endfor %}
            </ul>

            {% if current_db %}
                <h2>Tables in {{ current_db }}</h2>
                <a href="{{ url_for('create_table') }}">Create New Table</a>
                <ul>
                    {% for table in tables %}
                        <li><a href="{{ url_for('view_table', name=table) }}">{{ table }}</a></li>
                    {% endfor %}
                </ul>
            {% endif %}
        </div>
    """, databases=databases, tables=tables, current_db=current_db)

@app.route("/switch_db/<db_name>")
def switch_db(db_name):
    session["DATABASE"] = db_name
    return redirect(url_for("home"))

@app.route("/create_table", methods=["GET", "POST"])
def create_table():
    if not session.get("DATABASE"):
        return redirect(url_for("home"))

    if request.method == "POST":
        table_name = request.form.get("table_name")
        columns = request.form.getlist("columns[]")

        if not table_name or not columns:
            flash("Table name and columns are required!", "error")
            return redirect(url_for("create_table"))

        try:
            db = get_db()
            columns_def = ", ".join([f"{col} TEXT" for col in columns])
            db.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {columns_def})")
            db.commit()
            return redirect(url_for("view_table", name=table_name))
        except sqlite3.OperationalError:
            flash("Table already exists!", "error")
    
    return render_template_string(STYLE + """
        <div class="container">
            <h1>Create Table</h1>
            <form method="post">
                <input type="text" name="table_name" required placeholder="Table name">
                <div id="columns">
                    <input type="text" name="columns[]" required placeholder="Column name">
                </div>
                <button type="button" onclick="addColumn()">Add Column</button>
                <button type="submit">Create Table</button>
            </form>
        </div>
        <script>
            function addColumn() {
                let div = document.createElement("div");
                div.innerHTML = '<input type="text" name="columns[]" required placeholder="Column name">';
                document.getElementById("columns").appendChild(div);
            }
        </script>
    """)

@app.route("/table/<name>", methods=["GET", "POST"])
def view_table(name):
    if not session.get("DATABASE"):
        return redirect(url_for("home"))

    db = get_db()

    if request.method == "POST":
        columns = [col for col in request.form if col != "table_name"]
        values = [request.form[col] for col in columns]

        try:
            placeholders = ", ".join(["?" for _ in values])
            column_names = ", ".join(columns)
            db.execute(f"INSERT INTO {name} ({column_names}) VALUES ({placeholders})", values)
            db.commit()
        except sqlite3.OperationalError:
            flash("Failed to insert data!", "error")

        return redirect(url_for("view_table", name=name))

    try:
        rows = db.execute(f"SELECT * FROM {name}").fetchall()
        columns = [desc[1] for desc in db.execute(f"PRAGMA table_info({name})") if desc[1] != "id"]
    except sqlite3.OperationalError:
        return redirect(url_for("home"))

    return render_template_string(STYLE + """
        <div class="container">
            <h1>Table: {{ name }}</h1>
            <form method="post">
                {% for col in columns %}
                    <input type="text" name="{{ col }}" placeholder="{{ col }}" required>
                {% endfor %}
                <button type="submit">Add Row</button>
            </form>
            <table>
                <tr>
                    <th>ID</th>
                    {% for col in columns %}
                        <th>{{ col }}</th>
                    {% endfor %}
                    <th>Actions</th>
                </tr>
                {% for row in rows %}
                    <tr>
                        <td>{{ row['id'] }}</td>
                        {% for col in columns %}
                            <td>{{ row[col] }}</td>
                        {% endfor %}
                        <td>
                            <a href="{{ url_for('edit_row', name=name, row_id=row['id']) }}">Edit</a> |
                            <a href="{{ url_for('delete_row', name=name, row_id=row['id']) }}">Delete</a>
                        </td>
                    </tr>
                {% endfor %}
            </table>
        </div>
    """, name=name, rows=rows, columns=columns)

@app.route("/delete/<name>/<int:row_id>")
def delete_row(name, row_id):
    db = get_db()
    db.execute(f"DELETE FROM {name} WHERE id=?", (row_id,))
    db.commit()
    return redirect(url_for("view_table", name=name))

@app.route("/edit/<name>/<int:row_id>", methods=["GET", "POST"])
def edit_row(name, row_id):
    db = get_db()
    row = db.execute(f"SELECT * FROM {name} WHERE id=?", (row_id,)).fetchone()
    
    if not row:
        flash("Row not found!", "error")
        return redirect(url_for("view_table", name=name))
    
    columns = [desc[1] for desc in db.execute(f"PRAGMA table_info({name})") if desc[1] != "id"]

    if request.method == "POST":
        values = [request.form[col] for col in columns]
        update_stmt = ", ".join([f"{col}=?" for col in columns])
        db.execute(f"UPDATE {name} SET {update_stmt} WHERE id=?", values + [row_id])
        db.commit()
        return redirect(url_for("view_table", name=name))

    return render_template_string(STYLE + """
        <div class="container">
            <h1>Edit Row in {{ name }}</h1>
            <form method="post">
                {% for col in columns %}
                    <label>{{ col }}</label>
                    <input type="text" name="{{ col }}" value="{{ row[col] }}" required>
                {% endfor %}
                <button type="submit">Save Changes</button>
            </form>
            <a href="{{ url_for('view_table', name=name) }}">Back</a>
        </div>
    """, name=name, row=row, columns=columns)
    
if __name__ == "__main__":
    app.run()