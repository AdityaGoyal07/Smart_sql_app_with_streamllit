# sanitizer.py
import re
import pandas as pd

def sanitize_filename(filename):
    """
    Sanitize a file name to be URL and storage safe (no spaces or special characters).
    """
    name, ext = filename.rsplit('.', 1)
    name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    name = re.sub(r'_{2,}', '_', name).strip('_').lower()
    return f"{name}.{ext.lower()}"

def sanitize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize DataFrame column names to be SQL-safe and consistent.
    """
    clean_columns = []
    seen = set()
    for col in df.columns:
        clean = re.sub(r'[^a-zA-Z0-9]', '_', col)
        clean = re.sub(r'_{2,}', '_', clean).strip('_').lower()
        if clean in seen:
            i = 1
            while f"{clean}_{i}" in seen:
                i += 1
            clean = f"{clean}_{i}"
        seen.add(clean)
        clean_columns.append(clean)
    df.columns = clean_columns
    return df
