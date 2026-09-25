# Manual deployment preparation

`compose.prod.yaml` runs the built application locally, with web on
127.0.0.1:8080 and API on 127.0.0.1:8000. For the public server, additionally
load `compose.server.yaml` (Docker Compose 2.24.4 or newer). It removes the API
host port, replaces web ports with TCP 80/443, enables secure refresh cookies,
and sets the public frontend URL. PostgreSQL has no published port.

The server's untracked `.env.production` must contain DATABASE_URL,
POSTGRES_PASSWORD, JWT_SECRET_KEY and a bare hostname:

```dotenv
SITE_ADDRESS=neu.ttclangenbrombach.de
```

Do not include a URL scheme or path in SITE_ADDRESS. Caddy uses this hostname
for automatic HTTPS; DNS must point to the server and TCP 80/443 must be
reachable. The caddy_data volume preserves certificates and private keys;
caddy_config preserves Caddy runtime configuration. These volumes are not backups.

Validate without printing secrets (from the project root):

```sh
sudo docker compose --env-file .env.production -f compose.prod.yaml -f compose.server.yaml config --quiet
```

Always include both files, in that order, for server operations. Existing
images must be rebuilt after Dockerfile, application or Caddyfile changes.
Migrations must run before starting the API. Initial server deployment,
administrator setup, data transfer, SMTP, worker operation and backup/restore
verification remain pending; configuration validation alone is not a deployment.
