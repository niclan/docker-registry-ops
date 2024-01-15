# This is where we pull kubectl from
FROM bitnami/kubectl:1.21 as kubectl
# And this is the image we build from
FROM python:3.11-slim-bookworm
# Pull kubectl binary from the kubectl image
COPY --from=kubectl /opt/bitnami/kubectl/bin/kubectl /usr/local/bin/kubectl
RUN pip install --upgrade pip
RUN pip install kubernetes requests falcon
# Install our code
RUN mkdir -p /app
COPY images.json Registry.py Spinner.py k8s-inventory.py registry-checker.py /app/
ENV REPORTDIR=/app
ENV PYTHONUNBUFFERED=TRUE
WORKDIR /app
CMD ["python3", "./registry-check.py"]
