"""Tests for clock/timesheet processing."""
import pandas as pd
from calculator.clock import process_clock_csv


def test_process_clock_csv_basic():
    """Test basic clock CSV processing with standard format."""
    data = [
        {"Employee Name": "Alice", "Clock In Date": "01-Jan-25", "Elapsed Hours": 8.0},
        {"Employee Name": "Alice", "Clock In Date": "01-Jan-25", "Elapsed Hours": 2.0},
        {"Employee Name": "Bob", "Clock In Date": "01-Jan-25", "Elapsed Hours": 6.0},
        {"Employee Name": "Alice", "Clock In Date": "02-Jan-25", "Elapsed Hours": 7.5},
    ]
    df = pd.DataFrame(data)

    result = process_clock_csv(df, date_format="%d-%b-%y")

    assert len(result) == 3  # 3 unique (employee, date) pairs
    assert "Total Daily Hours" in result.columns

    # Check aggregation: Alice on 01-Jan had 8 + 2 = 10 hours
    alice_jan1 = result[(result["Employee Name"] == "Alice") & (result["Clock In Date"].dt.day == 1)]
    assert len(alice_jan1) == 1
    assert alice_jan1["Total Daily Hours"].values[0] == 10.0

    # Bob on 01-Jan had 6 hours
    bob_jan1 = result[(result["Employee Name"] == "Bob") & (result["Clock In Date"].dt.day == 1)]
    assert len(bob_jan1) == 1
    assert bob_jan1["Total Daily Hours"].values[0] == 6.0


def test_process_clock_csv_with_missing_data():
    """Test clock CSV processing handles missing/invalid data."""
    data = [
        {"Employee Name": "Carol", "Clock In Date": "03-Jan-25", "Elapsed Hours": 5.0},
        {"Employee Name": None, "Clock In Date": "03-Jan-25", "Elapsed Hours": 3.0},  # Missing name
        {"Employee Name": "Carol", "Clock In Date": "04-Jan-25", "Elapsed Hours": "invalid"},  # Invalid hours
        {"Employee Name": "Dave", "Clock In Date": "04-Jan-25", "Elapsed Hours": 4.0},
    ]
    df = pd.DataFrame(data)

    result = process_clock_csv(df, date_format="%d-%b-%y")

    # Should have 2 valid records: Carol 03-Jan and Dave 04-Jan
    assert len(result) == 2
    assert result["Employee Name"].tolist() == ["Carol", "Dave"]


def test_process_clock_csv_custom_columns():
    """Test clock CSV processing with custom column names."""
    data = [
        {"Staff": "Eve", "Work Date": "05-Jan-25", "Hours": 6.0},
        {"Staff": "Eve", "Work Date": "05-Jan-25", "Hours": 2.0},
        {"Staff": "Frank", "Work Date": "05-Jan-25", "Hours": 8.0},
    ]
    df = pd.DataFrame(data)

    result = process_clock_csv(
        df,
        employee_col="Staff",
        date_col="Work Date",
        hours_col="Hours",
        date_format="%d-%b-%y",
    )

    assert len(result) == 2
    assert "Total Daily Hours" in result.columns
    # Eve should have 6 + 2 = 8 hours
    eve_record = result[result["Staff"] == "Eve"]
    assert eve_record["Total Daily Hours"].values[0] == 8.0


def test_process_clock_csv_missing_column():
    """Test that missing required column raises KeyError."""
    data = [
        {"Employee Name": "Grace", "Elapsed Hours": 7.0},  # Missing Clock In Date
    ]
    df = pd.DataFrame(data)

    try:
        process_clock_csv(df, date_format="%d-%b-%y")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "Clock In Date" in str(e)
