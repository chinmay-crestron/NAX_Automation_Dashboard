import paramiko
import os

def ssh_command(hostname, port, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=hostname, port=port, username=username, password=password)
        _, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        return output, error
    except Exception as e:
        return None, str(e)
    finally:
        client.close()

def ssh_command_BTIO(hostname, port, username, password, command, timeout=10):
    import paramiko
    import time

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=hostname, port=port, username=username, password=password, timeout=timeout)
        shell = client.invoke_shell()
        shell.settimeout(timeout)

        # Clear initial prompt
        time.sleep(1)
        if shell.recv_ready():
            shell.recv(1000)

        shell.send(command + "\n")
        time.sleep(2)  # Wait for command to execute

        output = ""
        start_time = time.time()
        while True:
            if shell.recv_ready():
                output += shell.recv(4096).decode()
            if time.time() - start_time > timeout:
                output += "\n[Timeout reached]"
                break

        return output, ""
    except Exception as e:
        return None, str(e)
    finally:
        client.close()