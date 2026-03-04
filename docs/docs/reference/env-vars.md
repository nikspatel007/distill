# Environment Variables

All environment variables Distill reads. Only `ANTHROPIC_API_KEY` is required.

## Required

| Variable | Description |
|----------|------------|
| `ANTHROPIC_API_KEY` | Claude API key for LLM synthesis |

## LLM

| Variable | Default | Description |
|----------|---------|------------|
| `DISTILL_MODEL` | `claude-sonnet-4-6` | Override model for all pipelines |
| `DISTILL_USE_CLI` | | Set to `1` to force `claude -p` subprocess |

## Output

| Variable | Default | Description |
|----------|---------|------------|
| `DISTILL_OUTPUT_DIR` | `./insights` | Override output directory |

## Ghost CMS

| Variable | Description |
|----------|------------|
| `GHOST_URL` | Ghost instance URL |
| `GHOST_ADMIN_API_KEY` | Admin API key (`id:secret` format) |
| `GHOST_NEWSLETTER_SLUG` | Newsletter for auto-send |

For named targets (e.g., `personal`, `work`):

| Variable | Description |
|----------|------------|
| `GHOST_PERSONAL_URL` | Named target URL |
| `GHOST_PERSONAL_ADMIN_API_KEY` | Named target key |

## Postiz

| Variable | Default | Description |
|----------|---------|------------|
| `POSTIZ_URL` | | Postiz instance URL |
| `POSTIZ_API_KEY` | | API key |
| `POSTIZ_DEFAULT_TYPE` | `draft` | `draft`, `schedule`, or `now` |
| `POSTIZ_SCHEDULE_ENABLED` | `false` | Enable scheduling |
| `POSTIZ_TIMEZONE` | `America/Chicago` | Scheduling timezone |

## Reddit

| Variable | Description |
|----------|------------|
| `REDDIT_CLIENT_ID` | Reddit OAuth app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit OAuth app client secret |
| `REDDIT_USERNAME` | Reddit username |
| `REDDIT_PASSWORD` | Reddit password |

## YouTube

| Variable | Description |
|----------|------------|
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |

## Image generation

| Variable | Description |
|----------|------------|
| `GOOGLE_AI_API_KEY` | Google Gemini API key |

## Notifications

| Variable | Description |
|----------|------------|
| `DISTILL_SLACK_WEBHOOK` | Slack incoming webhook URL |
| `DISTILL_NTFY_URL` | ntfy.sh base URL |
| `DISTILL_NTFY_TOPIC` | ntfy topic (default: `distill`) |

## TLS / Server

| Variable | Default | Description |
|----------|---------|------------|
| `TLS_CERT` | | Path to TLS certificate |
| `TLS_KEY` | | Path to TLS private key |
| `TLS_PORT` | `6117` | HTTPS port |
