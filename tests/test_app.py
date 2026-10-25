import tempfile
import unittest
from pathlib import Path

from app import create_app


class CareerOSTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(root / "test.db"),
            "UPLOAD_FOLDER": str(root / "uploads"),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login_as_student(self):
        return self.client.post("/login", data={
            "email": "student@careeros.local", "password": "student123"
        }, follow_redirects=True)

    def test_login_and_dashboard(self):
        response = self.login_as_student()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Roadmap overview", response.data)
        self.assertIn(b"CareerOS", response.data)

    def test_roadmap_update(self):
        self.login_as_student()
        response = self.client.post("/roadmap", data={"stage_id": "1", "progress": "80"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Roadmap progress updated", response.data)
        with self.app.app_context():
            import sqlite3
            db = sqlite3.connect(self.app.config["DATABASE"])
            value = db.execute("SELECT progress FROM roadmap_progress WHERE id=1").fetchone()[0]
            db.close()
        self.assertEqual(value, 80)

    def test_dsa_problem_can_be_added(self):
        self.login_as_student()
        response = self.client.post("/dsa", data={"problem": "Binary Search", "topic": "Searching & Sorting"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Binary Search", response.data)

    def test_application_can_be_added(self):
        self.login_as_student()
        response = self.client.post("/applications", data={
            "company": "Example Tech", "role": "Python Intern", "status": "Applied",
            "deadline": "2026-12-01", "notes": "Prepare SQL"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Example Tech", response.data)

    def test_resource_search(self):
        self.login_as_student()
        response = self.client.get("/resources?q=Python")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Python Official Tutorial", response.data)

    def test_admin_access_is_restricted(self):
        self.login_as_student()
        response = self.client.get("/admin")
        self.assertEqual(response.status_code, 403)
        self.client.get("/logout")
        response = self.client.post("/login", data={"email": "admin@careeros.local", "password": "admin123"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add a resource", response.data)

    def test_invalid_login_does_not_authenticate(self):
        response = self.client.post("/login", data={"email": "student@careeros.local", "password": "wrong"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email or password is incorrect", response.data)
        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 302)


if __name__ == "__main__":
    unittest.main()
