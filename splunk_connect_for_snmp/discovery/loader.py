import subprocess
import sys
# Just to check the deployement, no use as of now
import nmap

from celery.utils.log import get_task_logger


logger = get_task_logger(__name__)


def check_nmap_installed():
    try:
        result = subprocess.run(["nmap", "--version"], capture_output=True, text=True, check=True)
        print("Nmap is installed.")
        print(result.stdout)
    except FileNotFoundError:
        print("Nmap is not installed.")
    except subprocess.CalledProcessError as e:
        print("Error running nmap:", e)

def scan_ip(ip_address):
    try:
        print(f"\nScanning IP: {ip_address}")
        result = subprocess.run(["nmap", ip_address], capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Nmap scan failed:", e)

def load():
    check_nmap_installed()
    scan_ip("1.1.1.1")

if __name__ == "__main__":
    r = load()
    if r:
        sys.exit(0)
