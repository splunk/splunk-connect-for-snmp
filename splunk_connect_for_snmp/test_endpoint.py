import socket
from celery import Celery
from splunk_connect_for_snmp.snmp.tasks import test_trap

HOST = ""
PORT = 65432
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(5)
app = Celery("sc4snmp_traps")
app.config_from_object("splunk_connect_for_snmp.celery_config")
app.autodiscover_tasks(
    packages=[
        "splunk_connect_for_snmp",
        "splunk_connect_for_snmp.enrich",
        "splunk_connect_for_snmp.inventory",
        "splunk_connect_for_snmp.splunk",
        "splunk_connect_for_snmp.snmp",
    ]
)


def main():
    while True:
        conn, addr = s.accept()
        data = conn.recv(1024).decode('utf-8')
        print(f"Connected by {addr}. Received: {data}")
        work = {"host": data}
        test_trap.s(work).set(queue="traps").apply_async()
