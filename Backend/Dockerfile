FROM python:3.11-slim

# System dependencies:
#   tesseract-ocr   — OCR binary needed by pytesseract
#   libglib2.0-0    — required by OpenCV (glib dependency)
#   libgomp1        — required by scikit-learn parallel jobs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# If model files were excluded from git, generate them now from the dataset.
# This runs only when models/solar_model.pkl is absent (i.e. gitignored build).
# matplotlib and seaborn are installed temporarily for plot generation then removed.
RUN if [ ! -f models/solar_model.pkl ]; then \
        echo "[docker-build] solar_model.pkl not found — training from dataset..." && \
        pip install --quiet matplotlib seaborn && \
        python train_model.py && \
        echo "[docker-build] Training complete." ; \
    else \
        echo "[docker-build] solar_model.pkl found — skipping training." ; \
    fi

EXPOSE 5000
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --timeout 120"]
