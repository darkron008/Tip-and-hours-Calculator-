# Tip-and-hours-Calculator-

Minimal Python scaffold for tip and hours calculations.

Run locally (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python -m pytest -q
```

Examples:

```powershell
python cli.py tip --amount 100 --percent 15
python cli.py pay --hours 40 --rate 15.50
```

## Web UI with Drag & Drop

Run the Flask web UI locally and open http://127.0.0.1:5000 in your browser:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python web_app.py
```

**Features:**
- Drag and drop your Excel file or click to browse
- Download the generated Excel summary automatically
- In-memory Excel processing (no temp files left on disk)
 - Download the generated Excel summary automatically
 - In-memory Excel processing (no temp files left on disk)

Multi-file uploads and auto-detection
-----------------------------------

- The web UI supports uploading multiple Excel files at once. Click the drop zone or drag multiple files into it. The server will combine rows from all uploaded files and compute tip distribution across matching dates.
- By default the UI tries to auto-detect the column names for `Shift Date`, `Daily Tip Total`, `Hours Worked`, and `Employee Name`. This is recommended for convenience — if auto-detect fails, uncheck the "Auto-detect columns" checkbox and provide the column names manually.
- Programmatic wrappers (`calculator.tips.distribute_daily_tips_df`) accept `None` for column names, which triggers the same auto-detection heuristic.

If you want to customize the column detection logic, consider modifying `calculator/tips.py` which contains the `_detect_columns` helper that uses keyword heuristics and fuzzy matching.

## Cloud Deployment

This app is ready for cloud deployment on **Heroku**, **Render**, **Railway**, or any platform that supports Python/Gunicorn.

### Deploy to Heroku

1. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Clone and navigate to the repo
3. Create a new Heroku app:
   ```bash
   heroku create your-app-name
   ```
4. Set a secure secret key:
   ```bash
   heroku config:set SECRET_KEY=$(openssl rand -hex 32)
   ```
5. Deploy:
   ```bash
   git push heroku main
   ```
6. Open the app:
   ```bash
   heroku open
   ```

### Deploy to Render

1. Push code to GitHub
2. Go to [Render](https://render.com) and create a new Web Service
3. Connect your GitHub repo
4. Set environment:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app`
5. Add environment variable `SECRET_KEY` (any random string for development)
6. Deploy

### Deploy to Railway

1. Push code to GitHub
2. Go to [Railway](https://railway.app) and create a new project
3. Connect your GitHub repo
4. Railway auto-detects Python and `Procfile`
5. Add environment variable `SECRET_KEY`
6. Deploy

Your app will be live at a public URL. Share it to allow anyone to upload and download tip summaries.

## Production Notes & Security

- **Set a secure `SECRET_KEY`** in your Render/Heroku environment variables. Example:

   ```bash
   heroku config:set SECRET_KEY=$(openssl rand -hex 32)
   ```

- **Enable Basic Auth** (optional): set `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` in your environment to require HTTP Basic authentication for the web UI. Browsers will prompt for credentials.

- **Sentry error monitoring**: set `SENTRY_DSN` to enable automatic error reporting to Sentry. Install Sentry on your Sentry account and add the DSN as an env var.

- **Upload size limit**: controlled by `MAX_CONTENT_LENGTH` (bytes) env var; defaults to 16 MiB (16 * 1024 * 1024).

- **Health & readiness endpoints**:
   - `/health` — simple liveness check (200 OK)
   - `/ready` — readiness check that attempts a lightweight pandas Excel write (200 OK when ready)

- **Custom domain & HTTPS**: Render provides automatic HTTPS for linked domains. To use a custom domain:
   1. Add the domain in the Render service settings
   2. Follow the DNS instructions (create CNAME or A records as directed)
   3. Wait for propagation; Render will provision TLS automatically

## Recommended next steps for production

- Rotate `SECRET_KEY` periodically and never commit it to source control.
- Consider adding rate-limiting (Flask-Limiter) if you expect public traffic.
- Monitor error logs in Render and Sentry, and enable alerts for high error rates.
