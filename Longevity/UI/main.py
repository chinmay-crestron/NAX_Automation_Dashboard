import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# IP selection dropdown
option = st.selectbox(
    "Select IP to view data",
    ["10.253.80.50","10.253.80.238","10.253.73.84","10.253.80.118",
     "10.253.73.82","10.253.73.83","10.253.80.49","10.253.73.81",
     "10.253.81.2","10.253.81.27","10.253.80.77","10.253.80.66","10.253.81.30","10.253.73.56"]
)

# Load CSV data
csv_path = 'C:\\runData\\event.csv'
df = pd.read_csv(csv_path)

# Filter data for selected IP
if 'IP' in df.columns:
    filtered_df = df[df['IP'] == option]
elif 'ip' in df.columns:
    filtered_df = df[df['ip'] == option]
else:
    filtered_df = df
    st.warning("No IP column found in the data. Showing all data.")

# Load uptime text file
uptime_path = f"C:\\runData\\{option}_uptime.txt"
try:
    with open(uptime_path, "r") as f:
        textfile = f.read()
    st.write(textfile)
except Exception as e:
    st.error(f"Error reading uptime file: {e}")

# Display filtered data
st.write(f"Data for IP: {option}")
st.dataframe(filtered_df)

# Plotting graphs vertically
if not filtered_df.empty:
    # Uptime plot
    fig1, ax1 = plt.subplots(figsize=(10, 4))
    ax1.plot(filtered_df['Timestamp'], filtered_df['Uptime (Days)'], marker='o')
    ax1.set_title('Uptime (Days) vs Timestamp')
    ax1.set_xlabel('Timestamp')
    ax1.set_ylabel('Uptime (Days)')
    ax1.tick_params(axis='x', rotation=45)
    st.pyplot(fig1)

    # RAM Usage plot
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.plot(filtered_df['Timestamp'], filtered_df['RAM Usage (%)'], marker='o', color='orange')
    ax2.set_title('RAM Usage (%) vs Timestamp')
    ax2.set_xlabel('Timestamp')
    ax2.set_ylabel('RAM Usage (%)')
    ax2.set_yticks(np.arange(0, 101, 10))  # Y-axis ticks at intervals of 10
    ax2.tick_params(axis='x', rotation=45)
    st.pyplot(fig2)
else:
    st.warning(f"No data found for IP: {option}")
