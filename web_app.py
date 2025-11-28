from flask import Flask, request, render_template, send_file, flash
import io
import os
from calculator.tips import distribute_daily_tips_df

app = Flask(__name__)
app.secret_key = "dev-secret-for-local"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or uploaded.filename == "":
            flash("Please upload an Excel file.")
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
            flash(f"Error processing file: {e}")

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
