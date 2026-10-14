# InvestPI Container for Google Cloud Run
FROM python:3.11-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install standard font & render packages for clean ReportLab PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Run with gunicorn WSGI server: 2 workers, 4 threads, timeout 120s for Gemini API calls
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 run:app
