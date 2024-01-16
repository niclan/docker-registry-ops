# This is where we pull kubectl from
FROM bitnami/kubectl:1.21 as kubectl
# And this is the image we build from
FROM python:3.11-slim-bookworm
# Pull kubectl binary from the kubectl image
RUN apt-get update && apt-get install -y cron
COPY --from=kubectl /opt/bitnami/kubectl/bin/kubectl /usr/local/bin/kubectl
# Python runtime environment
RUN pip install --upgrade pip
RUN pip install kubernetes requests
# Install our code
RUN mkdir -p /app/reports; mkdir -p /lib; mkdir -p /bin
COPY app /app
COPY lib /lib
COPY k8s-inventory.py registry-checker.py /bin/
ENV REPORTDIR=/app/reports
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONPATH=/lib
WORKDIR /app
USER www-data
CMD ["python3", "./webserver.py"]
