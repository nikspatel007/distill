FROM oven/bun:1 AS base
WORKDIR /app

# Install dependencies
COPY package.json bun.lock* ./
COPY packages/shared/package.json packages/shared/
COPY packages/server/package.json packages/server/
COPY packages/web/package.json packages/web/
RUN bun install

# Copy source
COPY packages/shared/ packages/shared/
COPY packages/server/ packages/server/
COPY packages/web/ packages/web/

# Build web frontend
RUN cd packages/web && bun run build

# Expose port
ENV PORT=6107
ENV NODE_ENV=production
EXPOSE 6107

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:6107/api/health || exit 1

# Start server
CMD ["bun", "run", "packages/server/src/index.ts"]
