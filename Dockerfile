FROM python:3-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk upgrade --no-cache && apk add --no-cache libpq libstdc++ bash

WORKDIR /app

COPY requirements.txt /app/
RUN apk add --no-cache --virtual .build-deps gcc g++ make musl-dev postgresql-dev \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps

FROM base AS runtime

RUN addgroup -g 1001 beta && adduser -u 1001 -G beta -s /bin/sh -D beta

COPY --chown=beta:beta . /app/

ARG VERSION=0.0.0
RUN echo "$VERSION" > /app/VERSION

RUN DJANGO_SECRET_KEY=build DJANGO_DEBUG=false python manage.py collectstatic --noinput \
 && chown -R beta:beta /app

USER beta
ENV PATH="/home/beta/.local/bin:${PATH}"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz',timeout=3).status==200 else 1)" || exit 1

ENTRYPOINT ["/app/deploy/docker-entrypoint.sh"]
CMD ["python", "-m", "gunicorn", "mercury.wsgi:application", "--config", "/app/mercury/gunicorn.conf.py", "--bind", "0.0.0.0:8000", "--workers", "3"]
