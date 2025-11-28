from typing import Dict, Optional
import pandas as pd


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


def distribute_daily_tips_df(
    df: pd.DataFrame,
    date_col: str,
    tips_col: str,
    hours_col: str,
    name_col: str,
) -> (Dict[str, float], pd.DataFrame):
    """Distribute tips given a pre-loaded DataFrame.

    Returns a tuple of (final_tip_distribution_dict, export_dataframe).
    """
    df = _normalize_df(df, date_col, tips_col, hours_col, name_col)

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
    input_file_path: str,
    output_file_path: str,
    date_col: str,
    tips_col: str,
    hours_col: str,
    name_col: str,
) -> Optional[Dict[str, float]]:
    """Backward-compatible wrapper: read from path and write to path using the df-based helper."""
    df = pd.read_excel(input_file_path)
    final, export_df = distribute_daily_tips_df(df, date_col, tips_col, hours_col, name_col)
    export_df.to_excel(output_file_path, index=False, sheet_name="Tip Distribution Summary")
    return final
