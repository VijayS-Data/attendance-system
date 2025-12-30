from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, date
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "attendance_secret"

DB = "attendance.db"
OUTPUT = "monthly_attendance.xlsx"
TEMP = "monthly_temp.xlsx"
LATE_AFTER = "09:15"


def get_db():
    return sqlite3.connect(DB)


# ---------- CREATE TABLES ----------
conn = get_db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    active INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER,
    staff_name TEXT,
    staff_type TEXT,
    salary_type TEXT,
    salary_amount REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    store_id INTEGER,
    staff_id INTEGER,
    date TEXT,
    status TEXT,
    in_time TEXT,
    out_time TEXT,
    hours REAL,
    late INTEGER,
    PRIMARY KEY (store_id, staff_id, date)
)
""")

conn.commit()
conn.close()


# ---------- LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_type = request.form["login_type"]

        # ADMIN
        if login_type == "admin":
            if request.form["username"] == "admin" and request.form["password"] == "admin123":
                session.clear()
                session["admin"] = True
                return redirect("/admin/dashboard")
            return "Invalid admin login"

        # STORE
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM stores
            WHERE username=? AND password=? AND active=1
        """, (request.form["username"], request.form["password"]))
        row = cur.fetchone()
        conn.close()

        if row:
            session.clear()
            session["store_id"] = row[0]
            return redirect("/staff")

        return "Invalid store login"

    return render_template("login.html")


# ---------- REGISTER STORE ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO stores (username, password) VALUES (?, ?)",
            (request.form["username"], request.form["password"])
        )
        conn.commit()
        conn.close()
        return redirect("/")

    return render_template("register.html")


# ---------- STAFF ----------
@app.route("/staff", methods=["GET", "POST"])
def staff():
    if "store_id" not in session:
        return redirect("/")

    store_id = session["store_id"]
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            INSERT INTO staff
            (store_id, staff_name, staff_type, salary_type, salary_amount)
            VALUES (?, ?, ?, ?, ?)
        """, (
            store_id,
            request.form["staff_name"],
            request.form["staff_type"],
            request.form["salary_type"],
            request.form["salary_amount"]
        ))
        conn.commit()

    cur.execute("""
        SELECT id, staff_name, staff_type, salary_type, salary_amount
        FROM staff WHERE store_id=?
    """, (store_id,))
    staff = cur.fetchall()
    conn.close()

    return render_template("staff.html", staff=staff)


@app.route("/remove_staff/<int:id>")
def remove_staff(id):
    if "store_id" not in session:
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/staff")


# ---------- ATTENDANCE ----------
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if "store_id" not in session:
        return redirect("/")

    store_id = session["store_id"]
    selected_date = request.args.get("date")
    today = selected_date if selected_date else date.today().strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, staff_name FROM staff WHERE store_id=?", (store_id,))
    staff = cur.fetchall()

    if request.method == "POST":
        for s in staff:
            status = request.form.get(f"status_{s[0]}")
            in_time = request.form.get(f"in_{s[0]}")
            out_time = request.form.get(f"out_{s[0]}")

            hours = 0
            late = 0
            if status == "Present" and in_time and out_time:
                t1 = datetime.strptime(in_time, "%H:%M")
                t2 = datetime.strptime(out_time, "%H:%M")
                hours = round((t2 - t1).seconds / 3600, 2)
                if in_time > LATE_AFTER:
                    late = 1

            cur.execute("""
                INSERT OR REPLACE INTO attendance
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (store_id, s[0], today, status, in_time, out_time, hours, late))

        conn.commit()

        # ---------- EXCEL OUTPUT (FINAL FORMAT) ----------
        df = pd.read_sql_query("""
            SELECT
                st.username AS Store,
                sf.staff_name AS Staff,
                strftime('%Y-%m', a.date) AS Month,

                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS PresentDays,
                SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) AS AbsentDays,

                ROUND(SUM(a.hours), 2) AS TotalHours,
                COUNT(a.date) AS TotalDays,

                CASE
                    WHEN sf.salary_type='daily'
                    THEN
                        SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)
                        * sf.salary_amount
                    ELSE
                        ROUND(SUM(a.hours) * sf.salary_amount, 2)
                END AS Salary

            FROM attendance a
            JOIN staff sf ON a.staff_id = sf.id
            JOIN stores st ON a.store_id = st.id
            GROUP BY st.username, sf.staff_name, Month
            ORDER BY st.username, sf.staff_name
        """, conn)

        conn.close()

        df.to_excel(TEMP, index=False)
        if os.path.exists(OUTPUT):
            os.remove(OUTPUT)
        os.rename(TEMP, OUTPUT)

        return redirect(f"/attendance?date={today}&success=1")

    conn.close()
    return render_template("attendance.html", staff=staff, today=today)


# ---------- ADMIN ----------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, active FROM stores")
    stores = cur.fetchall()
    conn.close()

    return render_template("admin_dashboard.html", stores=stores)


@app.route("/admin/toggle/<int:id>")
def toggle_store(id):
    if not session.get("admin"):
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE stores
        SET active = CASE WHEN active=1 THEN 0 ELSE 1 END
        WHERE id=?
    """, (id,))
    conn.commit()
    conn.close()
    return redirect("/admin/dashboard")


@app.route("/admin/reset/<int:id>", methods=["GET", "POST"])
def admin_reset(id):
    if not session.get("admin"):
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            "UPDATE stores SET password=? WHERE id=?",
            (request.form["password"], id)
        )
        conn.commit()
        conn.close()
        return redirect("/admin/dashboard")

    cur.execute("SELECT username FROM stores WHERE id=?", (id,))
    store = cur.fetchone()
    conn.close()

    return render_template("admin_reset.html", store=store, store_id=id)


@app.route("/admin/reset_attendance", methods=["POST"])
def admin_reset_attendance():
    if not session.get("admin"):
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance")
    conn.commit()
    conn.close()

    if os.path.exists(OUTPUT):
        os.remove(OUTPUT)

    return redirect("/admin/dashboard")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

