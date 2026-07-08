import pandas as pd

# Read the CSV
df = pd.read_csv("ns_ge2022_results.csv")

# Columns to fill
columns_to_fill = [
    "NO. KOD DAERAH MENGUNDI",
    "NAMA PUSAT MENGUNDI"
]

# Replace empty strings with NaN (just in case)
df[columns_to_fill] = df[columns_to_fill].replace("", pd.NA)

# Copy the previous non-empty value down (NOT drag fill)
df[columns_to_fill] = df[columns_to_fill].ffill()

# Save the completed CSV
df.to_csv("ns_ge2022_results_filled.csv", index=False)

print("Done! Saved as ns_ge2022_results_filled.csv")