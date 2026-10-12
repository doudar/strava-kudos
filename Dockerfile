# Keep this version in sync with requirements.txt and the GitHub Actions image.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# The base image includes browsers and system dependencies, but not the Python package.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY give_kudos.py ./

USER pwuser

CMD ["python", "give_kudos.py"]
