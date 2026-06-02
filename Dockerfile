FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the package source
COPY setup.py .
COPY src/ src/

# Install the package (creates the `pt` console script)
RUN pip install --no-cache-dir -e .

EXPOSE 5001

# Run the Flask webhook server directly
CMD ["python", "-c", "from planka_tools.webhook.server import run_server; run_server()"]
