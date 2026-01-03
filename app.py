from flask import Flask, render_template, request, redirect, session, send_file
from supabase import create_client
from datetime import datetime, date
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_type = request.form["login_type"]

        if login_type == "admin":
            if request.form["username"] == "admin" and request.form["password"] == "admin123":
                session["admin"] = True
                return redirect("/admin")
            return "Invalid admin login"

        res = supabase.table("stores") \
            .select("*") \
            .eq("username", request.form["username"]) \
            .eq("password", request.form["password"]) \
            .eq("active", True) \
            .execute()

        if res.data:
            session["store_id"] = res.data[0]["id"]
            return redirect("/staff")

        return "Invalid login"

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        supabase.table("stores").insert({
            "username": request.form["username"],
            "password": request.form["password"],
            "active": True
        }).execute()
        return redirect("/")
    return render_template("register.html")

@app.route("/staff", methods=["GET", "POST"])
def staff():
    if "store_id" not in session:
        return redirect("/")

    store_id = session["store_id"]

    if request.method == "POST":
        supabase.table("staff").insert({
            "store_id": store_id,
            "staff_name": request.form["staff_name"],
            "staff_type": request.form["staff_type"],
            "salary_type": request.form["salary_type"],
            "salary_amount": request.form["salary_amount"]
        }).execute()

    staff = supabase.table("staff").select("*").eq("store_id", store_id).execute().data
    return render_template("staff.html", staff=staff)

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if "store_id" not in session:
        return redirect("/")

    store_id = session["store_id"]
    today = request.args.get("date") or date.today().isoformat()

    staff = supabase.table("staff").select("*").eq("store_id", store_id).execute().data

    if request.method == "POST":
        for s in staff:
            in_time = request.form.get(f"in_{s['id']}")
            out_time = request.form.get(f"out_{s['id']}")
            status = request.form.get(f"status_{s['id']}", "Absent")

            hours = 0
            if in_time and out_time:
                t1 = datetime.strptime(in_time, "%H:%M")
                t2 = datetime.strptime(out_time, "%H:%M")
                hours = round((t2 - t1).seconds / 3600, 2)

            supabase.table("attendance").upsert({
                "store_id": store_id,
                "staff_id": s["id"],
                "date": today,
                "status": status,
                "in_time": in_time,
                "out_time": out_time,
                "hours": hours
            }).execute()

        return redirect(f"/attendance?date={today}")

    return render_template("attendance.html", staff=staff, today=today)

@app.route("/download")
def download():
    rows = supabase.table("attendance").select("*").execute().data
    df = pd.DataFrame(rows)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="attendance.xlsx")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
