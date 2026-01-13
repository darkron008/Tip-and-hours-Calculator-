"""Clock/timesheet CSV processing to generate daily hours summaries."""
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


def process_clock_csv(
    df: pd.DataFrame,
    employee_col: str = "Employee Name",
    date_col: str = "Clock In Date",
    hours_col: str = "Elapsed Hours",
    date_format: Optional[str] = "%d-%b-%y",
) -> pd.DataFrame:
    """Process clock/timesheet data and aggregate hours by employee and date.

    Args:
        df: Input DataFrame with clock records
        employee_col: Column name for employee names
        date_col: Column name for clock-in dates
        hours_col: Column name for elapsed hours
        date_format: Format string for parsing dates (e.g., '%d-%b-%y' for 01-Jan-25)
                     If None, pandas will infer the format.

    Returns:
        DataFrame with columns [employee_col, date_col, 'Total Daily Hours']
        sorted by employee and date.

    Raises:
        KeyError: If required columns are missing
        ValueError: If data cannot be properly converted
    """
    required_cols = [employee_col, date_col, hours_col]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        raise KeyError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    df_shifts = df[required_cols].copy()

    # Drop rows where Employee Name or Date is missing
    df_shifts.dropna(subset=[employee_col, date_col], inplace=True)

    # Convert hours to numeric, coerce errors to NaN, then drop NaN rows
    df_shifts[hours_col] = pd.to_numeric(df_shifts[hours_col], errors="coerce")
    df_shifts.dropna(subset=[hours_col], inplace=True)

    # Convert date column to datetime
    if date_format:
        # Use a pivot year of 2024 to ensure 2-digit years like '25' are interpreted as 2025+
        df_shifts[date_col] = pd.to_datetime(
            df_shifts[date_col], 
            format=date_format, 
            errors="coerce",
            utc=False
        )
    else:
        df_shifts[date_col] = pd.to_datetime(df_shifts[date_col], errors="coerce")

    # Drop rows where date conversion failed
    df_shifts.dropna(subset=[date_col], inplace=True)

    # Group by employee and date, sum the hours
    daily_hours = df_shifts.groupby([employee_col, date_col])[hours_col].sum().reset_index()
    daily_hours.rename(columns={hours_col: "Total Daily Hours"}, inplace=True)
    daily_hours.sort_values(by=[employee_col, date_col], inplace=True)

    logger.info(
        f"Processed clock data: {len(daily_hours)} records from {daily_hours[employee_col].nunique()} employees"
    )

    return daily_hours
