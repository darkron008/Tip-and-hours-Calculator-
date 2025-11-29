"""Sales data processing to extract daily tip amounts."""
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


def process_sales_csv(
    df: pd.DataFrame,
    tips_row_label: str = "Tips",
    sales_col_label: str = "Sales",
    data_start_col: int = 2,
) -> pd.DataFrame:
    """Extract daily tip amounts from a sales report CSV.

    Typical sales CSVs have a structure where:
    - One row contains "Tips" in the 'Sales' column
    - Dates are spread across columns (starting from a certain column)
    - Tip amounts are in the corresponding cells in the Tips row

    Args:
        df: Input DataFrame with sales data
        tips_row_label: Value in the 'Sales' column that identifies the Tips row (e.g., "Tips")
        sales_col_label: Name of the column containing row labels (e.g., "Sales")
        data_start_col: Column index where date/data values start (0-indexed, default 2)

    Returns:
        DataFrame with columns ['Date', 'Tip Amount'] sorted by date.

    Raises:
        ValueError: If Tips row cannot be found or data is malformed
    """
    # Ensure the sales column exists
    if sales_col_label not in df.columns:
        raise ValueError(f"Column '{sales_col_label}' not found. Available columns: {list(df.columns)}")

    # Find the Tips row
    tips_rows = df[df[sales_col_label] == tips_row_label]
    if tips_rows.empty:
        raise ValueError(f"Could not find row with '{sales_col_label}' == '{tips_row_label}'")

    tips_row = tips_rows.iloc[0]

    # Extract dates from the first data row
    first_data_row = df.iloc[0]
    dates = first_data_row.iloc[data_start_col:].tolist()

    # Extract tip values from the Tips row
    tip_values = tips_row.iloc[data_start_col:].tolist()

    # Create DataFrame
    daily_tips_df = pd.DataFrame({
        "Date": dates,
        "Tip Amount": tip_values,
    })

    # Clean Tip Amount: remove currency symbols, commas, and handle negative values in parentheses
    daily_tips_df["Tip Amount"] = (
        daily_tips_df["Tip Amount"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.strip()
    )

    # Convert to numeric
    daily_tips_df["Tip Amount"] = pd.to_numeric(daily_tips_df["Tip Amount"], errors="coerce")

    # Convert dates to strings to preserve them (don't coerce to NaN)
    daily_tips_df["Date"] = daily_tips_df["Date"].astype(str).str.strip()

    # Remove rows where Tip Amount is NaN
    daily_tips_df.dropna(subset=["Tip Amount"], inplace=True)

    # Remove rows where Date is empty or invalid
    daily_tips_df = daily_tips_df[daily_tips_df["Date"].notna() & (daily_tips_df["Date"] != "")]

    # Try to convert dates to datetime for sorting (but don't drop if conversion fails)
    try:
        daily_tips_df_sorted = daily_tips_df.copy()
        daily_tips_df_sorted["Date_dt"] = pd.to_datetime(daily_tips_df_sorted["Date"], errors="coerce")
        # Only use date sorting if most dates converted successfully
        valid_dates = daily_tips_df_sorted["Date_dt"].notna().sum()
        if valid_dates > len(daily_tips_df_sorted) / 2:
            daily_tips_df_sorted = daily_tips_df_sorted.sort_values(by="Date_dt")
            daily_tips_df = daily_tips_df_sorted.drop(columns=["Date_dt"])
        else:
            daily_tips_df.sort_values(by="Date", inplace=True)
    except Exception as e:
        logger.warning(f"Could not parse dates as datetime: {e}. Sorting as strings.")
        daily_tips_df.sort_values(by="Date", inplace=True)

    logger.info(f"Extracted {len(daily_tips_df)} daily tip records from sales data")

    return daily_tips_df
