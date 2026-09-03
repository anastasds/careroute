FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure adk[eval] is installed
RUN pip install --no-cache-dir "google-adk[eval]" google-cloud-storage

# Copy source
COPY . .

# Set entrypoint
CMD ["./scripts/run_eval.sh"]
