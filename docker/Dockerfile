# multi-stage build for combined AudioBookRequest + Mamlarr runtime
ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y build-essential curl git && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip

FROM node:${NODE_VERSION}-bookworm AS ui-build
WORKDIR /tmp/ui
COPY static ./static
COPY templates ./templates
## install tailwind/daisy to build compiled css
RUN npm install tailwindcss@4.1.12 daisyui@5 && \
    npx tailwindcss -i static/tw.css -o static/globals.css

FROM base AS install
WORKDIR /srv
# install AudioBookRequest
COPY ../pyproject.toml ../uv.lock ./
RUN pip install uv && uv pip install --system .
# install Mamlarr as package
COPY ../mamlarr ./mamlarr
RUN cd mamlarr && pip install .

FROM base AS runtime
WORKDIR /srv/app
COPY --from=install /opt/venv /opt/venv
COPY --from=ui-build /tmp/ui/static/globals.css /srv/static/globals.css
ENV AUDIOBOOKREQUEST_PORT=8000 \
    MAMLARR_PORT=8800
COPY docker/start.sh /start.sh
EXPOSE 8000 8800
ENTRYPOINT ["/start.sh"]
