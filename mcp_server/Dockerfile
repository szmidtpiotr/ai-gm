FROM python:3.11-slim
WORKDIR /app
COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mcp_server/server.py .
ENV DB_PATH=/data/ai_gm.db
EXPOSE 8400
CMD ["python", "server.py"]
