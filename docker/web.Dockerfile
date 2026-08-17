# The web app, for local development only.
#
# `node_modules` and `.next` are kept inside the image and masked from the bind
# mount by anonymous volumes in compose: Next builds platform-specific binaries
# (SWC, sharp), and letting a Windows or macOS host's `node_modules` show
# through would break them.
FROM node:22-slim

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm ci

COPY apps/web ./

EXPOSE 3000
CMD ["npm", "run", "dev"]
