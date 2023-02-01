import os
from django.conf import settings
from celery import Celery

# using importer to load the settings module
from configurations import importer

# set the default Django settings module for the 'celery' program to use Local Config.
os.environ.setdefault("DJANGO_CONFIGURATION", "Local")

# Setting the default Django settings env var to 'Local'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config")

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# install the settings module
importer.install()

# Initialize Celery app
app = Celery("api")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Apply the configurations
app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND
app.conf.task_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.result_serializer = "json"
app.conf.timezone = "Africa/Tunis"
app.conf.enable_utc = True
app.conf.disable_rate_limits = True


# import subprocess
# subprocess.Popen(['celery', 'worker', '--loglevel=info', '-c','8', '-E'])

# app.worker_main(argv = ['worker', '--loglevel=info', '-c','8','-E'])

# app.worker_main(argv = ['worker', '--loglevel=info', '-c','8','-E'])
# app.start(argv=sys.argv[1:])
