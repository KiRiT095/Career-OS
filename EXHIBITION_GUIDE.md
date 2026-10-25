# CareerOS Exhibition Cheat Sheet

## Aim
To develop a simple web-based Placement Roadmap & Career Management System that helps engineering students organize placement preparation, learning progress, internship applications and resources in one place.

## Problem statement
Students often track DSA progress, CGPA, certifications, internships, hackathons and learning links in separate notes or websites. CareerOS provides one dashboard for those activities and helps students understand their next steps.

## Main user roles
- **Student:** maintains their roadmap, solved DSA problems, CGPA plan, applications, hackathon participation, certifications and resume information.
- **Admin:** adds shared resource links, hackathons and companies, and views student/application summaries.

## Technology and why
- **Python + Flask:** readable route logic for a small web application.
- **SQLite:** data is saved locally without installing a database server.
- **HTML/Jinja + CSS:** straightforward pages and responsive dashboard styling.
- **Werkzeug password hashing:** stores password hashes instead of plain-text passwords.

The longer SRS describes React, Node/Express, MongoDB Atlas, JWT and Cloudinary. This prototype deliberately uses a smaller Python stack for the mini-project demo; it should be described that way in the viva.

## Architecture to draw on paper
```text
Browser UI (HTML/CSS)
        ↓ HTTP request
Flask routes (Python validation and application logic)
        ↓ SQL queries
SQLite database
        ↓ (resume uploads only)
Local uploads directory
```

## 60-second feature explanation
“After login, the dashboard summarizes my roadmap progress, DSA questions, CGPA target and active applications. The roadmap shows five preparation stages. The DSA tracker stores solved questions by topic. The CGPA planner calculates a target average for remaining semesters using an equal-semester assumption. The application tracker stores company, role, status and deadline. Students can track hackathons and certifications, while the resource library can be searched by category or keyword. The admin can add shared resources, events and company records. We use Flask for the Python web backend and SQLite for persistent local storage.”

## Demo flow (recommended)
1. Sign in as student with `student@careeros.local` / `student123`.
2. Show the consolidated dashboard and explain why it is the main screen.
3. Go to Roadmap and change “Projects” to 50%, then save.
4. Go to DSA Tracker and add “Binary Search” under “Searching & Sorting”. Show the new row and topic breakdown.
5. Go to CGPA Planner, change current CGPA or target and calculate. Explain the assumption.
6. Add an application such as “Example Tech — Python Intern”, then update its status.
7. Search the Resource Library for “Python”.
8. Sign out, then sign in as admin (`admin@careeros.local` / `admin123`) and add a resource or hackathon.

## Test cases

| ID | Test | Steps | Expected result |
|---|---|---|---|
| TC-01 | Valid login | Use the demo student credentials | Dashboard opens and shows student data |
| TC-02 | Invalid login | Use a wrong password | Error feedback appears; dashboard stays protected |
| TC-03 | Roadmap update | Set a stage to 80% and save | Stage percentage is saved and displayed |
| TC-04 | Add DSA problem | Enter problem and topic | Problem appears in the DSA history and topic totals update |
| TC-05 | Add application | Enter company, role, status and deadline | Application appears in the table and dashboard count changes |
| TC-06 | Search resources | Search for “Python” | Matching Python-related resource is displayed |
| TC-07 | Student admin protection | Visit Admin Panel as student | Access is denied |
| TC-08 | Admin operation | Log in as admin and add a resource | Resource is saved and available in the library |
| TC-09 | CGPA planning | Enter current/target values and semesters | Required average is shown; values outside valid range are rejected |
| TC-10 | Resume estimate | Paste resume text and job description, then save | Keyword match estimate and completeness update |

Automated checks for the first group of routes are in `tests/test_app.py`. The suite can be run after installing the dependency using the command in README.

## Likely viva questions

**1. What is the objective of CareerOS?**  
To centralize placement preparation and help students track progress from skills learning to applications.

**2. Why did you use SQLite?**  
It is file-based, comes with Python, needs no separate database server and is suitable for a small offline prototype.

**3. What is Flask?**  
A lightweight Python web framework that maps URLs to Python functions and returns web pages or responses.

**4. What is the role of the database?**  
It persistently stores users and their progress records so information remains after navigating to another page or restarting the app.

**5. How are passwords stored?**  
A password hash is stored using Werkzeug's password-hashing helper. The application does not put the original password in the users table.

**6. How is the CGPA requirement calculated?**  
Under the equal-semester assumption: `required average = (target CGPA × total semesters − current CGPA × completed semesters) ÷ remaining semesters`.

**7. Is the ATS score a real ATS result?**  
No. It is a transparent keyword-overlap estimate for demonstration. A production version would need better document parsing and a validated scoring method.

**8. What is the difference between functional and non-functional requirements?**  
Functional requirements describe system actions, such as adding an application. Non-functional requirements describe quality constraints, such as usability, performance, security and maintainability.

**9. What are the project limitations?**  
This version is local, uses SQLite, doesn't use cloud resume storage or JWT APIs, and uses sample event/catalog data. It is a prototype, not a production deployment.

**10. What would you add next?**  
Admin CRUD for every catalog, cloud storage, production authentication and authorization, automatic reminders, better resume parsing, and coding profile integration.
