FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Listens on TCP. Override with HOST/PORT env vars if you like.
ENV HOST=0.0.0.0
ENV PORT=8888

EXPOSE 8888

CMD ["python", "server.py"]