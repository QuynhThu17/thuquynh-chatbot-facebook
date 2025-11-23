### Install library

```sh
sudo apt-get update && apt-get install -y \
    build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libsqlite3-dev ffmpeg libsm6 libxext6 libbz2-dev \
    libssl-dev libreadline-dev libffi-dev wget curl \
    python3-venv nano tesseract-ocr libtesseract-dev poppler-utils gfortran libopenblas-dev liblapack-dev && \
    rm -rf /var/lib/apt/lists/*
    
sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-eng

python3.10 -m venv venv
source venv/bin/activate  ## venv\Scripts\activate.bat
pip3.10 install -r requirements.txt --use-deprecated=legacy-resolver

pip install python-magic-bin

pip3.10 install 'uvicorn[standard]'
pip3.10 install --upgrade camelot-py[cv]

cp .env.examples .env

wget https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata
sudo mv -v vie.traineddata /usr/share/tesseract-ocr/4.00/tessdata/

ulimit -n 60240

pip3.10 install onnx==1.16.1 onnx7runtime==1.19.2
pip3.10 install PyPDF2==2.12.1
pip3.10 install unstructured unstructured-inference pytesseract unstructured_pytesseract

Remove-Item Env:SSL_CERT_FILE
```

---

### API

```bash
python3.10 app.py
```
