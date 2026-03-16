# Gunicorn configuration file
# Usage: gunicorn -c gunicorn.conf.py server:app

bind = "0.0.0.0:5000"
workers = 2
timeout = 120
keepalive = 5
errorlog = "gunicorn_error.log"
accesslog = "gunicorn_access.log"
loglevel = "info"

# For development, you can also use:
# reload = True
