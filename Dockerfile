FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir aiohttp
COPY ntfy_to_sip.py /app/ntfy_to_sip.py
RUN useradd -u 10001 appuser
USER appuser
CMD ["python", "-u", "/app/ntfy_to_sip.py"]
