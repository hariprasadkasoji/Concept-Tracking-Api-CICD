# app/services/dataframe_utils.py
import pandas as pd
import numpy as np

# Operator keys match AG Grid's own filter option names exactly — no
# translation layer needed on the frontend. filterOptions sent to the
# grid, the filterModel it sends back, and what this module matches on
# are all the same vocabulary.
FILTER_OPERATIONS = {
    "string": [
        "contains",
        "notContains",
        "equals",
        "notEqual",
        "startsWith",
        "endsWith"
    ],
    "number": [
        "equals",
        "notEqual",
        "greaterThan",
        "lessThan",
        "greaterThanOrEqual",
        "lessThanOrEqual"
    ],
    "float": [
        "equals",
        "notEqual",
        "greaterThan",
        "lessThan",
        "greaterThanOrEqual",
        "lessThanOrEqual"
    ],
    "date": [
        "equals",
        "notEqual",
        "greaterThan",   # "after"
        "lessThan",      # "before"
        "inRange"        # "between"
    ],
    "datetime": [
        "equals",
        "notEqual",
        "greaterThan",
        "lessThan",
        "inRange"
    ]
}


def apply_filters_on_df(df: pd.DataFrame, filter_model: dict) -> pd.DataFrame:
    if not filter_model:
        return df

    for col, rule in filter_model.items():
        if col not in df.columns:
            continue

        ftype = rule.get("filterType", "").lower()
        op = rule.get("type", "")
        value = rule.get("filter")

        if ftype in ["string", "text"]:
            if value is None:
                continue
            value = str(value)
            if op == "contains":
                mask = df[col].astype(str).str.contains(value, case=False, na=False)
            elif op == "notContains":
                mask = ~df[col].astype(str).str.contains(value, case=False, na=False)
            elif op == "equals":
                mask = df[col].astype(str).str.strip() == value.strip()
            elif op == "notEqual":
                mask = df[col].astype(str).str.strip() != value.strip()
            elif op == "startsWith":
                mask = df[col].astype(str).str.startswith(value, na=False)
            elif op == "endsWith":
                mask = df[col].astype(str).str.endswith(value, na=False)
            else:
                logger_skip(col, op, ftype)
                continue

        elif ftype in ["number", "float"]:
            if value is None:
                continue
            numeric_col = pd.to_numeric(
                df[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip(),
                errors="coerce"
            )
            if op == "equals":
                mask = numeric_col == float(value)
            elif op == "notEqual":
                mask = numeric_col != float(value)
            elif op == "greaterThan":
                mask = numeric_col > float(value)
            elif op == "lessThan":
                mask = numeric_col < float(value)
            elif op == "greaterThanOrEqual":
                mask = numeric_col >= float(value)
            elif op == "lessThanOrEqual":
                mask = numeric_col <= float(value)
            else:
                logger_skip(col, op, ftype)
                continue

        elif ftype == "date":
            datefrom = rule.get("dateFrom")
            dateto = rule.get("dateTo")
            if not datefrom:
                continue

            # Normalize to date-only (strip time-of-day) on both sides. AG Grid's
            # date filter only ever lets the user pick a calendar day — dateFrom
            # always arrives as midnight ("2026-07-04 00:00:00") regardless of
            # what time the actual row was created. Comparing full timestamps
            # would make equals/greaterThan/lessThan almost never match once
            # CreatedDate started carrying a real time component.
            date_col = pd.to_datetime(df[col], errors="coerce").dt.normalize()
            datefrom_dt = pd.to_datetime(datefrom, errors="coerce").normalize()

            if op == "equals":
                mask = date_col == datefrom_dt
            elif op == "notEqual":
                mask = date_col != datefrom_dt
            elif op == "greaterThan":       # "after"
                mask = date_col > datefrom_dt
            elif op == "lessThan":          # "before"
                mask = date_col < datefrom_dt
            elif op == "inRange":           # "between"
                dateto_dt = pd.to_datetime(dateto, errors="coerce").normalize()
                mask = (date_col >= datefrom_dt) & (date_col <= dateto_dt)
            else:
                logger_skip(col, op, ftype)
                continue
        else:
            continue

        df = df[mask].reset_index(drop=True)

    return df


def logger_skip(col: str, op: str, ftype: str) -> None:
    import logging
    logging.getLogger(__name__).warning(
        "Unrecognized filter op '%s' for column '%s' (filterType=%s) — filter skipped", op, col, ftype
    )


def apply_sort_on_df(df: pd.DataFrame, sort_model: list) -> pd.DataFrame:
    if not sort_model:
        return df

    sort_cols, ascending = [], []
    for item in sort_model:
        if not isinstance(item, dict):
            continue
        col = item.get("colId")
        direction = item.get("sort", "asc")
        if not col or col not in df.columns:
            continue
        sort_cols.append(col)
        ascending.append(direction == "asc")

    if not sort_cols:
        return df

    return df.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True)


def infer_column_metadata(df: pd.DataFrame, filter_operations: dict) -> dict:
    """Infer column type + allowed filter ops (AG Grid-native names) directly
    from the dataframe dtype, since dashboard-concepts has no COMMON_LAYOUT
    to look up types from."""
    metadata = {}
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_datetime64_any_dtype(dtype):
            col_type = "date"
        elif pd.api.types.is_numeric_dtype(dtype):
            col_type = "number"
        else:
            col_type = "string"
        metadata[col] = {
            "type": col_type,
            "filterOperations": filter_operations.get(col_type, [])
        }
    return metadata


def coerce_date_columns(df: pd.DataFrame, date_column_names: set[str] | None = None) -> pd.DataFrame:
    """Converts columns that are actually dates (but arrived as strings from
    the DB cursor) into real datetime64 dtype, so infer_column_metadata can
    correctly classify them as 'date' instead of falling through to 'string'.
    """
    date_column_names = date_column_names or set()

    for col in df.columns:
        if df[col].dtype != object:
            continue

        is_known_date_col = col in date_column_names or "date" in col.lower()

        parsed = pd.to_datetime(df[col], errors="coerce")
        non_null = df[col].notna().sum()
        parsed_ok = parsed.notna().sum()

        if non_null == 0:
            continue

        parse_rate = parsed_ok / non_null

        if is_known_date_col or parse_rate >= 0.95:
            df[col] = parsed

    return df


def apply_quick_search(df: pd.DataFrame, search_text: str | None) -> pd.DataFrame:
    if not search_text or not search_text.strip():
        return df
    text = search_text.strip()
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask = mask | df[col].astype(str).str.contains(text, case=False, na=False, regex=False)
    return df[mask]