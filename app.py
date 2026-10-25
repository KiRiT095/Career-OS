from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx", "txt"}
ROADMAP_STAGES = [
    ("DSA Foundations", "Arrays, strings, linked lists and problem-solving", "DSA"),
    ("Web Development", "Build frontend and backend fundamentals", "Web Development"),
    ("System Design Basics", "Learn databases, APIs and core design concepts", "System Design"),
    ("Projects", "Build, document and publish practical projects", "Projects"),
    ("Placement Preparation", "Resume, aptitude and interview preparation", "Placement Prep"),
]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("CAREEROS_SECRET", "careeros-local-demo-secret-change-me"),
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        DATABASE=os.environ.get("CAREEROS_DB", str(BASE_DIR / "careeros.db")),
        UPLOAD_FOLDER=str(BASE_DIR / "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    class HybridRow(dict):
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return super().__getitem__(key)

    class PostgresConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, query, params=()):
            query = query.replace("?", "%s")
            return self.connection.execute(query, params)

        def executemany(self, query, params):
            query = query.replace("?", "%s")
            return self.connection.cursor().executemany(query, params)

        def executescript(self, script):
            for statement in script.split(";"):
                if statement.strip():
                    self.connection.execute(statement)

        def commit(self):
            self.connection.commit()

        def rollback(self):
            self.connection.rollback()

        def close(self):
            self.connection.close()


    def connect_db():
        database_url = app.config.get("DATABASE_URL")

        if database_url:
            import psycopg


            def row_factory(cursor):
                if cursor.description is None:
                    return None

                columns = [column.name for column in cursor.description]

                def build_row(values):
                    converted = [
                        value.isoformat(sep=" ") if isinstance(value, datetime) else value
                        for value in values
                    ]
                    return HybridRow(zip(columns, converted))

                return build_row


            connection = psycopg.connect(
                database_url,
                row_factory=row_factory
            )
            return PostgresConnection(connection)

        if os.environ.get("VERCEL"):
            raise RuntimeError(
                "DATABASE_URL is missing. Configure PostgreSQL in Vercel."
            )

        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


    def init_db():
        db = connect_db()
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                academic_year TEXT NOT NULL DEFAULT 'Second Year',
                career_track TEXT NOT NULL DEFAULT 'Software Developer',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS roadmap_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                stage TEXT NOT NULL,
                description TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
                UNIQUE(user_id, stage)
            );
            CREATE TABLE IF NOT EXISTS dsa_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic TEXT NOT NULL,
                problem TEXT NOT NULL,
                solved INTEGER NOT NULL DEFAULT 1,
                solved_on TEXT NOT NULL DEFAULT CURRENT_DATE
            );
            CREATE TABLE IF NOT EXISTS cgpa_records (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                current_cgpa REAL NOT NULL DEFAULT 0,
                target_cgpa REAL NOT NULL DEFAULT 9,
                completed_semesters INTEGER NOT NULL DEFAULT 4,
                total_semesters INTEGER NOT NULL DEFAULT 8,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Applied',
                deadline TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS hackathons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                organizer TEXT NOT NULL,
                deadline TEXT,
                link TEXT DEFAULT '',
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS hackathon_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                hackathon_id INTEGER NOT NULL REFERENCES hackathons(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'Interested',
                UNIQUE(user_id, hackathon_id)
            );
            CREATE TABLE IF NOT EXISTS certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                track TEXT NOT NULL DEFAULT 'General',
                link TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS user_certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                certification_id INTEGER NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_on TEXT,
                UNIQUE(user_id, certification_id)
            );
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT DEFAULT '',
                url TEXT DEFAULT '',
                keywords TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                careers_url TEXT DEFAULT '',
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS resume_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT DEFAULT '',
                resume_text TEXT DEFAULT '',
                job_description TEXT DEFAULT '',
                skills TEXT DEFAULT '',
                projects_added INTEGER NOT NULL DEFAULT 0,
                certifications_added INTEGER NOT NULL DEFAULT 0,
                experience_added INTEGER NOT NULL DEFAULT 0,
                ats_score INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """

        if app.config.get("DATABASE_URL"):
            schema = schema.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "SERIAL PRIMARY KEY"
            )
            schema = schema.replace(
                "solved_on TEXT NOT NULL DEFAULT CURRENT_DATE",
                "solved_on TEXT NOT NULL DEFAULT (CURRENT_DATE::text)"
            )
            schema = schema.replace(
                "DEFAULT CURRENT_TIMESTAMP",
                "DEFAULT (CURRENT_TIMESTAMP::text)"
            )

        if app.config.get("DATABASE_URL"):
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
        else:
            db.executescript(schema)

        seed_db(db)
        db.commit()
        db.close()

    def seed_db(db):
        db.execute("INSERT INTO users(name,email,password_hash,role,academic_year,career_track) VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                   ("Demo Student", "student@careeros.local", generate_password_hash("student123"), "student", "Third Year", "Software Developer"))
        db.execute("INSERT INTO users(name,email,password_hash,role,academic_year,career_track) VALUES(?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                   ("CareerOS Admin", "admin@careeros.local", generate_password_hash("admin123"), "admin", "Final Year", "Admin"))
        student = db.execute("SELECT id FROM users WHERE email=?", ("student@careeros.local",)).fetchone()["id"]
        for stage, desc, _ in ROADMAP_STAGES:
            count = db.execute("SELECT COUNT(*) AS n FROM roadmap_progress WHERE user_id=? AND stage=?", (student, stage)).fetchone()["n"]
            if count == 0:
                initial = {"DSA Foundations": 68, "Web Development": 45, "System Design Basics": 20, "Projects": 35, "Placement Preparation": 10}.get(stage, 0)
                db.execute("INSERT INTO roadmap_progress(user_id,stage,description,progress) VALUES(?,?,?,?)", (student, stage, desc, initial))
        db.execute("INSERT INTO cgpa_records(user_id,current_cgpa,target_cgpa,completed_semesters,total_semesters) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING", (student, 7.8, 9.0, 4, 8))
        if db.execute("SELECT COUNT(*) FROM dsa_logs WHERE user_id=?", (student,)).fetchone()[0] == 0:
            db.executemany("INSERT INTO dsa_logs(user_id,topic,problem) VALUES(?,?,?)", [
                (student, "Arrays", "Two Sum"), (student, "Arrays", "Maximum Subarray"),
                (student, "Linked List", "Reverse Linked List"), (student, "Trees", "Level Order Traversal"),
                (student, "Strings", "Valid Anagram"), (student, "Arrays", "Best Time to Buy and Sell Stock"),
            ])
        if db.execute("SELECT COUNT(*) FROM applications WHERE user_id=?", (student,)).fetchone()[0] == 0:
            db.executemany("INSERT INTO applications(user_id,company,role,status,deadline,notes) VALUES(?,?,?,?,?,?)", [
                (student, "TCS", "Ninja / Digital", "Applied", "2026-11-10", "Prepare aptitude and coding basics"),
                (student, "Accenture", "Software Engineering Intern", "Preparing", "2026-11-18", "Review arrays and SQL"),
                (student, "Google", "Software Engineering Intern", "Interested", "2026-12-01", "Check eligibility before applying"),
            ])
        if db.execute("SELECT COUNT(*) FROM hackathons").fetchone()[0] == 0:
            db.executemany("INSERT INTO hackathons(title,organizer,deadline,link,description) VALUES(?,?,?,?,?)", [
                ("Smart India Hackathon", "Government of India", "2026-11-15", "https://www.sih.gov.in/", "Team-based problem-solving and prototype development."),
                ("NASA Space Apps Challenge", "NASA", "2026-10-31", "https://www.spaceappschallenge.org/", "Build solutions using open data."),
                ("Hack the Mountains", "Community Hackathon", "2026-11-22", "https://hackthemountains.tech/", "A student-friendly hackathon experience."),
            ])
        if db.execute("SELECT COUNT(*) FROM certifications").fetchone()[0] == 0:
            db.executemany("INSERT INTO certifications(name,provider,track,link) VALUES(?,?,?,?)", [
                ("AWS Cloud Practitioner", "Amazon Web Services", "Cloud", "https://aws.amazon.com/certification/"),
                ("Google IT Support", "Google", "IT / Support", "https://grow.google/certificates/"),
                ("Java Programming Basics", "Oracle / Learning Resources", "Programming", "https://dev.java/learn/"),
                ("Python Essentials", "Cisco Networking Academy", "Programming", "https://www.netacad.com/"),
            ])
        if db.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
            db.executemany("INSERT INTO resources(title,category,description,url,keywords) VALUES(?,?,?,?,?)", [
                ("DSA Patterns Roadmap", "DSA", "A structured order for learning common data structure patterns.", "https://neetcode.io/roadmap", "arrays trees graphs interview coding"),
                ("Python Official Tutorial", "Programming", "Reference guide for Python syntax and core concepts.", "https://docs.python.org/3/tutorial/", "python programming basics"),
                ("Git & GitHub Basics", "Development", "Learn version control and how to publish projects.", "https://docs.github.com/en/get-started", "git github projects"),
                ("SQL Tutorial", "Database", "Practice SQL queries and relational database concepts.", "https://www.w3schools.com/sql/", "sql database dbms"),
                ("Interview Preparation", "Interview", "Practice common technical and behavioural interview questions.", "https://www.geeksforgeeks.org/interview-preparation/", "interview placement aptitude"),
                ("Resume Writing Guide", "Career", "Checklist for creating a readable, focused resume.", "https://careerservices.fas.harvard.edu/resources/create-a-resume/", "resume cv ats skills projects"),
                ("Web Development Learning Path", "Web Development", "Foundations for HTML, CSS and JavaScript.", "https://developer.mozilla.org/en-US/docs/Learn", "html css javascript frontend"),
                ("System Design Primer", "System Design", "Introductory notes on common system design concepts.", "https://github.com/donnemartin/system-design-primer", "system design backend api"),
            ])
        if db.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
            db.executemany("INSERT INTO companies(name,careers_url,notes) VALUES(?,?,?)", [
                ("TCS", "https://www.tcs.com/careers", "IT services"),
                ("Accenture", "https://www.accenture.com/in-en/careers", "Technology and consulting"),
                ("Infosys", "https://www.infosys.com/careers/", "IT services"),
            ])
        for row in db.execute("SELECT id FROM certifications LIMIT 4").fetchall():
            db.execute("INSERT INTO user_certifications(user_id,certification_id,completed) VALUES(?,?,?) ON CONFLICT DO NOTHING",
                       (student, row["id"], 1 if row["id"] == 2 else 0))
        if db.execute("SELECT COUNT(*) FROM resume_profiles WHERE user_id=?", (student,)).fetchone()[0] == 0:
            sample_text = "Python SQL Flask HTML CSS JavaScript Data Structures Algorithms Git teamwork projects problem solving"
            sample_jd = "Python SQL web development data structures algorithms teamwork communication"
            score = calculate_ats_score(sample_text, sample_jd)
            db.execute("INSERT INTO resume_profiles(user_id,resume_text,job_description,skills,projects_added,certifications_added,experience_added,ats_score) VALUES(?,?,?,?,?,?,?,?)",
                       (student, sample_text, sample_jd, "Python, SQL, Flask, HTML, CSS", 1, 1, 0, score))

    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            db = connect_db()
            g.user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            db.close()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if g.user["role"] != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    @app.context_processor
    def inject_globals():
        return {"today": date.today().isoformat(), "current_year": datetime.now().year}

    @app.route("/")
    def index():
        return redirect(url_for("dashboard" if g.user else "login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            db = connect_db()
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            db.close()
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                flash(f"Welcome back, {user['name'].split()[0]}!", "success")
                return redirect(url_for("dashboard"))
            flash("Email or password is incorrect.", "error")
        return render_template("login.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            academic_year = request.form.get("academic_year", "Second Year")
            career_track = request.form.get("career_track", "Software Developer")
            if not name or not email or len(password) < 6:
                flash("Enter your name and email, and use a password with at least 6 characters.", "error")
                return render_template("register.html")
            db = connect_db()
            try:
                cur = db.execute("INSERT INTO users(name,email,password_hash,academic_year,career_track) VALUES(?,?,?,?,?) RETURNING id",
                                 (name, email, generate_password_hash(password), academic_year, career_track))
                user_id = cur.fetchone()["id"]
                for stage, desc, _ in ROADMAP_STAGES:
                    db.execute("INSERT INTO roadmap_progress(user_id,stage,description,progress) VALUES(?,?,?,0)", (user_id, stage, desc))
                db.execute("INSERT INTO cgpa_records(user_id,current_cgpa,target_cgpa,completed_semesters,total_semesters) VALUES(?,?,?,?,?)", (user_id, 0, 9, 0, 8))
                db.commit()
                session["user_id"] = user_id
                flash("Your CareerOS account is ready. Start by updating your roadmap.", "success")
                return redirect(url_for("dashboard"))
            except Exception as error:
                if not isinstance(error, sqlite3.IntegrityError) and error.__class__.__name__ != "UniqueViolation":
                    raise
                db.rollback()
                flash("That email is already registered.", "error")
            finally:
                db.close()
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = connect_db()
        roadmap = db.execute("SELECT * FROM roadmap_progress WHERE user_id=? ORDER BY id", (g.user["id"],)).fetchall()
        dsa_total = db.execute("SELECT COUNT(*) FROM dsa_logs WHERE user_id=?", (g.user["id"],)).fetchone()[0]
        cgpa = db.execute("SELECT * FROM cgpa_records WHERE user_id=?", (g.user["id"],)).fetchone()
        active_apps = db.execute("SELECT COUNT(*) FROM applications WHERE user_id=? AND status NOT IN ('Rejected','Offer Received')", (g.user["id"],)).fetchone()[0]
        completed_certs = db.execute("SELECT COUNT(*) FROM user_certifications WHERE user_id=? AND completed=1", (g.user["id"],)).fetchone()[0]
        applications = db.execute("SELECT * FROM applications WHERE user_id=? ORDER BY CASE WHEN deadline IS NULL OR deadline='' THEN 1 ELSE 0 END, deadline LIMIT 5", (g.user["id"],)).fetchall()
        events = db.execute("SELECT * FROM hackathons WHERE deadline IS NULL OR deadline >= ? ORDER BY deadline LIMIT 3", (date.today().isoformat(),)).fetchall()
        resources = db.execute("SELECT * FROM resources ORDER BY id LIMIT 4").fetchall()
        avg_progress = round(sum(r["progress"] for r in roadmap) / len(roadmap)) if roadmap else 0
        db.close()
        return render_template("dashboard.html", roadmap=roadmap, dsa_total=dsa_total, cgpa=cgpa,
                               active_apps=active_apps, completed_certs=completed_certs,
                               applications=applications, events=events, resources=resources,
                               avg_progress=avg_progress)

    @app.route("/roadmap", methods=["GET", "POST"])
    @login_required
    def roadmap():
        db = connect_db()
        if request.method == "POST":
            stage_id = request.form.get("stage_id", type=int)
            progress = request.form.get("progress", type=int)
            if progress is None or not 0 <= progress <= 100:
                flash("Progress must be between 0 and 100.", "error")
            else:
                result = db.execute("UPDATE roadmap_progress SET progress=? WHERE id=? AND user_id=?", (progress, stage_id, g.user["id"]))
                if result.rowcount:
                    db.commit()
                    flash("Roadmap progress updated.", "success")
                else:
                    flash("That roadmap stage was not found.", "error")
            db.close()
            return redirect(url_for("roadmap"))
        rows = db.execute("SELECT * FROM roadmap_progress WHERE user_id=? ORDER BY id", (g.user["id"],)).fetchall()
        db.close()
        return render_template("roadmap.html", stages=rows)

    @app.route("/dsa", methods=["GET", "POST"])
    @login_required
    def dsa():
        db = connect_db()
        topics = ["Arrays", "Strings", "Linked List", "Stacks & Queues", "Trees", "Graphs", "Dynamic Programming", "Searching & Sorting", "Other"]
        if request.method == "POST":
            topic = request.form.get("topic", "").strip()
            problem = request.form.get("problem", "").strip()
            if topic not in topics or not problem:
                flash("Choose a topic and enter the problem name.", "error")
            else:
                db.execute("INSERT INTO dsa_logs(user_id,topic,problem) VALUES(?,?,?)", (g.user["id"], topic, problem))
                db.commit()
                flash("Problem added to your DSA tracker.", "success")
            db.close()
            return redirect(url_for("dsa"))
        logs = db.execute("SELECT * FROM dsa_logs WHERE user_id=? ORDER BY solved_on DESC, id DESC", (g.user["id"],)).fetchall()
        topic_counts = db.execute("SELECT topic, COUNT(*) AS total FROM dsa_logs WHERE user_id=? GROUP BY topic ORDER BY total DESC", (g.user["id"],)).fetchall()
        total = len(logs)
        db.close()
        return render_template("dsa.html", logs=logs, topics=topics, topic_counts=topic_counts, total=total)

    @app.post("/dsa/<int:log_id>/delete")
    @login_required
    def delete_dsa(log_id):
        db = connect_db()
        db.execute("DELETE FROM dsa_logs WHERE id=? AND user_id=?", (log_id, g.user["id"]))
        db.commit(); db.close()
        flash("DSA entry removed.", "success")
        return redirect(url_for("dsa"))

    @app.route("/cgpa", methods=["GET", "POST"])
    @login_required
    def cgpa_tracker():
        db = connect_db()
        if request.method == "POST":
            try:
                current = float(request.form.get("current_cgpa", ""))
                target = float(request.form.get("target_cgpa", ""))
                completed = int(request.form.get("completed_semesters", ""))
                total = int(request.form.get("total_semesters", "8"))
                if not (0 <= current <= 10 and 0 <= target <= 10 and 1 <= total <= 12 and 0 <= completed < total):
                    raise ValueError
                db.execute("INSERT INTO cgpa_records(user_id,current_cgpa,target_cgpa,completed_semesters,total_semesters,updated_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET current_cgpa=excluded.current_cgpa,target_cgpa=excluded.target_cgpa,completed_semesters=excluded.completed_semesters,total_semesters=excluded.total_semesters,updated_at=CURRENT_TIMESTAMP",
                           (g.user["id"], current, target, completed, total))
                db.commit()
                flash("CGPA plan saved.", "success")
            except (ValueError, TypeError):
                flash("Enter valid CGPA values (0–10) and semester counts.", "error")
            db.close()
            return redirect(url_for("cgpa_tracker"))
        record = db.execute("SELECT * FROM cgpa_records WHERE user_id=?", (g.user["id"],)).fetchone()
        if record:
            remaining = record["total_semesters"] - record["completed_semesters"]
            required = ((record["target_cgpa"] * record["total_semesters"]) - (record["current_cgpa"] * record["completed_semesters"])) / remaining if remaining > 0 else 0
            required = round(required, 2)
        else:
            required, remaining = 0, 8
        db.close()
        return render_template("cgpa.html", record=record, required=required, remaining=remaining)

    @app.route("/applications", methods=["GET", "POST"])
    @login_required
    def applications():
        db = connect_db()
        statuses = ["Interested", "Preparing", "Applied", "Assessment", "Interview", "Offer Received", "Rejected"]
        if request.method == "POST":
            company = request.form.get("company", "").strip()
            role = request.form.get("role", "").strip()
            status = request.form.get("status", "Applied")
            deadline = request.form.get("deadline", "").strip()
            notes = request.form.get("notes", "").strip()
            if not company or not role or status not in statuses:
                flash("Company and role are required.", "error")
            else:
                db.execute("INSERT INTO applications(user_id,company,role,status,deadline,notes) VALUES(?,?,?,?,?,?)",
                           (g.user["id"], company, role, status, deadline or None, notes))
                db.commit()
                flash("Application added.", "success")
            db.close()
            return redirect(url_for("applications"))
        rows = db.execute("SELECT * FROM applications WHERE user_id=? ORDER BY created_at DESC, id DESC", (g.user["id"],)).fetchall()
        db.close()
        return render_template("applications.html", applications=rows, statuses=statuses)

    @app.post("/applications/<int:application_id>/status")
    @login_required
    def update_application_status(application_id):
        status = request.form.get("status", "")
        allowed = ["Interested", "Preparing", "Applied", "Assessment", "Interview", "Offer Received", "Rejected"]
        if status not in allowed:
            flash("Invalid application status.", "error")
        else:
            db = connect_db()
            result = db.execute("UPDATE applications SET status=? WHERE id=? AND user_id=?", (status, application_id, g.user["id"]))
            db.commit(); db.close()
            flash("Application status updated." if result.rowcount else "Application not found.", "success" if result.rowcount else "error")
        return redirect(url_for("applications"))

    @app.post("/applications/<int:application_id>/delete")
    @login_required
    def delete_application(application_id):
        db = connect_db()
        db.execute("DELETE FROM applications WHERE id=? AND user_id=?", (application_id, g.user["id"]))
        db.commit(); db.close()
        flash("Application removed.", "success")
        return redirect(url_for("applications"))

    @app.route("/hackathons")
    @login_required
    def hackathons():
        db = connect_db()
        rows = db.execute("SELECT h.*, hr.status AS my_status FROM hackathons h LEFT JOIN hackathon_registrations hr ON h.id=hr.hackathon_id AND hr.user_id=? ORDER BY CASE WHEN h.deadline IS NULL THEN 1 ELSE 0 END, h.deadline", (g.user["id"],)).fetchall()
        db.close()
        return render_template("hackathons.html", hackathons=rows)

    @app.post("/hackathons/<int:hackathon_id>/register")
    @login_required
    def register_hackathon(hackathon_id):
        status = request.form.get("status", "Interested")
        if status not in ["Interested", "Registered", "Completed"]:
            status = "Interested"
        db = connect_db()
        exists = db.execute("SELECT id FROM hackathons WHERE id=?", (hackathon_id,)).fetchone()
        if not exists:
            db.close(); abort(404)
        db.execute("INSERT INTO hackathon_registrations(user_id,hackathon_id,status) VALUES(?,?,?) ON CONFLICT(user_id,hackathon_id) DO UPDATE SET status=excluded.status", (g.user["id"], hackathon_id, status))
        db.commit(); db.close()
        flash("Hackathon status saved.", "success")
        return redirect(url_for("hackathons"))

    @app.route("/certifications")
    @login_required
    def certifications():
        db = connect_db()
        rows = db.execute("SELECT c.*, COALESCE(uc.completed,0) AS completed, uc.completed_on FROM certifications c LEFT JOIN user_certifications uc ON c.id=uc.certification_id AND uc.user_id=? ORDER BY c.id", (g.user["id"],)).fetchall()
        complete_count = sum(1 for r in rows if r["completed"])
        db.close()
        return render_template("certifications.html", certifications=rows, complete_count=complete_count)

    @app.post("/certifications/<int:cert_id>/toggle")
    @login_required
    def toggle_certification(cert_id):
        completed = 1 if request.form.get("completed") == "1" else 0
        db = connect_db()
        exists = db.execute("SELECT id FROM certifications WHERE id=?", (cert_id,)).fetchone()
        if not exists:
            db.close(); abort(404)
        db.execute("INSERT INTO user_certifications(user_id,certification_id,completed,completed_on) VALUES(?,?,?,?) ON CONFLICT(user_id,certification_id) DO UPDATE SET completed=excluded.completed,completed_on=excluded.completed_on", (g.user["id"], cert_id, completed, date.today().isoformat() if completed else None))
        db.commit(); db.close()
        flash("Certification progress saved.", "success")
        return redirect(url_for("certifications"))

    @app.route("/resources")
    @login_required
    def resources():
        term = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        db = connect_db()
        sql = "SELECT * FROM resources WHERE 1=1"
        params = []
        if term:
            like = f"%{term}%"
            sql += " AND (title LIKE ? OR description LIKE ? OR category LIKE ? OR keywords LIKE ?)"
            params.extend([like, like, like, like])
        if category:
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY category,title"
        rows = db.execute(sql, params).fetchall()
        cats = [r[0] for r in db.execute("SELECT DISTINCT category FROM resources ORDER BY category").fetchall()]
        db.close()
        return render_template("resources.html", resources=rows, categories=cats, search_term=term, selected_category=category)

    def calculate_ats_score(resume_text, job_description):
        """A transparent demo estimate based on overlapping meaningful words, not a real ATS."""
        if not resume_text.strip() or not job_description.strip():
            return 0
        stop = {"with", "from", "that", "this", "will", "your", "have", "has", "are", "and", "the", "for", "you", "our", "into", "their", "about", "using", "work", "role", "team", "good", "ability", "strong", "skills", "experience", "years", "including", "such", "other", "must", "can", "all", "who", "what", "job", "description"}
        tokens = lambda text: {w for w in re.findall(r"[a-zA-Z][a-zA-Z+#.]{2,}", text.lower()) if w not in stop}
        target = tokens(job_description)
        actual = tokens(resume_text)
        if not target:
            return 0
        return max(0, min(100, round(len(target & actual) / len(target) * 100)))

    @app.route("/resume", methods=["GET", "POST"])
    @login_required
    def resume():
        db = connect_db()
        if request.method == "POST":
            resume_text = request.form.get("resume_text", "").strip()
            job_description = request.form.get("job_description", "").strip()
            skills = request.form.get("skills", "").strip()
            projects_added = 1 if request.form.get("projects_added") else 0
            certifications_added = 1 if request.form.get("certifications_added") else 0
            experience_added = 1 if request.form.get("experience_added") else 0
            uploaded = request.files.get("resume_file")
            filename = None
            if uploaded and uploaded.filename:
                safe_name = secure_filename(uploaded.filename)
                extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
                if extension not in ALLOWED_RESUME_EXTENSIONS:
                    flash("Upload a PDF, DOCX, or TXT resume file (maximum 5 MB).", "error")
                    db.close()
                    return redirect(url_for("resume"))
                unique_name = f"user{g.user['id']}_{int(datetime.now().timestamp())}_{safe_name}"
                uploaded.save(Path(app.config["UPLOAD_FOLDER"]) / unique_name)
                filename = unique_name
            score = calculate_ats_score(resume_text, job_description)
            completeness = round((bool(skills) + bool(projects_added) + bool(certifications_added) + bool(experience_added)) / 4 * 100)
            existing = db.execute("SELECT * FROM resume_profiles WHERE user_id=?", (g.user["id"],)).fetchone()
            chosen_filename = filename if filename else (existing["filename"] if existing else "")
            db.execute("INSERT INTO resume_profiles(user_id,filename,resume_text,job_description,skills,projects_added,certifications_added,experience_added,ats_score,updated_at) VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET filename=excluded.filename,resume_text=excluded.resume_text,job_description=excluded.job_description,skills=excluded.skills,projects_added=excluded.projects_added,certifications_added=excluded.certifications_added,experience_added=excluded.experience_added,ats_score=excluded.ats_score,updated_at=CURRENT_TIMESTAMP",
                       (g.user["id"], chosen_filename, resume_text, job_description, skills, projects_added, certifications_added, experience_added, score))
            db.commit(); db.close()
            flash("Resume profile saved. The ATS score is a simple keyword-overlap estimate for demonstration.", "success")
            return redirect(url_for("resume"))
        profile = db.execute("SELECT * FROM resume_profiles WHERE user_id=?", (g.user["id"],)).fetchone()
        db.close()
        completeness = round((bool(profile["skills"]) + bool(profile["projects_added"]) + bool(profile["certifications_added"]) + bool(profile["experience_added"])) / 4 * 100) if profile else 0
        return render_template("resume.html", profile=profile, completeness=completeness)

    @app.route("/uploads/<path:filename>")
    @login_required
    def download_resume(filename):
        db = connect_db()
        profile = db.execute("SELECT filename FROM resume_profiles WHERE user_id=?", (g.user["id"],)).fetchone()
        db.close()
        if not profile or profile["filename"] != filename:
            abort(404)
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)

    @app.route("/admin", methods=["GET", "POST"])
    @admin_required
    def admin():
        db = connect_db()
        if request.method == "POST":
            action = request.form.get("action")
            if action == "resource":
                title = request.form.get("title", "").strip()
                category = request.form.get("category", "").strip()
                description = request.form.get("description", "").strip()
                url = request.form.get("url", "").strip()
                keywords = request.form.get("keywords", "").strip()
                if title and category:
                    db.execute("INSERT INTO resources(title,category,description,url,keywords) VALUES(?,?,?,?,?)", (title, category, description, url, keywords))
                    db.commit(); flash("Resource added to the library.", "success")
                else:
                    flash("Resource title and category are required.", "error")
            elif action == "hackathon":
                title = request.form.get("title", "").strip()
                organizer = request.form.get("organizer", "").strip()
                deadline = request.form.get("deadline", "").strip()
                link = request.form.get("link", "").strip()
                description = request.form.get("description", "").strip()
                if title and organizer:
                    db.execute("INSERT INTO hackathons(title,organizer,deadline,link,description) VALUES(?,?,?,?,?)", (title, organizer, deadline or None, link, description))
                    db.commit(); flash("Hackathon added.", "success")
                else:
                    flash("Hackathon title and organizer are required.", "error")
            elif action == "company":
                name = request.form.get("name", "").strip()
                careers_url = request.form.get("careers_url", "").strip()
                notes = request.form.get("notes", "").strip()
                if name:
                    db.execute("INSERT INTO companies(name,careers_url,notes) VALUES(?,?,?)", (name, careers_url, notes))
                    db.commit(); flash("Company added to the directory.", "success")
                else:
                    flash("Company name is required.", "error")
            db.close()
            return redirect(url_for("admin"))
        students = db.execute("SELECT id,name,email,academic_year,career_track,created_at FROM users WHERE role='student' ORDER BY id DESC").fetchall()
        app_counts = db.execute("SELECT u.name, COUNT(a.id) AS total FROM users u LEFT JOIN applications a ON a.user_id=u.id WHERE u.role='student' GROUP BY u.id ORDER BY total DESC").fetchall()
        res = db.execute("SELECT * FROM resources ORDER BY id DESC LIMIT 8").fetchall()
        hacks = db.execute("SELECT * FROM hackathons ORDER BY id DESC LIMIT 8").fetchall()
        companies = db.execute("SELECT * FROM companies ORDER BY name").fetchall()
        db.close()
        return render_template("admin.html", students=students, app_counts=app_counts, resources=res, hackathons=hacks, companies=companies)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="This page is available to the CareerOS admin account only."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(413)
    def too_large(_error):
        flash("The file is too large. Maximum upload size is 5 MB.", "error")
        return redirect(url_for("resume"))

    with app.app_context():
        init_db()

    return app


app = create_app()

if __name__ == "__main__":
    print("\nCareerOS is running locally. Open http://127.0.0.1:5000")
    print("Demo student: student@careeros.local / student123")
    print("Admin:        admin@careeros.local / admin123\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
