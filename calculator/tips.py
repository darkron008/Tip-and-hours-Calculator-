from typing import Dict, Optional, List, Union, Tuple
import logging
import io
import difflib
import pandas as pd
from calculator.clock import process_clock_csv

logger = logging.getLogger(__name__)


def is_clock_file(df: pd.DataFrame, filename: str = None) -> bool:
    """Heuristically determine if a DataFrame is clock/timesheet data.
    
    Clock files typically have:
    - Employee/name column
    - Date column
    - Hours column (but NOT tips column)
    
    If filename is provided, uses it as a strong indicator (e.g., "clock" in filename).
    
    Returns True if likely a clock file, False otherwise.
    """
    # Check filename first if provided - strong indicator
    if filename:
        filename_lower = filename.lower()
        if 'clock' in filename_lower or 'timesheet' in filename_lower:
            return True
        if 'sales' in filename_lower or 'tip' in filename_lower:
            return False
    
    # Convert column names to lowercase strings, handling non-string types
    cols_lower = {str(c).lower() for c in df.columns}
    
    # Check for keywords in column names
    has_employee = any(kw in col for col in cols_lower for kw in ['employee', 'name', 'staff', 'emp'])
    has_date = any(kw in col for col in cols_lower for kw in ['date', 'shift', 'clock'])
    has_hours = any(kw in col for col in cols_lower for kw in ['hour', 'hours', 'hrs', 'elapsed', 'time'])
    has_tips = any(kw in col for col in cols_lower for kw in ['tip', 'tips', 'gratuity', 'gratuities'])
    
    # Clock file: has employee, date, hours but NOT tips
    return has_employee and has_date and has_hours and not has_tips


def read_file_to_df(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read Excel or CSV file from bytes and return DataFrame.
    
    Attempts to detect and skip report headers and multi-row headers.
    
    Args:
        file_bytes: Raw file content
        filename: Original filename (used to infer format)
    
    Returns:
        pd.DataFrame
    
    Raises:
        ValueError: If file format is not supported
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    # Read WITHOUT header first so we can examine all rows
    if ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), header=None)
    elif ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes), header=None)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: xlsx, xls, csv")
    
    # Now find the actual header row by scanning from top
    header_idx = 0
    if len(df) > 1:
        for idx in range(min(15, len(df))):
            row = df.iloc[idx]
            row_str = ' '.join(str(c).lower() for c in row)
            
            # Skip rows that are clearly not headers:
            # - Row is mostly NaN/empty
            # - Row contains "report" or "sales" (report title rows)
            non_empty = sum(1 for v in row if not pd.isna(v) and str(v).strip() != "")
            has_report_keyword = any(kw in row_str for kw in ['report', 'sales', 'summary', 'total'])
            
            if non_empty < len(df.columns) * 0.4:  # Less than 40% filled
                continue
            if has_report_keyword and non_empty < len(df.columns) * 0.7:  # Report line but sparse
                continue
                
            # This looks like a header row
            header_idx = idx
            logger.info(f"Found header at row {idx}: {list(row)[:5]}...")
            break
    
    # Apply the header
    header_row = [str(x).strip() for x in df.iloc[header_idx]]
    df = df.iloc[header_idx + 1:].reset_index(drop=True)
    df.columns = header_row
    
    logger.info(f"Applied header from row {header_idx}. Columns: {list(df.columns)}")
    
    return df


def _is_transposed_sales_report(df: pd.DataFrame) -> bool:
    """Check if this is a transposed sales report with Tips row."""
    if len(df) < 2:
        return False
    # Check for a 'Tips' row indicator (usually in first column)
    first_col = df.iloc[:, 0] if len(df.columns) > 0 else None
    if first_col is None:
        return False
    has_tips_row = any('tip' in str(v).lower() for v in first_col)
    return has_tips_row


def _extract_from_transposed_sales_report(file_bytes: bytes, filename: str) -> Optional[pd.DataFrame]:
    """
    Extract daily tips from a transposed sales report format where:
    - Dates are in a header row (typically around row 9)
    - Tips values are in a 'Tips' labeled row
    - Each column represents a day
    
    Returns a DataFrame with 'Date' and 'Tip Amount' columns, or None if not this format.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    try:
        # Try reading with no header first to find the date row
        if ext in ("xlsx", "xls"):
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
        elif ext == "csv":
            df_raw = pd.read_csv(io.BytesIO(file_bytes), header=None)
        else:
            return None
        
        # Look for a row that contains dates (typically has many date-like values)
        # Focus on rows with date patterns like "28-Jun", "29-Jun", etc.
        date_row_idx = None
        for idx in range(min(15, len(df_raw))):
            row = df_raw.iloc[idx]
            # Try to parse values as dates, but prefer short date formats like "28-Jun"
            date_count = 0
            short_date_count = 0
            for val in row[1:]:  # Skip first column (usually row label)
                val_str = str(val).strip()
                if not val_str or pd.isna(val):
                    continue
                # Check for short date format (e.g., "28-Jun", "1-Jul")
                if len(val_str) <= 10 and '-' in val_str and any(c.isalpha() for c in val_str):
                    short_date_count += 1
                try:
                    pd.to_datetime(val_str)
                    date_count += 1
                except:
                    pass
            
            # Prefer short date formats, but accept if majority can be parsed as dates
            if short_date_count >= len(row[1:]) * 0.8:  # 80% short date format
                date_row_idx = idx
                logger.info(f"Found date row at index {idx} (short date format)")
                break
            elif date_count >= len(row[1:]) * 0.8 and idx > 2:  # Avoid early rows with mixed text
                date_row_idx = idx
                logger.info(f"Found date row at index {idx}")
                break
        
        if date_row_idx is None:
            return None
        
        # Look for Tips row - check for variations like "Tips", "Total", "Gratuity", etc.
        tips_row_idx = None
        tip_keywords = ['tip', 'total', 'gratuity', 'gratuities', 'distributed']
        for idx in range(len(df_raw)):
            row_label = str(df_raw.iloc[idx, 0]).lower().strip()
            if any(kw in row_label for kw in tip_keywords):
                tips_row_idx = idx
                logger.info(f"Found Tips row at index {idx} with label: {df_raw.iloc[idx, 0]}")
                break
        
        if tips_row_idx is None:
            logger.debug("No Tips row found - not a transposed sales report")
            return None
        
        # Extract dates and tips
        dates = df_raw.iloc[date_row_idx, 1:].tolist()
        tip_values = df_raw.iloc[tips_row_idx, 1:].tolist()
        
        logger.debug(f"Extracted {len(dates)} dates and {len(tip_values)} tip values")
        
        # Create DataFrame with a placeholder employee name since transposed format doesn't have employee info
        daily_tips_df = pd.DataFrame({
            'Employee': 'Daily Tips',  # Placeholder - transposed format doesn't track individual employees
            'Date': dates,
            'Hours': 1,  # Placeholder - will be replaced with clock data if available
            'Tips': tip_values
        })
        
        logger.debug(f"Created DataFrame with {len(daily_tips_df)} rows")
        
        # Clean Tips column
        daily_tips_df['Tips'] = (
            daily_tips_df['Tips']
            .astype(str)
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
            .str.replace('(', '-', regex=False)
            .str.replace(')', '', regex=False)
            .str.strip()
        )
        daily_tips_df['Tips'] = pd.to_numeric(daily_tips_df['Tips'], errors='coerce')
        
        logger.debug(f"After tip column cleaning, {daily_tips_df['Tips'].notna().sum()} non-NaN tips")
        
        # Convert dates - try multiple formats since the file might have dates like "28-Jun" without year
        logger.debug(f"Sample dates before conversion: {daily_tips_df['Date'].head(3).tolist()}")
        
        # First try parsing with explicit format handling
        def parse_date(date_str):
            if pd.isna(date_str) or str(date_str).strip() == '':
                return pd.NaT
            try:
                # Try direct parsing first
                return pd.to_datetime(date_str)
            except:
                try:
                    # If that fails, try common formats like "28-Jun" (add current/report year)
                    # For this file, dates are from Jun-Jul 2025
                    return pd.to_datetime(f"{date_str}-25", format="%d-%b-%y")
                except:
                    return pd.NaT
        
        daily_tips_df['Date'] = daily_tips_df['Date'].apply(parse_date)
        
        logger.debug(f"After date conversion, {daily_tips_df['Date'].notna().sum()} valid dates")
        logger.debug(f"Sample dates after conversion: {daily_tips_df['Date'].head(3).tolist()}")
        
        # Remove rows with NaN dates or tips
        daily_tips_df = daily_tips_df.dropna(subset=['Date', 'Tips'])
        
        logger.info(f"Extracted {len(daily_tips_df)} daily tips from transposed sales report")
        return daily_tips_df if len(daily_tips_df) > 0 else None
        
    except Exception as e:
        logger.debug(f"Not a transposed sales report: {type(e).__name__}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


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
    
    If columns are not found and many columns have "Unnamed" in them,
    tries skipping the first row and rereading.
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
    
    If clock_df is provided, hours will be sourced from clock data.
    If df_or_list is None or empty, uses clock data only for tip distribution calculation.

    Returns a tuple of (final_tip_distribution_dict, export_dataframe).
    """
    # Handle case where only clock data is provided (no tips file)
    if df_or_list is None or (isinstance(df_or_list, list) and not df_or_list):
        if clock_df is None:
            raise ValueError("Either tips/sales data or clock data must be provided")
        
        # Use clock data as the primary data source
        df = clock_df.copy()
        
        # Detect or use provided clock columns
        if clock_employee_col is None or clock_date_col is None or clock_hours_col is None:
            # Try to auto-detect clock columns
            cols_lower = {c.lower() for c in df.columns}
            if clock_employee_col is None:
                clock_employee_col = next((c for c in df.columns if c.lower() in ['employee', 'name', 'staff']), None)
            if clock_date_col is None:
                clock_date_col = next((c for c in df.columns if c.lower() in ['date', 'shift date', 'clock in date']), None)
            if clock_hours_col is None:
                clock_hours_col = next((c for c in df.columns if c.lower() in ['hours', 'elapsed hours', 'hrs']), None)
        
        if not all([clock_employee_col, clock_date_col, clock_hours_col]):
            raise ValueError("Could not detect required clock columns: employee, date, hours")
        
        # Rename clock columns to standard names for processing
        df = df.rename(columns={
            clock_employee_col: 'Employee',
            clock_date_col: 'Date',
            clock_hours_col: 'Hours'
        })
        
        # Create a simple summary: employee total tips (using hours as proxy if no tips)
        df['Date'] = pd.to_datetime(df['Date'])
        df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce').fillna(0.0)
        
        summary = df.groupby('Employee')['Hours'].sum().reset_index()
        summary.columns = ['Employee Name', 'Total Tip Share']  # Use Hours as proxy for tips
        
        logger.info(f"Using clock data only: {len(summary)} employees")
        return {}, summary
    
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
