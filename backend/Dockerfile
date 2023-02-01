FROM python:3.8
ENV PYTHONUNBUFFERED 1

# Allows docker to cache installed dependencies between builds
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt 

# Install PDF converter
RUN wget --no-check-certificate https://dl.xpdfreader.com/xpdf-tools-linux-4.04.tar.gz && \
    tar -xvf xpdf-tools-linux-4.04.tar.gz && cp xpdf-tools-linux-4.04/bin64/pdftotext /usr/local/bin
    
# install en_core_web_sm for spacy
RUN python3 -m spacy download en_core_web_sm

# install unrar bin for extracting rar files
RUN wget --no-check-certificate https://www.rarlab.com/rar/rarlinux-x64-612.tar.gz  && \
    tar -xvf rarlinux-x64-612.tar.gz  &&  \
    cp -r ./rar/ /usr/local/bin
# Adds our application code to the image
COPY . code
WORKDIR code

EXPOSE 8000

# Run the production server
CMD newrelic-admin run-program gunicorn --bind 0.0.0.0:$PORT --access-logfile - api.wsgi:application
