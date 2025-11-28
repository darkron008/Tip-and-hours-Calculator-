import pandas as pd
from decimal import Decimal
from calculator.tips import distribute_daily_tips


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
