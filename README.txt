SCHOOL BUS TRACKING MANAGEMENT SYSTEM
======================================

Stack: HTML, CSS, JavaScript, Python/Flask, MySQL.
Features: admin login, vehicle registration, driver profiles, routes, student records,
student-to-bus allocation, demo coordinates, map display, JSON APIs.

IMPORTANT ABOUT TRACKING
------------------------
This project supports manually entered demonstration coordinates and displays them on a map.
It does NOT automatically track a real bus. Genuine live tracking requires a GPS-enabled
device or a driver's phone to send location coordinates to a secured API with permission.

SETUP (Windows + VS Code)
-------------------------
1. Start your MySQL server.
2. Open MySQL Workbench and connect to your local server.
3. Open database.sql and execute the entire script.
4. Open this folder in VS Code.
5. Open Terminal > New Terminal.
6. Install packages:
      python -m pip install -r requirements.txt
7. Set database settings in your terminal if needed. Default config is:
      host=localhost, user=root, password empty, database=school_bus_tracking
   If your MySQL root password is not empty, set DB_PASSWORD in the terminal:
      PowerShell: $env:DB_PASSWORD="your_mysql_password"
   Optional:
      $env:DB_HOST="localhost"
      $env:DB_USER="root"
      $env:DB_NAME="school_bus_tracking"
8. Create the admin account:
      python seed_admin.py
   Enter your MySQL root password when prompted, then create an admin login password.
   Note: if you use DB_PASSWORD environment variable, seed_admin.py still prompts for the
   MySQL password directly.
9. Start the website:
      python app.py
10. Open the local address printed in the terminal (usually http://127.0.0.1:5000).

FIRST DEMO
----------
1. Log in with the admin email and password created in step 8.
2. Add a bus, driver, route and student.
3. Open Student Allocation and assign the student to a bus and route.
4. Open Bus Tracking and enter sample coordinates for the bus.
   Example coordinates for a demo marker: latitude 20.2961, longitude 85.8245.
   These are example coordinates around Bhubaneswar, not live bus data.
5. The map shows the saved demonstration location.
6. API endpoints after login:
      /api/buses
      /api/locations

TROUBLESHOOTING
---------------
- "Access denied": check your MySQL username/password.
- "Unknown database": execute database.sql in Workbench.
- "ModuleNotFoundError": run python -m pip install -r requirements.txt.
- "Can't connect to MySQL": make sure the MySQL server service is running.
- If a bus cannot be deleted, it may be referenced by an allocation. Remove dependent
  records first (the current UI keeps deletion conservative).

SECURITY NOTES
--------------
- Passwords are stored as hashes.
- Change SECRET_KEY before any deployment.
- This is a student prototype. Do not deploy publicly with debug mode enabled.
- Admin account creation is done separately with seed_admin.py; public registration is
  intentionally not exposed so visitors cannot make themselves administrators.
