# Caddy with the built web app: HTTPS for the site, the app's files, and /api, /admin,
# /static and /privacy/ passed to Django (deploy/Caddyfile). Build context: frontend/.
FROM node:20-alpine AS build
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# No VITE_API_BASE_URL: the browser calls the API on its own origin.
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /frontend/dist /srv
