FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastmcp httpx

COPY server.py /app/server.py

ENV PORT=8001

EXPOSE 8001

CMD ["python", "/app/server.py"]

