import io
import pandas as pd
from flask import url_for


def make_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return bio.getvalue()


def test_flask_upload_two_files_returns_excel(tmp_path):
    # Import app from web_app
    from web_app import app

    client = app.test_client()

    # Prepare two small Excel files in memory
    df1 = pd.DataFrame([
        {"Shift Date": "2025-11-10", "Daily Tip Total": 90.0, "Hours Worked": 3.0, "Employee Name": "Ivy"},
        {"Shift Date": "2025-11-10", "Daily Tip Total": 0.0, "Hours Worked": 3.0, "Employee Name": "Jack"},
    ])
    df2 = pd.DataFrame([
        {"Shift Date": "2025-11-11", "Daily Tip Total": 30.0, "Hours Worked": 2.0, "Employee Name": "Ivy"},
        {"Shift Date": "2025-11-11", "Daily Tip Total": 0.0, "Hours Worked": 6.0, "Employee Name": "Kate"},
    ])

    b1 = make_excel_bytes(df1)
    b2 = make_excel_bytes(df2)

    data = {
        "auto_detect": "on",
        "file": [
            (io.BytesIO(b1), "input1.xlsx"),
            (io.BytesIO(b2), "input2.xlsx"),
        ],
    }

    resp = client.post("/", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    # Response should be an Excel attachment
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.content_type

    # Read returned Excel
    returned = io.BytesIO(resp.data)
    out_df = pd.read_excel(returned, sheet_name="Tip Distribution Summary")

    assert "Employee Name" in out_df.columns
    assert "Total Tip Share" in out_df.columns
