from flask import Flask, request, render_template, send_file, flash, jsonify
import io
import os
import logging
from calculator.tips import distribute_daily_tips_df, read_file_to_df, _extract_from_transposed_sales_report
from calculator.clock import process_clock_csv

logger = logging.getLogger(__name__)

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
        # Get all uploaded files
        uploaded_files = request.files.getlist("files")
        if not uploaded_files or all(f.filename == "" for f in uploaded_files):
            flash("Please upload at least one file.")
            return render_template("index.html")

        # Validate and separate files into clock and tips
        valid_files = []
        for f in uploaded_files:
            if f and f.filename and _allowed_file(f.filename):
                valid_files.append(f)
        
        if not valid_files:
            flash("Unsupported file type. Please upload .xlsx, .xls, or .csv files.")
            return render_template("index.html")

        # Import here to use the new differentiation function
        from calculator.tips import is_clock_file

        # Separate files by type
        clock_files = []
        tips_files = []

        for f in valid_files:
            try:
                file_bytes = f.read()
                df = read_file_to_df(file_bytes, f.filename)
                
                if is_clock_file(df, f.filename):
                    clock_files.append((f.filename, file_bytes))
                    logger.info(f"Identified {f.filename} as clock/timesheet file")
                else:
                    tips_files.append((f.filename, file_bytes))
                    logger.info(f"Identified {f.filename} as tips/sales file")
            except Exception as e:
                logger.error(f"Could not identify file type for {f.filename}: {e}")
                flash(f"Error reading file {f.filename}: {e}")
                return render_template("index.html")

        if not clock_files:
            flash("No clock/timesheet file detected. Please ensure one of your files contains employee, date, and hours columns.")
            return render_template("index.html")

        # Get column names from form (with defaults); support auto-detect
        advanced_mode = request.form.get("advanced_mode") == "on"

        # In advanced mode, use provided values; otherwise auto-detect (pass None)
        if advanced_mode:
            date_col = request.form.get("date_col", "").strip() or None
            tips_col = request.form.get("tips_col", "").strip() or None
            hours_col = request.form.get("hours_col", "").strip() or None
            name_col = request.form.get("name_col", "").strip() or None
            clock_employee_col = request.form.get("clock_employee_col", "").strip() or None
            clock_date_col = request.form.get("clock_date_col", "").strip() or None
            clock_hours_col = request.form.get("clock_hours_col", "").strip() or None
        else:
            # Auto-detect by passing None
            date_col = None
            tips_col = None
            hours_col = None
            name_col = None
            clock_employee_col = None
            clock_date_col = None
            clock_hours_col = None

        try:
            import pandas as pd

            # Load clock file (use first clock file if multiple identified)
            clock_bytes = clock_files[0][1]
            clock_df = read_file_to_df(clock_bytes, clock_files[0][0])
            logger.info(f"Clock file {clock_files[0][0]} loaded successfully")

            # Load tips/sales files if any
            dfs = []
            for filename, file_bytes in tips_files:
                # Try transposed sales report format first
                df = _extract_from_transposed_sales_report(file_bytes, filename)
                
                # If not a transposed report, try regular format
                if df is None:
                    df = read_file_to_df(file_bytes, filename)
                
                dfs.append(df)
                logger.info(f"Tips file {filename} loaded successfully")

            # Pass list of DataFrames to processor with clock data as primary
            final_dict, export_df = distribute_daily_tips_df(
                dfs if dfs else None,
                date_col,
                tips_col,
                hours_col,
                name_col,
                clock_df=clock_df,
                clock_employee_col=clock_employee_col,
                clock_date_col=clock_date_col,
                clock_hours_col=clock_hours_col,
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


if __name__ == "__main__":
    # Use PORT environment variable for cloud servers; default to 5000 for local dev
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
