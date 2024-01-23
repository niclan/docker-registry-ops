# This is where we pull kubectl from
FROM bitnami/kubectl:1.21 as kubectl
# And this is the image we build from
FROM python:3.11-slim-bookworm
# Pull kubectl binary from the kubectl image
COPY --from=kubectl /opt/bitnami/kubectl/bin/kubectl /usr/local/bin/kubectl
# Python runtime environment
RUN pip install --upgrade pip
RUN pip install kubernetes requests sched
# Install our code
RUN mkdir -p /app/reports; mkdir -p /lib; mkdir -p /bin
RUN chown -R www-data:www-data /app
# USER www-data
COPY app /app
COPY Spinner.py Registry.py /lib/
COPY container-start.sh k8s-inventory.py registry-checker.py cron.py /bin/
ENV REPORTDIR=/app/reports
ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONPATH=/lib
WORKDIR /app
CMD ["/bin/container-start.sh"]
