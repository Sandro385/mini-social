## Dockerfile for the Mini FB social network
#
# This image sets up a minimal environment for running the Flask
# application contained in mini_fb.py.  It installs dependencies
# from mini_fb_requirements.txt, copies the application code and
# starts it using Python.  The application listens on the port
# specified by the PORT environment variable (default 5000).

FROM python:3.11-slim

# Install dependencies.  Use a separate requirements file to avoid
# inadvertently pulling in dev tools used for other projects.  You
# can rename mini_fb_requirements.txt to requirements.txt if you
# prefer the conventional name.
WORKDIR /app
COPY mini_fb_requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY mini_fb.py .

# Expose the default port (5000) for local development.  Render or
# other hosting platforms will map their designated port to this.
EXPOSE 5000

# Set the entrypoint.  The port will be picked up from the PORT
# environment variable if provided.  Debug mode is controlled via
# FLASK_DEBUG (default on).
CMD ["python", "mini_fb.py"]