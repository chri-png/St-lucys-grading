# St. Lucy's School for the Blind — Grading System (Online Backend)

A real backend: FastAPI + a database, with password hashing and secure
login sessions, serving both the API and the web page from one place.
Once deployed, admins, teachers, and students can log in from anywhere
with an internet connection — no more passing save files around.

## What's inside

- `main.py`, `database.py`, `models.py`, `schemas.py`, `auth.py` — the backend (Python/FastAPI)
- `static/index.html` — the web page everyone uses (admin, teacher, and student login)
- `requirements.txt` — Python packages needed

## 1. Test it on your own computer first

1. Install Python 3.10+ if you don't have it: https://www.python.org/downloads/
2. Open a terminal in this folder and run:

   ```
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```

3. Open **http://127.0.0.1:8000** in your browser. You should see the login page.
4. Log in as Administrator with the default password `admin123`, then
   change it immediately in the Administrator dashboard.

Data is stored in a local file called `stlucys.db` while testing.

## 2. Deploy it online (free option: Render)

These steps put the site at a public web address anyone can open.

1. Create a free account at https://render.com
2. Put this folder in a GitHub repository (Render deploys from GitHub,
   GitLab, or a direct upload — GitHub is easiest).
3. In Render, click **New +** → **Web Service**, and connect that repository.
4. Fill in:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment**, add these variables:
   - `SECRET_KEY` — any long random string (this signs login sessions; keep it private)
   - `DEFAULT_ADMIN_PASSWORD` — the administrator password to start with (change it after first login)
6. Click **Create Web Service**. After a few minutes you'll get a public
   URL like `https://stlucys-grading.onrender.com` — that's the address
   everyone uses to log in.

### Important: use a persistent database in production

Render's free web services can lose local files (like `stlucys.db`) when
the service restarts. For real use, add a free Render Postgres database
instead:

1. In Render, click **New +** → **PostgreSQL** and create a free instance.
2. Copy its **Internal Database URL**.
3. Add it as an environment variable on your web service named
   `DATABASE_URL` (the app already reads this automatically —
   see `database.py`).
4. In `requirements.txt`, remove the `#` from the front of the
   `psycopg2-binary` line so it actually installs (it's commented out
   by default because it can fail to install locally on Windows, and
   isn't needed for local SQLite testing).
5. Push this change and redeploy. Your data will now persist properly
   across restarts.

Railway (https://railway.app) and Fly.io (https://fly.io) work in a very
similar way if you'd rather use one of those instead of Render.

## 3. Using the system day to day

- **Administrator**: logs in with the admin password, adds classes,
  creates teacher accounts (and assigns which classes each teacher can
  access), and can enroll students or look up anyone's results.
- **Teacher**: logs in with a username and password created by the
  admin. Can enroll students into their own classes, record results
  (subject, score, and a term/period label like "Term 1 2026"), and
  view a class roster or any of their students' full history.
- **Student**: logs in with registration number + full name + class
  (no password). Sees their entire result history, grouped by term,
  with per-term and overall averages — going back as far as results
  have been recorded.

## Security notes

- Change the default administrator password immediately after first login.
- Set a real, random `SECRET_KEY` before deploying — don't leave the
  placeholder value in `auth.py`.
- All passwords are stored as bcrypt hashes, never in plain text.
- Consider adding HTTPS-only cookies or a password-reset flow later if
  this grows beyond a single school's internal use — this version
  covers the core login and grading workflow.
