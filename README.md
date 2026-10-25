# CareerOS

CareerOS is a Python web application for engineering students preparing for internships and campus placements. It combines a roadmap, DSA log, CGPA planner, application tracker, hackathon and certification lists, resource library, resume checklist, and an admin area.

## Stack

- Python and Flask
- PostgreSQL for hosted deployments
- SQLite for local development when `DATABASE_URL` is not set
- HTML, CSS and JavaScript

## Run locally

Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. On Windows, activate the environment with `.venv\Scripts\Activate.ps1`.

The first local run creates `careeros.db` and sample records. Demo accounts are `student@careeros.local` / `student123` and `admin@careeros.local` / `admin123`. These credentials are for local demonstration only.

## Use PostgreSQL

Create a PostgreSQL database with a managed provider such as Neon or another PostgreSQL host. Copy its connection string and set these environment variables before starting the app:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require'
export CAREEROS_SECRET='a-long-random-secret-value'
python app.py
```

The application creates its tables and sample records on startup. When `DATABASE_URL` is set, PostgreSQL is used instead of the local SQLite file. Keep the connection string and secret in the hosting provider's environment-variable settings. Never commit a real `.env` file or production credentials.

For production, change or remove the demo accounts and use a strong secret. Demo seed accounts are intended for the student exhibition and should not remain enabled on a public deployment.

## Deploy

The app can run on a Python-capable host with persistent PostgreSQL access. For a Vercel deployment, use the included `vercel.json` and confirm the selected Vercel Python runtime supports the app configuration. Set `DATABASE_URL` and `CAREEROS_SECRET` in Vercel project environment variables. Resume uploads currently use local disk, so they are not durable across serverless deployments; use object storage before accepting real user resumes.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

```text
CareerOS/
├── app.py
├── requirements.txt
├── vercel.json
├── .env.example
├── README.md
├── PROJECT_NOTES.md
├── EXHIBITION_GUIDE.md
├── static/
│   ├── main.js
│   └── style.css
├── templates/
├── tests/
└── uploads/
```

## Notes

- Student records are associated with a user ID and the admin page is role-restricted.
- The resume keyword score is a basic estimate, not a real ATS assessment.
- The CGPA planner assumes equal semester weight.
- Sample hackathon and company records are for demonstration; verify current details independently.
- Before a public launch, add CSRF protection, rate limiting, email verification, password reset, production session settings, a migration process, and durable object storage for uploaded files.
