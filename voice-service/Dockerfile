FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    ca-certificates \
    libsndfile1 \
    libespeak-ng1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
    -O /tmp/piper.tar.gz \
    && tar -xzf /tmp/piper.tar.gz -C /tmp \
    && mkdir -p /opt/piper \
    && cp -r /tmp/piper/* /opt/piper/ \
    && chmod +x /opt/piper/piper \
    && ln -sf /opt/piper/piper /usr/local/bin/piper \
    && rm -rf /tmp/piper*

ENV LD_LIBRARY_PATH="/opt/piper"

COPY requirements.txt .
RUN pip install --no-cache-dir faster-whisper==1.0.3 fastapi==0.115.0 \
    uvicorn[standard]==0.30.6 python-multipart==0.0.9 \
    websockets==12.0 numpy==1.26.4 soundfile==0.12.1 requests==2.32.5

RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='/app/models/stt')"

RUN mkdir -p /app/models/tts && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx \
        -O /app/models/tts/pl_PL-darkman-medium.onnx && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx.json \
        -O /app/models/tts/pl_PL-darkman-medium.onnx.json && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx \
        -O /app/models/tts/pl_PL-gosia-medium.onnx && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx.json \
        -O /app/models/tts/pl_PL-gosia-medium.onnx.json && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/bass/high/pl_PL-bass-high.onnx \
        -O /app/models/tts/pl_PL-bass-high.onnx && \
    wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/pl/pl_PL/bass/high/pl_PL-bass-high.onnx.json \
        -O /app/models/tts/pl_PL-bass-high.onnx.json

COPY . .

EXPOSE 8300

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300", "--workers", "1"]
