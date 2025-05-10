FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables with default values
ENV DB_USER="root" \
    DB_PASSWORD="" \
    DB_NAME="tunnel" \
    DB_HOST="127.0.0.1" \
    INSTANCE_CONNECTION_NAME="" \
    CLOUD_RUN="False" \
    EMAIL_HOST="smtp.gmail.com" \
    EMAIL_PORT="587" \
    EMAIL_USER="ramzi2.bouzidi2@gmail.com" \
    EMAIL_PASSWORD="" \
    EMAIL_FROM_NAME="Wind Tunnel App" \
    EMAIL_USE_TLS="True"

# Expose port for FastAPI application
EXPOSE 8080

# Command to run the application with Uvicorn on port 8080
CMD ["uvicorn", "Tunnel.main:app", "--host", "0.0.0.0", "--port", "8080"]