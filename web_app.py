from flask import Flask, request, render_template, send_file, flash, jsonify
import io
import os
from calculator.tips import distribute_daily_tips_df, read_file_to_df
from calculator.clock import process_clock_csv

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except Exception:
    sentry_sdk = None


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-for-local-testing-only")

# Production-friendly limits
# Max upload size: default 16 MiB, can be overridden via env var MAX_CONTENT_LENGTH
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

# Optional Basic Auth: set BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD in env to enable
BASIC_AUTH_USERNAME = os.environ.get("BASIC_AUTH_USERNAME")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD")

# Initialize Sentry if DSN provided
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN and sentry_sdk is not None:
    sentry_sdk.init(dsn=SENTRY_DSN, integrations=[FlaskIntegration()])


def _check_basic_auth():
    """Return True if auth is not enabled or if provided credentials match env vars."""
    if not (BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD):
        return True
    auth = request.authorization
    if not auth:
        return False
    return auth.username == BASIC_AUTH_USERNAME and auth.password == BASIC_AUTH_PASSWORD


@app.before_request
def require_basic_auth():
    # Protect all routes when BASIC_AUTH_* are set
    if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
        if not _check_basic_auth():
            return (
                ("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Login Required"'}),
            )


ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template("index.html", error="File too large. Max size is {} bytes.".format(app.config["MAX_CONTENT_LENGTH"])), 413


@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="ok"), 200


@app.route("/ready", methods=["GET"])
def ready():
    # Basic readiness check: can import pandas and write an in-memory excel
    try:
        import pandas as pd
        import tempfile

        df = pd.DataFrame({"a": [1]})
        with tempfile.TemporaryFile() as tf:
            with pd.ExcelWriter(tf, engine="openpyxl") as w:
                df.to_excel(w, index=False)
        return jsonify(ready=True), 200
    except Exception:
        return jsonify(ready=False), 500


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_files = request.files.getlist("file")
        if not uploaded_files or all(f.filename == "" for f in uploaded_files):
            flash("Please upload at least one Excel file.")
            return render_template("index.html")

        # Validate each uploaded file
        valid_files = []
        for f in uploaded_files:
            if f and f.filename and _allowed_file(f.filename):
                valid_files.append(f)

        if not valid_files:
            flash("Unsupported file type. Please upload .xlsx, .xls, or .csv files.")
            return render_template("index.html")

        # Get column names from form (with defaults); support auto-detect
        auto_detect = request.form.get("auto_detect", "on") == "on"
        advanced_mode = request.form.get("advanced_mode") == "on"

        # In advanced mode, use provided values; otherwise auto-detect (pass None)
        if advanced_mode:
            date_col = request.form.get("date_col", "").strip() or None
            tips_col = request.form.get("tips_col", "").strip() or None
            hours_col = request.form.get("hours_col", "").strip() or None
            name_col = request.form.get("name_col", "").strip() or None
        else:
            # Auto-detect by passing None
            date_col = None
            tips_col = None
            hours_col = None
            name_col = None

        try:
            import pandas as pd

            dfs = []
            for f in valid_files:
                file_bytes = f.read()
                df = read_file_to_df(file_bytes, f.filename)
                dfs.append(df)

            # Pass list of DataFrames to processor (supports concatenation)
            final_dict, export_df = distribute_daily_tips_df(
                dfs, date_col, tips_col, hours_col, name_col
            )

            # Write export_df to an in-memory Excel file
            output_io = io.BytesIO()
            with pd.ExcelWriter(output_io, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Tip Distribution Summary")
            output_io.seek(0)

            return send_file(
                output_io,
                as_attachment=True,
                download_name="Tip_Payroll_Summary_OUTPUT.xlsx",
                mimetype=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            )
        except Exception as e:
            # Capture exception in Sentry (if configured)
            if sentry_sdk is not None:
                sentry_sdk.capture_exception(e)
            flash(f"Error processing file: {e}")

    return render_template("index.html")


@app.route("/process-clock", methods=["GET", "POST"])
def process_clock():
    """Process clock/timesheet CSV and return daily hours summary."""
    if request.method == "POST":
        uploaded_file = request.files.get("clock_file")
        if not uploaded_file or uploaded_file.filename == "":
            flash("Please upload a clock/timesheet file.")
            return render_template("index.html")

        if not _allowed_file(uploaded_file.filename):
            flash("Unsupported file type. Please upload .xlsx, .xls, or .csv files.")
            return render_template("index.html")

        try:
            import pandas as pd

            file_bytes = uploaded_file.read()
            df = read_file_to_df(file_bytes, uploaded_file.filename)

            # Get optional custom column names from form
            employee_col = request.form.get("clock_employee_col", "Employee Name").strip() or "Employee Name"
            date_col = request.form.get("clock_date_col", "Clock In Date").strip() or "Clock In Date"
            hours_col = request.form.get("clock_hours_col", "Elapsed Hours").strip() or "Elapsed Hours"
            date_format = request.form.get("clock_date_format", "%d-%b-%y").strip() or "%d-%b-%y"

            # Process the clock data
            daily_hours_df = process_clock_csv(
                df,
                employee_col=employee_col,
                date_col=date_col,
                hours_col=hours_col,
                date_format=date_format,
            )

            # Write to in-memory Excel
            output_io = io.BytesIO()
            with pd.ExcelWriter(output_io, engine="openpyxl") as writer:
                daily_hours_df.to_excel(writer, index=False, sheet_name="Daily Hours Summary")
            output_io.seek(0)

            return send_file(
                output_io,
                as_attachment=True,
                download_name="Daily_Hours_Summary.xlsx",
                mimetype=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            )

        except Exception as e:
            if sentry_sdk is not None:
                sentry_sdk.capture_exception(e)
            flash(f"Error processing clock file: {e}")

    return render_template("index.html")


if __name__ == "__main__":
    # Use PORT environment variable for cloud servers; default to 5000 for local dev
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
