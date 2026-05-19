FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project into /app/mnacp/ so "import mnacp.xxx" works
COPY . /app/mnacp/

ENV PYTHONPATH=/app

EXPOSE 9000

CMD ["python", "mnacp/docker/agent_entrypoint.py"]
