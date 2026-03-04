# Postiz (Social Media)

[Postiz](https://postiz.com) is a self-hosted social media scheduler. Distill pushes content to Postiz as drafts, which you can review and publish from the Postiz UI.

## Setup

1. Deploy Postiz via Docker (see [Postiz docs](https://docs.postiz.com))
2. Get your API key from the Postiz settings

## Configuration

```toml
[postiz]
url = "https://your-postiz-instance.com"
api_key = "your-api-key"
default_type = "draft"          # draft | schedule | now
```

Or via environment variables:

```bash
export POSTIZ_URL=https://your-postiz-instance.com
export POSTIZ_API_KEY=your-api-key
```

## Usage

```bash
# Push blog posts as Postiz drafts
uv run python -m distill blog --output ./insights --publish postiz

# Push intake digest
uv run python -m distill intake --output ./insights --publish postiz
```

## Scheduling

Postiz can auto-schedule posts:

```toml
[postiz]
schedule_enabled = true
timezone = "America/New_York"
weekly_time = "09:00"
weekly_day = 0                  # Monday
daily_social_enabled = true
daily_social_time = "08:00"
daily_social_platforms = ["linkedin", "twitter"]
```

## Supported platforms

Postiz supports 20+ platforms including Twitter/X, LinkedIn, Reddit, Bluesky, Mastodon, Instagram, Facebook, and more. Connect platforms in the Postiz admin UI.
