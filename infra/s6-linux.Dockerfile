FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-trixie
USER root
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 ca-certificates && apt-get clean
WORKDIR /workspace
COPY requirements.lock requirements-dev.lock ./
RUN python -m pip install --no-cache-dir -r requirements-dev.lock
COPY package.json package-lock.json ./
COPY web.package.json apps/web/package.json
RUN useradd --uid 10001 --create-home pao && chown -R 10001:10001 /workspace
USER 10001
ENV HOME=/home/pao PAO_ROOT=/workspace PYTHONPATH=/workspace/apps/api PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PAO_BUILD_CHECK=1
RUN npm ci
USER root
COPY source.zip /tmp/s6-source.zip
RUN python -c "import zipfile,pathlib,os; z=zipfile.ZipFile('/tmp/s6-source.zip'); assert all(not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts and (not pathlib.PurePosixPath(n).name.startswith('.env') or n=='.env.example') for n in z.namelist()); z.extractall('/workspace'); [os.chown('/workspace/'+n,10001,10001) for n in z.namelist()]; [os.chown(p,10001,10001) for p,d,f in os.walk('/workspace') if 'node_modules' not in pathlib.Path(p).parts]"
USER 10001
CMD ["python","scripts/s6_linux_entry.py"]
