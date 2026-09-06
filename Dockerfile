FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir '.[ingest,mcp]'
COPY config.example.yaml ./config.example.yaml
ENV PYTHONUNBUFFERED=1 RAN2WIKI_CONFIG=/config/config.yaml
CMD ["python", "-m", "ran2wiki.mcp.server"]

