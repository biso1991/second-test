import json
from time import sleep

# import GPUtil
import psutil
import threading
from django.conf import settings

from api.qa.task_service import Send_Metrics
from django.core import serializers

# Class to handle monitoring metrics
class Monitor(threading.Thread):
    pid = None

    def __init__(self, pid, training_job, project_uuid, training_job_monitoring):
        threading.Thread.__init__(self)
        self.pid = pid
        self.project_uuid = project_uuid
        self.cpu_utilization = 0.0
        self.memory_utilization = 0.0
        self.memory_utilization_size = 0.0
        self.disk_utilization = ""
        self.training_job_monitoring = training_job_monitoring

    # Start function to handle monitoring to start monitoring
    def run(self):
        self.running = True
        currentProcess = psutil.Process(self.pid)
        nbCores = psutil.cpu_count()

        while self.running != False:
            cpu_percent = currentProcess.cpu_percent(interval=None) / nbCores
            path = "{}{}/".format(settings.MEDIA_URL, self.project_uuid).strip("/")
            iocounter = psutil.disk_usage(path)
            memorypercent = currentProcess.memory_percent()
            memoryutilization = currentProcess.memory_info().rss / 1024 / 1024 / 1024
            # try:
            self.training_job_monitoring.cpu_utilization = cpu_percent
            self.training_job_monitoring.memory_utilization = memorypercent
            self.training_job_monitoring.memory_utilization_size = memoryutilization
            self.training_job_monitoring.disk_utilization = json.dumps(iocounter)
            Send_Metrics(serializers.serialize("json", [self.training_job_monitoring]))
            if cpu_percent > self.cpu_utilization:
                self.cpu_utilization = cpu_percent
            self.disk_utilization = iocounter
            if memorypercent > self.memory_utilization:
                self.memory_utilization = memorypercent
            if memoryutilization > self.memory_utilization_size:
                self.memory_utilization_size = memoryutilization
            # print("GPU usage %: " + str(GPUtil.getGPUs()[0].load * 100) + '%')
            # print("GPU memory usage %: " +
            #       str(GPUtil.getGPUs()[0].memoryUtil * 100) + '%')
            # print("GPU memory total GB: " +
            #       str(GPUtil.getGPUs()[0].memoryTotal / 1024))
            # print(json.dumps(GPUtil.getGPUs()[0].__dict__,default=vars))
            sleep(3)

    # Function to stop monitoring

    def stop(self):
        sleep(5)
        Send_Metrics([{"status": "stopped"}])
        self.running = False
        return {
            "cpu_utilization": self.cpu_utilization,
            "memory_utilization": self.memory_utilization,
            "memory_utilization_size": self.memory_utilization_size,
            "disk_utilization": self.disk_utilization,
        }

    # Function update monitoring

    def update(self, training_monitoring):
        self.training_job_monitoring.f1_score = training_monitoring.f1_score
        self.training_job_monitoring.sas = training_monitoring.sas
        self.training_job_monitoring.validation_accuracy = (
            training_monitoring.validation_accuracy
        )
        self.training_job_monitoring.training_accuracy = (
            training_monitoring.training_accuracy
        )
        self.training_job_monitoring.precision = training_monitoring.precision
        self.training_job_monitoring.recall = training_monitoring.recall
        self.training_job_monitoring.loop_count = training_monitoring.loop_count
