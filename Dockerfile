FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ ./mcp_server/
COPY demo_data/ ./demo_data/
COPY topology.yaml ./topology.yaml

ENV TOPOLOGY_PATH=/app/demo_data/topology.yaml \
    LOGS_PATH=/app/demo_data/logs.jsonl \
    OS_PATH=/app/demo_data/os.json \
    DIAG_MCP_MODEL=claude-sonnet-5-5

EXPOSE 8000

CMD ["python", "-m", "mcp_server.server"]
