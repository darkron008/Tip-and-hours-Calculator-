"""Tests for sales data processing."""
import pandas as pd
from calculator.sales import process_sales_csv


def test_process_sales_csv_basic():
    """Test basic sales CSV processing."""
    # Row 0 contains dates, Row 1 contains item labels, Row 2 contains Tips
    data = {
        "Sales": ["2025-01-01", "Item A", "Tips"],
        "Metric": ["2025-01-02", "units", "150.00"],
        "Col3": ["2025-01-03", 10, 120.00],
    }
    df = pd.DataFrame(data)

    result = process_sales_csv(df, data_start_col=1)

    assert len(result) == 2
    assert "Tip Amount" in result.columns
    assert "Date" in result.columns
    # Check that we got values
    assert 150.0 in result["Tip Amount"].values
    assert 120.0 in result["Tip Amount"].values


def test_process_sales_csv_with_currency():
    """Test sales CSV with currency formatting."""
    data = {
        "Sales": ["Jan 01", "Product", "Tips"],
        "Category": ["Jan 02", "count", "$450.50"],
        "Col3": ["Jan 03", 3, "$(500.00)"],
    }
    df = pd.DataFrame(data)

    result = process_sales_csv(df, data_start_col=1)

    assert len(result) == 2
    # Check that we extracted tip amounts with currency cleaned
    assert all(isinstance(val, (int, float)) for val in result["Tip Amount"])
    # Should have -500.0 (from parentheses) and 450.5 (from dollars)
    assert -500.0 in result["Tip Amount"].values
    assert 450.5 in result["Tip Amount"].values


def test_process_sales_csv_custom_row_label():
    """Test sales CSV with custom Tips row label."""
    data = {
        "Category": ["Mon", "Sales", "Gratuity"],
        "Week": ["Tue", "items", ""],
        "Col3": ["Wed", 10, 85.25],
    }
    df = pd.DataFrame(data)

    result = process_sales_csv(
        df,
        tips_row_label="Gratuity",
        sales_col_label="Category",
        data_start_col=1,
    )

    assert len(result) >= 1
    assert "Tip Amount" in result.columns


def test_process_sales_csv_missing_tips_row():
    """Test that missing Tips row raises ValueError."""
    data = {
        "Sales": ["", "Item A", "Item B"],
        "Metric": ["", "count", ""],
        "Date 1": ["", 10, 15],
        "Date 2": ["", 20, 25],
    }
    df = pd.DataFrame(data)

    try:
        process_sales_csv(df)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Tips" in str(e)


def test_process_sales_csv_with_nan_values():
    """Test that NaN values are handled gracefully."""
    data = {
        "Sales": ["Date 1", "Item", "Tips"],
        "Metric": ["Date 2", "qty", ""],
        "Col3": ["Date 3", 10, 200.0],
    }
    df = pd.DataFrame(data)

    result = process_sales_csv(df, data_start_col=1)

    # Should have valid records
    assert len(result) >= 1
    assert "Tip Amount" in result.columns
