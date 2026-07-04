"""Gunicorn configuration for mercury.

Makes gunicorn's own logs (startup, worker lifecycle) JSON, consistent with
Django's mercury.logging_json.JsonFormatter. All output goes to stdout.

Worker recycling (max_requests) mitigates slow memory leaks; timeout respawns
workers that block on a slow Ollama call. Note: RAG generation can be slow
(ensemble mode calls several models), so the timeout is generous.
"""

errorlog = "-"
accesslog = "-"

max_requests = 1000
max_requests_jitter = 100

keepalive = 5

# RAG generation (esp. ensemble) can take a while; keep workers alive for it.
timeout = 180

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "mercury.logging_json.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
