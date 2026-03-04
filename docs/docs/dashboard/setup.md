# Web Dashboard

Distill includes a web dashboard for browsing digests, managing shared links, and reading extracted articles.

## Prerequisites

The dashboard requires [Bun](https://bun.sh) (JavaScript runtime):

```bash
curl -fsSL https://bun.sh/install | bash
```

## Starting the dashboard

```bash
uv run python -m distill serve --output ./insights
```

This:

1. Installs JS dependencies (`bun install`) if needed
2. Builds the frontend (`bun run build`) if needed
3. Starts the API server on [http://localhost:6107](http://localhost:6107)

!!! info "First start takes ~30 seconds"
    Subsequent starts are instant since the build is cached.

## What you get

| Page | What it shows |
|------|--------------|
| **Home** | Pipeline status, recent activity, quick stats |
| **Reading** | Daily intake digests with full markdown rendering |
| **Shares** | URLs shared from your phone — click to read extracted content |
| **Studio** | Blog post editor with AI chat and multi-platform publishing |
| **Settings** | Configuration, source management, sharing setup |

## Port

The default port is **6107**. Override with:

```bash
uv run python -m distill serve --output ./insights --port 8080
```

## HTTPS / TLS

For Tailscale or remote access, enable HTTPS:

```bash
# Generate certs with Tailscale
tailscale cert your-machine.ts.net

# Start with TLS
uv run python -m distill serve --output ./insights \
  --tls-cert your-machine.ts.net.crt \
  --tls-key your-machine.ts.net.key
```

This binds HTTPS on port **6117** alongside HTTP on 6107.

## Development mode

For frontend development with hot reload:

```bash
# Terminal 1: API server
uv run python -m distill serve --output ./insights --dev

# Terminal 2: Vite dev server (HMR)
cd web && bun run dev
```

The Vite dev server on port 6108 proxies API requests to 6107.
