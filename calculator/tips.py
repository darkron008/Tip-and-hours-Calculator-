from typing import Dict, Optional, List, Union, Tuple
import logging
import io
import difflib
import pandas as pd
from calculator.clock import process_clock_csv

logger = logging.getLogger(__name__)


def read_file_to_df(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read Excel or CSV file from bytes and return DataFrame.
    
    Args:
        file_bytes: Raw file content
        filename: Original filename (used to infer format)
    
    Returns:
        pd.DataFrame
    
    Raises:
        ValueError: If file format is not supported
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    if ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(file_bytes))
    elif ext == "csv":
        return pd.read_csv(io.BytesIO(file_bytes))
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: xlsx, xls, csv")


def _normalize_df(df: pd.DataFrame, date_col: str, tips_col: str, hours_col: str, name_col: str) -> pd.DataFrame:
    required_cols = [date_col, tips_col, hours_col, name_col]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        raise KeyError(f"Missing required columns: {missing}")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df[hours_col] = pd.to_numeric(df[hours_col], errors="coerce").fillna(0.0)
    df[tips_col] = pd.to_numeric(df[tips_col], errors="coerce").fillna(0.0)
    return df


def _concat_if_needed(df_or_list: Union[pd.DataFrame, List[pd.DataFrame]]) -> pd.DataFrame:
    if isinstance(df_or_list, list):
        # concat and ignore index
        return pd.concat(df_or_list, ignore_index=True)
    return df_or_list


def _detect_columns(df: pd.DataFrame) -> Tuple[str, str, str, str]:
    """Try to heuristically detect the four required columns in a DataFrame.

    Returns (date_col, tips_col, hours_col, name_col).
    Raises KeyError if any cannot be found.
    """
    cols = [c for c in df.columns]
    lowered = {c: c.lower() for c in cols}

    # helper to find column by keywords
    def find_by_keywords(keywords):
        for orig, low in lowered.items():
            for kw in keywords:
                if kw in low:
                    return orig
        return None

    # common candidates
    date_kw = ["date", "shift", "day", "work date", "shift date"]
    tips_kw = ["tip", "tips", "gratuity", "gratuities"]
    hours_kw = ["hour", "hours", "hrs", "worked", "time"]
    name_kw = ["name", "employee", "staff", "emp"]

    date_col = find_by_keywords(date_kw)
    tips_col = find_by_keywords(tips_kw)
    hours_col = find_by_keywords(hours_kw)
    name_col = find_by_keywords(name_kw)

    # fallback: look for columns whose dtype or sample values look like dates/times
    if date_col is None:
        for c in cols:
            try:
                pd.to_datetime(df[c].dropna().iloc[:5])
                date_col = c
                break
            except Exception:
                continue

    missing = [n for n, v in (
        ("date_col", date_col),
        ("tips_col", tips_col),
        ("hours_col", hours_col),
        ("name_col", name_col),
    ) if v is None]

    # If still missing, try fuzzy matching against column names
    if missing:
        lowered_values = list(lowered.values())
        for key, kw_list in ("date_col", date_kw), ("tips_col", tips_kw), ("hours_col", hours_kw), ("name_col", name_kw):
            # only try for ones that are still missing
            if locals().get(key) is not None:
                continue
            for kw in kw_list:
                # find closest matching column lower-cased
                matches = difflib.get_close_matches(kw, lowered_values, n=1, cutoff=0.6)
                if matches:
                    # find original column name that matches the lowered match
                    low_match = matches[0]
                    for orig, low in lowered.items():
                        if low == low_match:
                            locals()[key] = orig
                            break
                if locals().get(key) is not None:
                    break

    missing = [n for n, v in (
        ("date_col", date_col),
        ("tips_col", tips_col),
        ("hours_col", hours_col),
        ("name_col", name_col),
    ) if v is None]

    if missing:
        raise KeyError(f"Could not auto-detect required columns, missing: {missing}. Columns found: {cols}")

    # Log the detected columns
    logger.info(
        f"Auto-detected columns: date_col={date_col}, tips_col={tips_col}, "
        f"hours_col={hours_col}, name_col={name_col} from columns: {cols}"
    )

    return date_col, tips_col, hours_col, name_col


def distribute_daily_tips_df(
    df_or_list: Union[pd.DataFrame, List[pd.DataFrame]],
    date_col: Optional[str],
    tips_col: Optional[str],
    hours_col: Optional[str],
    name_col: Optional[str],
    clock_df: Optional[pd.DataFrame] = None,
    clock_employee_col: Optional[str] = None,
    clock_date_col: Optional[str] = None,
    clock_hours_col: Optional[str] = None,
) -> (Dict[str, float], pd.DataFrame):
    """Distribute tips given a pre-loaded DataFrame, with optional clock data integration.
    
    If clock_df is provided, hours will be sourced from clock data instead of the tips DataFrame.
    This allows using actual timesheet hours for tip distribution rather than sales data hours.

    Returns a tuple of (final_tip_distribution_dict, export_dataframe).
    """
    df = _concat_if_needed(df_or_list)

    # Auto-detect column names when any are not provided
    if not (date_col and tips_col and hours_col and name_col):
        detected = _detect_columns(df)
        date_col, tips_col, hours_col, name_col = detected

    df = _normalize_df(df, date_col, tips_col, hours_col, name_col)

    # If clock data is provided, process it and merge with tips data
    if clock_df is not None:
        try:
            # Process clock data to get daily hours per employee
            processed_clock = process_clock_csv(
                clock_df,
                employee_col=clock_employee_col,
                date_col=clock_date_col,
                hours_col=clock_hours_col,
            )
            # Merge clock data into tips DataFrame to replace/supplement hours
            # Match by date and employee name
            df = df.merge(
                processed_clock,
                left_on=[df[date_col].dt.date, name_col],
                right_on=["Date", "Employee"],
                how="left",
            )
            # Use clock hours if available, otherwise fall back to original hours
            df[hours_col] = df["Hours"].fillna(df[hours_col])
            df = df.drop(columns=["Date", "Employee", "Hours"], errors="ignore")
            logger.info(f"Merged clock data: {len(processed_clock)} employee-date records")
        except Exception as e:
            logger.warning(f"Could not merge clock data: {e}. Using hours from tips data.")

    final_tip_distribution: Dict[str, float] = {}
    daily_groups = df.groupby(df[date_col].dt.date)

    for date, day_data in daily_groups:
        day_total_tips = float(day_data[tips_col].sum())
        day_total_staff_hours = float(day_data[hours_col].sum())

        if day_total_staff_hours <= 0 or day_total_tips == 0:
            continue

        for _, row in day_data.iterrows():
            name = row[name_col]
            employee_hours = float(row[hours_col])
            if employee_hours <= 0:
                continue
            tip_share_ratio = employee_hours / day_total_staff_hours
            employee_daily_tip = day_total_tips * tip_share_ratio
            final_tip_distribution[name] = final_tip_distribution.get(name, 0.0) + employee_daily_tip

    export_df = pd.DataFrame(list(final_tip_distribution.items()), columns=["Employee Name", "Total Tip Share"])
    return final_tip_distribution, export_df


def distribute_daily_tips(
    input_file_path: Union[str, List[str]],
    output_file_path: str,
    date_col: str,
    tips_col: str,
    hours_col: str,
    name_col: str,
) -> Optional[Dict[str, float]]:
    """Backward-compatible wrapper: read from path and write to path using the df-based helper."""
    # Allow a single path or a list of paths
    if isinstance(input_file_path, list):
        dfs = [pd.read_excel(p) for p in input_file_path]
        df = pd.concat(dfs, ignore_index=True)
    else:
        df = pd.read_excel(input_file_path)

    final, export_df = distribute_daily_tips_df(df, date_col, tips_col, hours_col, name_col)
    export_df.to_excel(output_file_path, index=False, sheet_name="Tip Distribution Summary")
    return final
