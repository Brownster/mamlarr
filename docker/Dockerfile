ARG PYTHON_VERSION=3.12
ARG NODE_VERSION=20
ARG ABR_REPO=https://github.com/Brownster/audiobookrequest.git
ARG ABR_REF=main

FROM alpine/git AS abr-src
ARG ABR_REPO
ARG ABR_REF
RUN git clone --branch ${ABR_REF} --depth=1 ${ABR_REPO} /src/audiobookrequest

FROM node:${NODE_VERSION}-bookworm AS ui-build
WORKDIR /workspace
COPY --from=abr-src /src/audiobookrequest/static ./static
RUN npm init -y && \
    npm install --no-audit --no-fund tailwindcss@4.1.12 daisyui@5 && \
    npx tailwindcss tailwindcss -i ./static/tw.css -o ./static/globals.css

FROM python:${PYTHON_VERSION}-slim AS python-build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip uv
COPY --from=abr-src /src/audiobookrequest /srv/audiobookrequest
COPY . /srv/mamlarr
RUN uv pip install --system /srv/audiobookrequest && \
    uv pip install --system /srv/mamlarr

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUDIOBOOKREQUEST_PORT=8000 \
    MAMLARR_PORT=8800
WORKDIR /srv
COPY --from=python-build /usr/local /usr/local
COPY --from=abr-src /src/audiobookrequest /srv/audiobookrequest
COPY . /srv/mamlarr
COPY --from=ui-build /workspace/static/globals.css /srv/audiobookrequest/static/globals.css
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 8000 8800
ENTRYPOINT ["/start.sh"]
