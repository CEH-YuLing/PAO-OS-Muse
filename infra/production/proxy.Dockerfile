FROM caddy:2
USER root
RUN setcap -r /usr/bin/caddy && mkdir -p /data/caddy /config/caddy && chown -R 1000:1000 /data /config
USER 1000:1000
