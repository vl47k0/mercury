# --- build stage: compile deps into a venv (toolchain discarded) ---
FROM python:3-alpine AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apk add --no-cache gcc g++ make musl-dev postgresql-dev
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /venv \
 && /venv/bin/pip install --no-cache-dir --upgrade pip \
 && /venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# --- runtime stage ---
FROM python:3-alpine AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"
RUN apk upgrade --no-cache && apk add --no-cache libpq libstdc++ bash
RUN addgroup -g 1001 beta && adduser -u 1001 -G beta -s /bin/sh -D beta
COPY --from=builder /venv /venv
RUN rm -rf /usr/local/lib/python3.*/site-packages/pip \
           /usr/local/lib/python3.*/site-packages/pip-*.dist-info
WORKDIR /app
COPY --chown=beta:beta . /app/
ARG VERSION=0.0.0
RUN echo "$VERSION" > /app/VERSION
RUN DJANGO_SECRET_KEY=build DJANGO_DEBUG=false python manage.py collectstatic --noinput \
 && chown -R beta:beta /app
USER beta
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz',timeout=3).status==200 else 1)" || exit 1

ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
CMD ["python", "-m", "gunicorn", "mercury.wsgi:application", "--config", "/app/mercury/gunicorn.conf.py", "--bind", "0.0.0.0:8000", "--workers", "3"]
