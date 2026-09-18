FROM node:22-alpine AS builder
WORKDIR /app
RUN mkdir -p .next/standalone .next/static && echo ok > .next/standalone/server.js
FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
