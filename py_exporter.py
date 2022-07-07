import time
import subprocess
from prometheus_client import start_http_server, Enum
import requests
import argparse
import mmap

parser = argparse.ArgumentParser(description='Check if text is in file, then send to Prometheus if the execution was successful.')
parser.add_argument('-f', '--file', help='file to check', required=True)
parser.add_argument('-e', '--environment', help='Environment to add as a label on prometheus', choices=['beta', 'DEV', 'staging', 'prodp3'],  required=True)
parser.add_argument('-t', '--type', help='If the instance is "celery|api"', choices=['celery', 'api'], required=True)
parser.add_argument('-s', '--service', help='Service name to monitor', choices=['celery-worker-leonardo', 'leonardo_django'], required=True)
args = parser.parse_args()



class GeneralMetric:
    """
    Representation of Prometheus metrics and loop to fetch and transform
    application metrics into Prometheus metrics.
    """

    def __init__(self):
        """
        Initialize labels for metrics
        """
        self.pub_ip = requests.get('https://icanhazip.com').text.rstrip('\n')
        self.instance_id = requests.get('http://169.254.169.254/latest/meta-data/instance-id').text
        self.file = args.file
        self.env = args.environment
        self.instance_type = args.type
        self.service_name = args.service



class ProvisionerExecutionStatus(GeneralMetric):
    """
    Gather if provisioner went ok or not
    """

    def __init__(self):
        self.provisioner_executor_health = Enum("provisioner_health", "Find out if a local provision on auto-scaled instances fails", states=["healthy", "unhealthy"], labelnames=["instance_id", "pub_ip", "env", "type"])
        super().__init__()

    def remove_line(self, file):
        with open(file, "r") as f:
            lines = f.readlines()
        with open(file, "w") as f:
            for line in lines:
                if line.strip("\n") != "FAILED SELF-PROVISIONING":
                    f.write(line)

    def fetch(self):
        """
        Get line from file and expose to prometheus
        """

        with open(self.file, 'rb', 0) as file_mmap, \
            mmap.mmap(file_mmap.fileno(), 0, access=mmap.ACCESS_READ) as s:
            if s.find(b"FAILED SELF-PROVISIONING") != -1:
                print("Found string in file " + self.file + ": FAILED SELF-PROVISIONING")
                self.provisioner_executor_health.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("unhealthy")
                print("Removing line in file: " + self.file)
                self.remove_line(self.file)
            else:
                print("No string in file " + self.file)
                self.provisioner_executor_health.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("healthy")


class ProcStatus(GeneralMetric):
    """
    Check if celery or api are running
    """
    def __init__(self):
        super().__init__()
        if self.instance_type == "celery":
            self.proc_status_celery = Enum("proc_status_celery", "Find process status on Celery", states=["healthy", "unhealthy"], labelnames=["instance_id", "pub_ip", "env", "type"])
        else:
            self.proc_status_api = Enum("proc_status_api", "Find process status on API", states=["healthy", "unhealthy"], labelnames=["instance_id", "pub_ip", "env", "type"])

    def fetch(self, proc_name):
        """
        Find out if celery or api are running
        """

        proc_status = subprocess.call(["systemctl", "is-active", "--quiet", proc_name])
        if proc_status == 0:
            print("Service {} is running".format(proc_name))
            if self.instance_type == "celery":
                self.proc_status_celery.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("healthy")
            else:
                self.proc_status_api.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("healthy")
        else:
            print("Service {} is down".format(proc_name))
            if self.instance_type == "celery":
                self.proc_status_celery.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("unhealthy")
            else:
                self.proc_status_api.labels(self.instance_id, self.pub_ip, self.env, self.instance_type).state("unhealthy")

class MetricManager:
    def __init__(self):
        self.provisioner_executor_health = ProvisionerExecutionStatus()
        self.proc_status = ProcStatus()

    def run_metrics_loop(self):
        """Metrics fetching loop"""
        while True:
            self.proc_status.fetch(self.proc_status.service_name)
            self.provisioner_executor_health.fetch()
            time.sleep(30)


def main():
    """Main entry point"""
    exporter_port = 9877

    metric_manager = MetricManager()
    start_http_server(exporter_port)
    metric_manager.run_metrics_loop()

if __name__ == "__main__":
    main()
