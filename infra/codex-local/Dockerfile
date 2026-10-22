# Dedicated offline Codex candidate. No PAO backend, secrets or host mounts.
FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
LABEL pao.cli.version="0.157.1" pao.cli.binary-sha256="3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970"
COPY --chmod=0555 codex /usr/local/bin/codex
COPY package.json README.md /opt/codex/
COPY pao_cli_runtime /opt/pao_cli_runtime
COPY fixture.py /opt/fixture.py
ENV HOME=/tmp/home CODEX_HOME=/tmp/home/.codex PYTHONPATH=/opt PYTHONDONTWRITEBYTECODE=1
WORKDIR /tmp
USER 65534:65534
ENTRYPOINT ["python", "-B", "/opt/fixture.py"]
