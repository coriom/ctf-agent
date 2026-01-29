FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    jq file binutils xxd unzip p7zip-full \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt /app/
COPY ctf_agent /app/ctf_agent

RUN python3 -m venv /venv \
 && /venv/bin/pip install -U pip \
 && /venv/bin/pip install -r /app/requirements.txt \
 && /venv/bin/pip install -e /app

ENV PATH="/venv/bin:${PATH}"
ENTRYPOINT ["ctf-agent"]
