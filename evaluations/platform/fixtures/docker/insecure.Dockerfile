# INTENTIONALLY UNSAFE. Evaluation only; never build for deployment.
FROM ubuntu:latest
USER root
COPY . /app
WORKDIR /app
CMD ["sh", "-c", "echo demo"]
