import sys
import os
import re
from datetime import datetime
from csv import writer
import ssh

def monitor_ip(ip, password):
    # Initialize metrics
    UserCPU = sysCPU = nicCPU = idleCPU = ioCPU = irqCPU = sirqCPU = ramUsage = uptime_days = ""
    uptime_output = ""

    # RAM Usage
    try:
        output, error = ssh.ssh_command(ip, 22, "admin", password, "ramfree\n")
        print(f"[{ip}] RAM Output:", output)
        split = output.replace("\r\n", "").split(" percent of memory in use")
        ramUsage = split[0].replace(" ", "") if split else "N/A"
    except Exception as e:
        print(f"[{ip}] Error getting RAM usage: {str(e)}")
        ramUsage = "N/A"

    # CPU Usage
    try:
        cpuoutput, error = ssh.ssh_command(ip, 22, "admin", password, "cpuload\n")
        print(f"[{ip}] CPU Output:", cpuoutput)

        for line in cpuoutput.split("\r\n"):
            if "CPU:" in line:
                matches = re.findall(r"([\d\.]+)%\s*(usr|sys|nic|idle|io|irq|sirq)", line)
                cpu_dict = {key: value for value, key in matches}
                UserCPU = cpu_dict.get("usr", "N/A")
                sysCPU = cpu_dict.get("sys", "N/A")
                nicCPU = cpu_dict.get("nic", "N/A")
                idleCPU = cpu_dict.get("idle", "N/A")
                ioCPU = cpu_dict.get("io", "N/A")
                irqCPU = cpu_dict.get("irq", "N/A")
                sirqCPU = cpu_dict.get("sirq", "N/A")
    except Exception as e:
        print(f"[{ip}] Error getting CPU usage: {str(e)}")
        UserCPU = sysCPU = nicCPU = idleCPU = ioCPU = irqCPU = sirqCPU = "N/A"

    # Timestamp
    now = datetime.now()
    datetime_string = now.strftime("%m-%d")

    # Uptime
    try:
        uptime_output, error = ssh.ssh_command(ip, 22, "admin", password, "uptime\n")
        print(f"[{ip}] Uptime Output:", uptime_output)

        lines = uptime_output.split("\r\n")
        for line in lines:
            if "The system has been running for" in line:
                parts = line.split(" ")
                if "days" in parts:
                    day_index = parts.index("days")
                    uptime_days = parts[day_index - 1]
                else:
                    uptime_days = "0"
                break
        else:
            uptime_days = "N/A"
    except Exception as e:
        print(f"[{ip}] Error getting uptime: {str(e)}")
        uptime_days = "N/A"

    # Save uptime to file
    # try:
    #     rundata_dir = "C:\\runData"
    #     os.makedirs(rundata_dir, exist_ok=True)
    #     cleaned_uptime = uptime_output.replace("\r\n", " ")
    #     with open(f"{rundata_dir}\\{ip}_uptime.txt", "w") as f:
    #         f.write(f"Control System IP : {ip} {cleaned_uptime}")
    # except Exception as e:
    #     print(f"[{ip}] Error writing uptime file: {str(e)}")

    # CSV Logging
    csv_file_path = 'C:\\runData\\event.csv'
    try:
        if not os.path.exists(csv_file_path):
            os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
            with open(csv_file_path, 'w', newline='') as f_object:
                writer_object = writer(f_object)
                column_headers = ['Timestamp', 'IP', 'Uptime (Days)', 'RAM Usage (%)', 'User CPU (%)',
                                  'System CPU (%)', 'Nice CPU (%)', 'Idle CPU (%)',
                                  'IO CPU (%)', 'IRQ CPU (%)', 'SIRQ CPU (%)']
                writer_object.writerow(column_headers)

        data_row = [datetime_string, ip, uptime_days, ramUsage, UserCPU, sysCPU, nicCPU,
                    idleCPU, ioCPU, irqCPU, sirqCPU]

        with open(csv_file_path, 'a', newline='') as f_object:
            writer_object = writer(f_object)
            writer_object.writerow(data_row)
    except Exception as e:
        print(f"[{ip}] Error writing to CSV file: {str(e)}")


# Main Execution
if __name__ == "__main__":
    ipINput = "10.253.80.50,10.253.80.238,10.253.73.84,10.253.80.118,10.253.73.82,10.253.73.83,10.253.80.49,10.253.73.81,10.253.81.2,10.253.81.27,10.253.80.77,10.253.80.66,10.253.81.30,10.253.73.56"
    password = 'admin123'
    poolInterval = 1

    print("IP passed as:", ipINput)
    print("Password passed as:", password)

    ips = ipINput.split(",")
    for ip in ips:
        try:
            print(f"Starting monitoring for {ip}")
            monitor_ip(ip, password)
            print(f"Successfully completed monitoring for {ip}")
        except Exception as e:
            print(f"Critical error monitoring {ip}: {str(e)}")
            print("Continuing with next IP...")
            continue