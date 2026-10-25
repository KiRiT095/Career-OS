# Project notes

CareerOS follows the modules described in the supplied project description and SRS: roadmap, DSA, CGPA, applications, hackathons, certifications, resume management, resources, dashboard, and admin functions.

The code supports PostgreSQL through `DATABASE_URL` for hosted use and SQLite for local development. Set `DATABASE_URL` to switch to PostgreSQL. The admin role is stored on the user record; public registration creates student accounts only.

The visual interface has been cleaned of emoji decoration and the stylesheet has been expanded into readable, multi-line rules. JavaScript interactions live in `static/main.js` rather than inline script blocks.

Before a real public launch, remove demo accounts, configure strong environment secrets, add CSRF protection and rate limiting, and move resume uploads to durable object storage.
