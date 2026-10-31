import os
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Please set the SECRET_KEY environment variable.")
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3307")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "school_bus_tracking"),
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def query_all(sql, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None

def execute(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()

@app.context_processor
def inject_globals():
    return {"current_user": session.get("user")}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if session["user"].get("role") != "admin":
            flash("Admin access is required for that page.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    try:
        stats = {
            "buses": query_one("SELECT COUNT(*) AS n FROM buses")["n"],
            "drivers": query_one("SELECT COUNT(*) AS n FROM drivers")["n"],
            "students": query_one("SELECT COUNT(*) AS n FROM students")["n"],
            "routes": query_one("SELECT COUNT(*) AS n FROM routes")["n"],
        }
    except Error:
        stats = {"buses": 0, "drivers": 0, "students": 0, "routes": 0}
    return render_template("index.html", stats=stats)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            user = query_one("SELECT id, name, email, password_hash, role FROM users WHERE email=%s", (email,))
        except Error:
            flash("Database is not ready. Import database.sql and check database settings.", "danger")
            return render_template("login.html")
        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
            flash("Welcome back, " + user["name"] + "!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "buses": query_one("SELECT COUNT(*) AS n FROM buses")["n"],
        "drivers": query_one("SELECT COUNT(*) AS n FROM drivers")["n"],
        "students": query_one("SELECT COUNT(*) AS n FROM students")["n"],
        "routes": query_one("SELECT COUNT(*) AS n FROM routes")["n"],
    }
    recent = query_all("""SELECT l.id, b.bus_number, l.latitude, l.longitude, l.updated_at
                          FROM bus_locations l JOIN buses b ON b.id=l.bus_id
                          ORDER BY l.updated_at DESC LIMIT 5""")
    return render_template("dashboard.html", stats=stats, recent=recent)
@app.route("/reports")
@login_required
def reports():
    stats = {
        "buses": query_one("SELECT COUNT(*) AS n FROM buses")["n"],
        "drivers": query_one("SELECT COUNT(*) AS n FROM drivers")["n"],
        "students": query_one("SELECT COUNT(*) AS n FROM students")["n"],
        "routes": query_one("SELECT COUNT(*) AS n FROM routes")["n"],
        "allocations": query_one("SELECT COUNT(*) AS n FROM allocations")["n"],
    }

    rows = query_all("""
        SELECT s.student_code, s.name AS student_name,
               b.bus_number, r.name AS route_name,
               r.start_point, r.end_point
        FROM allocations a
        JOIN students s ON s.id = a.student_id
        JOIN buses b ON b.id = a.bus_id
        JOIN routes r ON r.id = a.route_id
        ORDER BY s.name
    """)

    return render_template("reports.html", stats=stats, allocations=rows)

@app.route("/buses", methods=["GET", "POST"])
@admin_required
def buses():
    if request.method == "POST":
        bus_number = request.form.get("bus_number", "").strip().upper()
        model = request.form.get("model", "").strip()
        capacity = request.form.get("capacity", "0").strip()
        if not bus_number or not capacity.isdigit() or int(capacity) < 1:
            flash("Enter a bus number and a positive seating capacity.", "danger")
        else:
            try:
                execute("INSERT INTO buses (bus_number, model, capacity) VALUES (%s,%s,%s)",
                        (bus_number, model or None, int(capacity)))
                flash("Bus registered successfully.", "success")
                return redirect(url_for("buses"))
            except Error as e:
                flash("Could not add bus. Check whether the bus number already exists.", "danger")
    rows = query_all("SELECT * FROM buses ORDER BY id DESC")
    return render_template("buses.html", buses=rows)

@app.route("/buses/delete/<int:bus_id>", methods=["POST"])
@admin_required
def delete_bus(bus_id):
    try:
        execute("DELETE FROM buses WHERE id=%s", (bus_id,))
        flash("Bus deleted if it was not assigned to another record.", "success")
    except Error:
        flash("This bus is assigned to another record. Remove its allocations/locations first.", "danger")
    return redirect(url_for("buses"))

@app.route("/buses/edit/<int:bus_id>", methods=["GET", "POST"])
@admin_required
def edit_bus(bus_id):
    bus = query_one("SELECT * FROM buses WHERE id=%s", (bus_id,))

    if not bus:
        flash("Bus not found.", "danger")
        return redirect(url_for("buses"))

    if request.method == "POST":
        bus_number = request.form.get("bus_number", "").strip().upper()
        model = request.form.get("model", "").strip()
        capacity = request.form.get("capacity", "").strip()

        if not bus_number or not capacity.isdigit() or int(capacity) < 1:
            flash("Enter a bus number and a positive seating capacity.", "danger")
        else:
            try:
                execute(
                    "UPDATE buses SET bus_number=%s, model=%s, capacity=%s WHERE id=%s",
                    (bus_number, model or None, int(capacity), bus_id)
                )
                flash("Bus updated successfully.", "success")
                return redirect(url_for("buses"))
            except Error:
                flash("Could not update bus. Check whether the bus number already exists.", "danger")

    return render_template("edit_bus.html", bus=bus)
@app.route("/drivers", methods=["GET", "POST"])
@admin_required
def drivers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        license_no = request.form.get("license_no", "").strip()
        if not name or not phone or not license_no:
            flash("All driver fields are required.", "danger")
        else:
            try:
                execute("INSERT INTO drivers (name, phone, license_no) VALUES (%s,%s,%s)", (name, phone, license_no))
                flash("Driver profile added.", "success")
                return redirect(url_for("drivers"))
            except Error:
                flash("Could not add driver. Phone or licence number may already exist.", "danger")
    rows = query_all("SELECT * FROM drivers ORDER BY id DESC")
    return render_template("drivers.html", drivers=rows)

@app.route("/drivers/edit/<int:driver_id>", methods=["GET", "POST"])
@admin_required
def edit_driver(driver_id):
    driver = query_one(
        "SELECT * FROM drivers WHERE id=%s", (driver_id,)
    )

    if not driver:
        flash("Driver not found.", "danger")
        return redirect(url_for("drivers"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        license_no = request.form.get("license_no", "").strip()

        if not name or not phone or not license_no:
            flash("All driver fields are required.", "danger")
        else:
            try:
                execute(
                    """UPDATE drivers
                    SET name=%s, phone=%s, license_no=%s
                    WHERE id=%s""",
                    (name, phone, license_no, driver_id)
                )
                flash("Driver updated successfully.", "success")
                return redirect(url_for("drivers"))
            except Error:
                flash(
                    "Could not update driver. Phone or licence number may already exist.",
                    "danger"
                )

    return render_template("edit_driver.html", driver=driver)


@app.route("/drivers/delete/<int:driver_id>", methods=["POST"])
@admin_required
def delete_driver(driver_id):
    try:
        execute(
            "DELETE FROM drivers WHERE id=%s",
            (driver_id,)
        )
        flash("Driver deleted successfully.", "success")
    except Error:
        flash(
            "Cannot delete this driver because it may be assigned to a bus.",
            "danger"
        )

    return redirect(url_for("drivers"))
@app.route("/routes", methods=["GET", "POST"])
@admin_required
def routes():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_point = request.form.get("start_point", "").strip()
        end_point = request.form.get("end_point", "").strip()
        stops = request.form.get("stops", "").strip()
        if not name or not start_point or not end_point:
            flash("Route name, starting point, and destination are required.", "danger")
        else:
            try:
                execute("INSERT INTO routes (name, start_point, end_point, stops) VALUES (%s,%s,%s,%s)",
                        (name, start_point, end_point, stops or None))
                flash("Route created.", "success")
                return redirect(url_for("routes"))
            except Error:
                flash("Could not create route.", "danger")
    rows = query_all("SELECT * FROM routes ORDER BY id DESC")
    return render_template("routes.html", routes=rows)

@app.route("/routes/edit/<int:route_id>", methods=["GET", "POST"])
@admin_required
def edit_route(route_id):
    route = query_one("SELECT * FROM routes WHERE id=%s", (route_id,))

    if not route:
        flash("Route not found.", "danger")
        return redirect(url_for("routes"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_point = request.form.get("start_point", "").strip()
        end_point = request.form.get("end_point", "").strip()
        stops = request.form.get("stops", "").strip()

        if not name or not start_point or not end_point:
            flash("Route name, starting point, and destination are required.", "danger")
        else:
            try:
                execute(
                    """UPDATE routes
                    SET name=%s, start_point=%s, end_point=%s, stops=%s
                    WHERE id=%s""",
                    (name, start_point, end_point, stops or None, route_id)
                )
                flash("Route updated successfully.", "success")
                return redirect(url_for("routes"))
            except Error:
                flash("Could not update route.", "danger")

    return render_template("edit_route.html", route=route)


@app.route("/routes/delete/<int:route_id>", methods=["POST"])
@admin_required
def delete_route(route_id):
    try:
        execute("DELETE FROM routes WHERE id=%s", (route_id,))
        flash("Route deleted successfully.", "success")
    except Error:
        flash(
            "Cannot delete this route because it may be assigned to another record.",
            "danger"
        )

    return redirect(url_for("routes"))

@app.route("/students", methods=["GET", "POST"])
@admin_required
def students():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_code = request.form.get("student_code", "").strip().upper()
        class_name = request.form.get("class_name", "").strip()
        pickup = request.form.get("pickup_point", "").strip()
        if not name or not student_code or not class_name:
            flash("Name, student ID, and class are required.", "danger")
        else:
            try:
                execute("INSERT INTO students (name, student_code, class_name, pickup_point) VALUES (%s,%s,%s,%s)",
                        (name, student_code, class_name, pickup or None))
                flash("Student added.", "success")
                return redirect(url_for("students"))
            except Error:
                flash("Could not add student. Student ID may already exist.", "danger")
    rows = query_all("SELECT * FROM students ORDER BY id DESC")
    return render_template("students.html", students=rows)

@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@admin_required
def edit_student(student_id):
    student = query_one("SELECT * FROM students WHERE id=%s", (student_id,))

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_code = request.form.get("student_code", "").strip().upper()
        class_name = request.form.get("class_name", "").strip()
        pickup = request.form.get("pickup_point", "").strip()

        if not name or not student_code or not class_name:
            flash("Name, student ID, and class are required.", "danger")
        else:
            try:
                execute(
                    """UPDATE students
                    SET name=%s, student_code=%s, class_name=%s, pickup_point=%s
                    WHERE id=%s""",
                    (name, student_code, class_name, pickup or None, student_id)
                )
                flash("Student updated successfully.", "success")
                return redirect(url_for("students"))
            except Error:
                flash("Could not update student. Student ID may already exist.", "danger")

    return render_template("edit_student.html", student=student)


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@admin_required
def delete_student(student_id):
    try:
        execute("DELETE FROM students WHERE id=%s", (student_id,))
        flash("Student deleted successfully.", "success")
    except Error:
        flash("Cannot delete this student because they may be linked to another record.", "danger")

    return redirect(url_for("students"))

@app.route("/allocations", methods=["GET", "POST"])
@admin_required
def allocations():
    if request.method == "POST":
        student_id = request.form.get("student_id", "")
        bus_id = request.form.get("bus_id", "")
        route_id = request.form.get("route_id", "")
        if not (student_id.isdigit() and bus_id.isdigit() and route_id.isdigit()):
            flash("Select a student, bus, and route.", "danger")
        else:
            try:
                execute("""INSERT INTO allocations (student_id, bus_id, route_id)
                           VALUES (%s,%s,%s)
                           ON DUPLICATE KEY UPDATE bus_id=VALUES(bus_id), route_id=VALUES(route_id)""",
                        (int(student_id), int(bus_id), int(route_id)))
                flash("Student bus allocation saved.", "success")
                return redirect(url_for("allocations"))
            except Error:
                flash("Could not save allocation. Check the selected records.", "danger")
    students_list = query_all("SELECT * FROM students ORDER BY name")
    buses_list = query_all("SELECT * FROM buses ORDER BY bus_number")
    routes_list = query_all("SELECT * FROM routes ORDER BY name")
    rows = query_all("""SELECT a.id, s.name AS student_name, s.student_code, b.bus_number, r.name AS route_name
                        FROM allocations a JOIN students s ON s.id=a.student_id
                        JOIN buses b ON b.id=a.bus_id JOIN routes r ON r.id=a.route_id
                        ORDER BY a.id DESC""")
    return render_template("allocations.html", allocations=rows, students=students_list, buses=buses_list, routes=routes_list)
@app.route("/allocations/delete/<int:allocation_id>", methods=["POST"])
@admin_required
def delete_allocation(allocation_id):
    try:
        execute(
            "DELETE FROM allocations WHERE id = %s",
            (allocation_id,)
        )
        flash("Student allocation deleted successfully.", "success")
    except Error:
        flash("Could not delete this allocation.", "danger")

    return redirect(url_for("allocations"))

@app.route("/tracking", methods=["GET", "POST"])
@login_required
def tracking():
    buses_list = query_all("SELECT * FROM buses ORDER BY bus_number")
    if request.method == "POST":
        if session["user"]["role"] != "admin":
            flash("Only an admin can update demo coordinates.", "danger")
            return redirect(url_for("tracking"))
        bus_id = request.form.get("bus_id", "")
        lat = request.form.get("latitude", "")
        lon = request.form.get("longitude", "")
        try:
            lat_f, lon_f = float(lat), float(lon)
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                raise ValueError()
            execute("""INSERT INTO bus_locations (bus_id, latitude, longitude, source)
                       VALUES (%s,%s,%s,'manual demo')
                       ON DUPLICATE KEY UPDATE latitude=VALUES(latitude), longitude=VALUES(longitude),
                       source='manual demo', updated_at=CURRENT_TIMESTAMP""", (int(bus_id), lat_f, lon_f))
            flash("Demo location updated. This is not live GPS unless a GPS device/app sends coordinates.", "success")
            return redirect(url_for("tracking"))
        except (ValueError, TypeError, Error):
            flash("Enter a valid bus and coordinates (latitude -90 to 90, longitude -180 to 180).", "danger")
    locations = query_all("""SELECT b.bus_number, b.id AS bus_id, l.latitude, l.longitude, l.source, l.updated_at
                             FROM buses b LEFT JOIN bus_locations l ON b.id=l.bus_id
                             ORDER BY b.bus_number""")
    return render_template("tracking.html", buses=buses_list, locations=locations)

@app.route("/api/buses", methods=["GET"])
@login_required
def api_buses():
    rows = query_all("""SELECT b.id, b.bus_number, b.model, b.capacity,
                        l.latitude, l.longitude, l.updated_at
                        FROM buses b LEFT JOIN bus_locations l ON b.id=l.bus_id
                        ORDER BY b.bus_number""")
    return jsonify({"count": len(rows), "buses": rows})

@app.route("/api/locations", methods=["GET"])
@login_required
def api_locations():
    rows = query_all("""SELECT b.bus_number, l.latitude, l.longitude, l.updated_at
                        FROM bus_locations l JOIN buses b ON b.id=l.bus_id""")
    return jsonify({"count": len(rows), "locations": rows})

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The page you requested was not found."), 404

@app.errorhandler(500)
def server_error(_):
    return render_template("error.html", code=500, message="Something went wrong. Check the terminal for details."), 500

if __name__ == "__main__":
    app.run(debug=True)
