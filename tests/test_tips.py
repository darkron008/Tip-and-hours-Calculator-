import pandas as pd
from decimal import Decimal
from calculator.tips import distribute_daily_tips, read_file_to_df
import tempfile
import csv


def test_distribute_daily_tips(tmp_path):
    # Create a small sample DataFrame representing two dates and two employees
    data = [
        {"Shift Date": "2025-11-01", "Daily Tip Total": 100.0, "Hours Worked": 5.0, "Employee Name": "Alice"},
        {"Shift Date": "2025-11-01", "Daily Tip Total": 0.0, "Hours Worked": 5.0, "Employee Name": "Bob"},
        {"Shift Date": "2025-11-02", "Daily Tip Total": 60.0, "Hours Worked": 4.0, "Employee Name": "Alice"},
        {"Shift Date": "2025-11-02", "Daily Tip Total": 0.0, "Hours Worked": 6.0, "Employee Name": "Bob"},
    ]

    df = pd.DataFrame(data)

    input_file = tmp_path / "input.xlsx"
    output_file = tmp_path / "output.xlsx"

    df.to_excel(input_file, index=False)

    result = distribute_daily_tips(
        str(input_file), str(output_file), "Shift Date", "Daily Tip Total", "Hours Worked", "Employee Name"
    )

    # Expected: 2025-11-01 -> 100 split 5/10 -> 50 each; 2025-11-02 -> 60 split 4/10 -> 24 Alice, 36 Bob
    assert round(result["Alice"], 2) == 74.0
    assert round(result["Bob"], 2) == 86.0

    # Output file should exist and contain the summary sheet
    out_df = pd.read_excel(output_file, sheet_name="Tip Distribution Summary")
    assert "Employee Name" in out_df.columns
    assert "Total Tip Share" in out_df.columns


def test_distribute_two_input_files(tmp_path):
    # First file: one day's tips and hours
    data1 = [
        {"Shift Date": "2025-11-03", "Daily Tip Total": 80.0, "Hours Worked": 4.0, "Employee Name": "Carol"},
        {"Shift Date": "2025-11-03", "Daily Tip Total": 0.0, "Hours Worked": 4.0, "Employee Name": "Dave"},
    ]

    # Second file: another day's tips and hours
    data2 = [
        {"Shift Date": "2025-11-04", "Daily Tip Total": 40.0, "Hours Worked": 2.0, "Employee Name": "Carol"},
        {"Shift Date": "2025-11-04", "Daily Tip Total": 0.0, "Hours Worked": 6.0, "Employee Name": "Eve"},
    ]

    df1 = pd.DataFrame(data1)
    df2 = pd.DataFrame(data2)

    input_file1 = tmp_path / "input1.xlsx"
    input_file2 = tmp_path / "input2.xlsx"
    output_file = tmp_path / "output_multi.xlsx"

    df1.to_excel(input_file1, index=False)
    df2.to_excel(input_file2, index=False)

    # Pass a list of input paths to the wrapper
    result = distribute_daily_tips(
        [str(input_file1), str(input_file2)],
        str(output_file),
        "Shift Date",
        "Daily Tip Total",
        "Hours Worked",
        "Employee Name",
    )

    # For 2025-11-03: 80 split 4/8 -> 40 Carol, 40 Dave
    # For 2025-11-04: 40 split 2/8 -> 10 Carol, 30 Eve
    # Totals: Carol 50, Dave 40, Eve 30
    assert round(result.get("Carol", 0.0), 2) == 50.0
    assert round(result.get("Dave", 0.0), 2) == 40.0
    assert round(result.get("Eve", 0.0), 2) == 30.0

    out_df = pd.read_excel(output_file, sheet_name="Tip Distribution Summary")
    assert "Employee Name" in out_df.columns
    assert "Total Tip Share" in out_df.columns


def test_auto_detect_columns(tmp_path):
    # Non-standard column names
    data = [
        {"Work Date": "2025-11-05", "Gratuities": 50.0, "Worked Hrs": 3.0, "Staff": "Gina"},
        {"Work Date": "2025-11-05", "Gratuities": 0.0, "Worked Hrs": 5.0, "Staff": "Hank"},
    ]

    df = pd.DataFrame(data)

    # Use the df-based function and pass None for columns to trigger detection
    from calculator.tips import distribute_daily_tips_df

    final, export_df = distribute_daily_tips_df(df, None, None, None, None)

    # 50 split 3/8 -> Gina 18.75, Hank 31.25
    assert round(final.get("Gina", 0.0), 2) == 18.75
    assert round(final.get("Hank", 0.0), 2) == 31.25


def test_read_csv_file(tmp_path):
    # Create a CSV file
    csv_file = tmp_path / "test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Shift Date", "Daily Tip Total", "Hours Worked", "Employee Name"])
        writer.writeheader()
        writer.writerow({"Shift Date": "2025-11-06", "Daily Tip Total": 40.0, "Hours Worked": 2.0, "Employee Name": "Leo"})
        writer.writerow({"Shift Date": "2025-11-06", "Daily Tip Total": 0.0, "Hours Worked": 4.0, "Employee Name": "Mia"})

    # Read CSV using the helper
    with open(csv_file, "rb") as f:
        file_bytes = f.read()
    
    df = read_file_to_df(file_bytes, "test.csv")
    
    assert len(df) == 2
    assert "Employee Name" in df.columns
    assert "Shift Date" in df.columns


def test_distribute_csv_and_excel_mixed(tmp_path):
    # CSV file
    csv_file = tmp_path / "input.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Shift Date", "Daily Tip Total", "Hours Worked", "Employee Name"])
        writer.writeheader()
        writer.writerow({"Shift Date": "2025-11-07", "Daily Tip Total": 60.0, "Hours Worked": 3.0, "Employee Name": "Noah"})
    
    # Excel file
    excel_file = tmp_path / "input2.xlsx"
    df_excel = pd.DataFrame([
        {"Shift Date": "2025-11-07", "Daily Tip Total": 0.0, "Hours Worked": 3.0, "Employee Name": "Olivia"}
    ])
    df_excel.to_excel(excel_file, index=False)

    # Read and combine both
    with open(csv_file, "rb") as f:
        df_csv = read_file_to_df(f.read(), "input.csv")
    
    df_excel2 = pd.read_excel(excel_file)
    dfs = [df_csv, df_excel2]

    from calculator.tips import distribute_daily_tips_df
    final, export_df = distribute_daily_tips_df(dfs, None, None, None, None)

    # 60 split 3/6 -> Noah 30, Olivia 30
    assert round(final.get("Noah", 0.0), 2) == 30.0
    assert round(final.get("Olivia", 0.0), 2) == 30.0
