FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies first for better Docker layer caching.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files into the container.
COPY . .

# Start the safe hub loop by default.
CMD ["python", "-m", "src.hub.hub_loop"]