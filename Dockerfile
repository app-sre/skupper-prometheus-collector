FROM registry.access.redhat.com/ubi9/python-39
ARG POETRY_VERSION

RUN mkdir -p bin && \
    curl -sSL https://github.com/skupperproject/skupper/releases/download/1.2.1/skupper-cli-1.2.1-linux-amd64.tgz | tar -C /opt/app-root/src/bin -xzf -

RUN pip install --upgrade pip && \
    pip install poetry==$POETRY_VERSION
COPY --chown=1000 skupper_prometheus_collector skupper_prometheus_collector
COPY --chown=1000 README.md pyproject.toml poetry.* ./
RUN poetry install
USER 1000
CMD [".venv/bin/skupper-prometheus-collector"]
