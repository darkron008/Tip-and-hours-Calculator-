from flask import Flask, request, render_template, send_file, flash, jsonify
import io
import os
from calculator.tips import distribute_daily_tips_df

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


ALLOWED_EXTENSIONS = {"xlsx", "xls"}


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
        uploaded = request.files.get("file")
        if not uploaded or uploaded.filename == "":
            flash("Please upload an Excel file.")
            return render_template("index.html")

        if not _allowed_file(uploaded.filename):
            flash("Unsupported file type. Please upload an .xlsx or .xls file.")
            return render_template("index.html")

        # Get column names from form (with defaults)
        date_col = request.form.get("date_col", "Shift Date")
        tips_col = request.form.get("tips_col", "Daily Tip Total")
        hours_col = request.form.get("hours_col", "Hours Worked")
        name_col = request.form.get("name_col", "Employee Name")

        try:
            # Read uploaded file into a DataFrame directly from the file stream
            file_bytes = uploaded.read()
            input_io = io.BytesIO(file_bytes)
            import pandas as pd

            df = pd.read_excel(input_io)

            final_dict, export_df = distribute_daily_tips_df(
                df, date_col, tips_col, hours_col, name_col
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
