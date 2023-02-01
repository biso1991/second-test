# celery -A api worker --loglevel=info -E -P threads
# celery -A api worker --loglevel=info --autoscale=2,5 -E -P threads --max-memory-per-child=244141
# celery -A api worker --loglevel=info -c 5 -E


# RUn celery command in the terminal when django is running from python

# run command in terminal from python:


# celery -A api worker --loglevel=info --concurrency=3 --max-tasks-per-child=1 -E -P threads


# celery -A api worker --loglevel=info -E -P threads
