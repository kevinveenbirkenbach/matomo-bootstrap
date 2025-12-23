# Playwright Python image with Chromium + all required OS dependencies
# Version should roughly match your playwright requirement
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# Keep stdout clean (token-only), logs go to stderr
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install matomo-bootstrap
# Option A: from PyPI (recommended once published)
# RUN pip install --no-cache-dir matomo-bootstrap==1.0.1

# Option B: build from source (current repo)
COPY pyproject.toml README.md LICENSE /app/
COPY constraints.txt /app/
COPY src /app/src
RUN pip install --no-cache-dir -c /app/constraints.txt .

# Default entrypoint: environment-driven bootstrap
ENTRYPOINT ["matomo-bootstrap"]
