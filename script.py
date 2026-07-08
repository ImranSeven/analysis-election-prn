"""
Normalize the 'parlimen' and 'dun' columns in a dataset:
    "N.01 Chennah"  -> "N01 CHENNAH"
    "P.126 Jelebu"  -> "P126 JELEBU"

Usage:
    python normalize_dun_parlimen.py input.csv

This will overwrite input.csv in place with the normalized values.

If your file is Excel instead of CSV, see the commented-out lines below
for pd.read_excel / to_excel.
"""

import re
import pandas as pd

# Set your file path once here
# INPUT_PATH = "Data/nsn_se15_2023.csv"
INPUT_PATH = "Data/ge15_2022.csv"


def normalize_dun(value):
    """For 'dun': remove the dot in codes like 'N.01' -> 'N01', then uppercase the whole string."""
    if pd.isna(value):
        return value
    text = str(value).strip()
    # Remove a dot that sits between a letter-prefix and digits, e.g. N.01 -> N01
    text = re.sub(r'^([A-Za-z]+)\.(\d+)', r'\1\2', text)
    return text.upper()


def normalize_parlimen(value):
    """For 'parlimen': keep the dot as-is, just uppercase the whole string, e.g. P.126 Jelebu -> P.126 JELEBU."""
    if pd.isna(value):
        return value
    return str(value).strip().upper()


def main():
    # --- CSV ---
    df = pd.read_csv(INPUT_PATH)

    # --- Excel (uncomment if needed instead of the CSV line above) ---
    # df = pd.read_excel(INPUT_PATH)

    if "dun" in df.columns:
        df["dun"] = df["dun"].apply(normalize_dun)
    else:
        print("Warning: column 'dun' not found in the file.")

    if "parlimen" in df.columns:
        df["parlimen"] = df["parlimen"].apply(normalize_parlimen)
    else:
        print("Warning: column 'parlimen' not found in the file.")

    # --- CSV (overwrite the same file) ---
    df.to_csv(INPUT_PATH, index=False)

    # --- Excel (uncomment if needed instead of the CSV line above) ---
    # df.to_excel(INPUT_PATH, index=False)

    print(f"Done. Overwrote normalized data in: {INPUT_PATH}")


if __name__ == "__main__":
    main()