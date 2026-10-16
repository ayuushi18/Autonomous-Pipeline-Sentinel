FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest/ ingest/
COPY benchmark/ benchmark/
COPY dashboard/ dashboard/
COPY .streamlit/ .streamlit/

EXPOSE 8501

CMD streamlit run dashboard/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true