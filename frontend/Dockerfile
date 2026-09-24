FROM node:22-bookworm-slim AS build

WORKDIR /app

RUN npm install --global npm@10.9.2

COPY package.json package-lock.json ./
RUN npm ci

COPY angular.json tsconfig*.json ./
COPY src/ ./src/
COPY public/ ./public/

RUN npm run build -- --configuration production


FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist/frontend/browser/ /srv/