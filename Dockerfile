FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y libpq5 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir mcp httpx uvicorn starlette psycopg2-binary sse-starlette

# Copy source
COPY src/ ./src/
COPY pyproject.toml .

# Environment variables with defaults
ENV DB_HOST=db
ENV DB_PORT=5432
ENV DB_NAME=supermarkt_db
ENV DB_USER=postgres
ENV DB_PASSWORD=supermarkt123
ENV PORT=8000

EXPOSE 8000

CMD ["python", "src/server_sse.py"]
