FROM python:3.10-slim
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libssl-dev libffi-dev tesseract-ocr poppler-utils ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV MONGODB_CONNECTION=mongodb://mongo:27017/mekongai_social
ENV SERVER_ADDRESS=http://localhost:1975
ENV FRONTEND_URL=http://localhost:3002
EXPOSE 1975
CMD ["python","app.py"]
