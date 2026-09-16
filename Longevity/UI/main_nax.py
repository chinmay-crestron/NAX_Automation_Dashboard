import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
 
# -----------------------------
# 1. IP Selection Dropdown
# -----------------------------
option = st.selectbox(
    "Select IP to view data",
    [
        "172.18.88.3",
        "172.18.88.15",
        "172.18.88.48",
        "172.18.88.18",
        "172.18.88.17",
        "172.18.88.19",
        "172.18.88.16"
    ]
)
 
# -----------------------------
# 2. Load CSV
# -----------------------------
csv_path = r"C:\runData_BTIO\event.csv"
 
columns = [
    "Date",
    "IP",
    "Model",
    "Uptime (Days)",
    "RAM Usage (%)",
    "Val3",
    "Val4",
    "Val5",
    "Val6",
    "Val7",
    "Val8",
    "Val9"
]
 
df = pd.read_csv(csv_path, names=columns)
 
# -----------------------------
# 3. Convert Numeric Columns
# -----------------------------
df["Uptime (Days)"] = pd.to_numeric(
    df["Uptime (Days)"],
    errors="coerce"
)
 
df["RAM Usage (%)"] = pd.to_numeric(
    df["RAM Usage (%)"],
    errors="coerce"
)
 
# -----------------------------
# 4. Create Timestamp
# CSV Date format : MM-DD
# -----------------------------
current_year = datetime.now().year
current_month = datetime.now().month
 
df["Timestamp"] = pd.to_datetime(
    df["Date"] + f"-{current_year}",
    format="%m-%d-%Y",
    errors="coerce"
)
 
# Handle year rollover
mask = df["Timestamp"].dt.month > current_month
 
df.loc[mask, "Timestamp"] = (
    df.loc[mask, "Timestamp"] - pd.DateOffset(years=1)
)
 
# Remove invalid rows
df = df.dropna(
    subset=[
        "Timestamp",
        "Uptime (Days)",
        "RAM Usage (%)"
    ]
)
 
# -----------------------------
# 5. Filter by Selected IP
# -----------------------------
filtered_df = df[df["IP"] == option].copy()
 
# Sort chronologically
filtered_df = filtered_df.sort_values("Timestamp")

# -----------------------------
# 5A. Display Model Name
# -----------------------------
if not filtered_df.empty:
    model_name = filtered_df.iloc[0]["Model"]
    st.title(model_name)
 
# -----------------------------
# 6. Load Uptime Text File
# -----------------------------
uptime_path = fr"C:\runData_BTIO\{option}_uptime.txt"
 
try:
    with open(uptime_path, "r") as f:
        textfile = f.read()
        st.write(textfile)
except Exception as e:
    st.error(f"Error reading uptime file: {e}")
 
# -----------------------------
# 7. Display Data
# Show only required columns
# -----------------------------
st.write(f"Data for IP: {option}")
 
display_df = filtered_df[
    [
        "Date",
        "IP",
        "Model",
        "Uptime (Days)",
        "RAM Usage (%)"
    ]
]
 
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)
 
# -----------------------------
# 8. Plot Latest 30 Records
# -----------------------------
if not filtered_df.empty:
 
   # Get latest 30 unique timestamps (days)
    latest_dates = (
        filtered_df["Timestamp"]
        .drop_duplicates()
        .sort_values()
        .tail(30)
    )
    
    # Keep all records from those dates
    graph_df = (
        filtered_df[
            filtered_df["Timestamp"].isin(latest_dates)
        ]
        .sort_values("Timestamp")
        .reset_index(drop=True)
    )
 
    # Sequential X-axis
    x_values = list(range(len(graph_df)))
 
    # Show roughly 10 labels to avoid clutter
    label_step = max(1, len(graph_df) // 10)
 
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(18, 10)
    )
 
    # -------------------------
    # Uptime Graph
    # -------------------------
    ax1.plot(
        x_values,
        graph_df["Uptime (Days)"],
        marker='o',
        linestyle='-',
        linewidth=2,
        color='blue'
    )
 
    ax1.set_title("Uptime (Days) ")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Uptime (Days)")
    ax1.grid(True)
 
    ax1.set_xticks(
        x_values[::label_step]
    )
 
    ax1.set_xticklabels(
        graph_df["Date"][::label_step],
        rotation=45,
        ha="right"
    )
 
    # -------------------------
    # RAM Usage Graph
    # -------------------------
    ax2.plot(
        x_values,
        graph_df["RAM Usage (%)"],
        marker='o',
        linestyle='-',
        linewidth=2,
        color='orange'
    )
 
    ax2.set_title("RAM Usage (%) ")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("RAM Usage (%)")
    ax2.set_ylim(0, 100)
    ax2.set_yticks(np.arange(0, 101, 10))
    ax2.grid(True)
 
    ax2.set_xticks(
        x_values[::label_step]
    )
 
    ax2.set_xticklabels(
        graph_df["Date"][::label_step],
        rotation=45,
        ha="right"
    )
 
    plt.tight_layout(pad=3.0)
 
    st.pyplot(fig)
 
else:
    st.warning(f"No data found for IP: {option}")