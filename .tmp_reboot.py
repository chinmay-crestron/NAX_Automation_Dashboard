import sys
sys.path.insert(0, r"Longevity\backend")
import ssh
for ip in ("172.18.88.28", "172.18.88.20"):
    for cmd in ("help nvramreboot", "uptime", "ver -v"):
        out, err = ssh.ssh_command_BTIO(ip, 22, "admin", "admin123", cmd, 5)
        print("=" * 60, ip, cmd, err)
        print((out or "").replace("\r", "").replace("\n[Timeout reached]", "").strip())
