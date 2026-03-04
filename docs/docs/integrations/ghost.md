# Ghost CMS

Publish intake digests and blog posts directly to a Ghost blog.

## Setup

1. In your Ghost admin panel, go to **Settings** > **Integrations** > **Add custom integration**
2. Name it "Distill" and copy the **Admin API Key** (format: `id:secret`)
3. Note your Ghost URL (e.g., `https://your-blog.ghost.io`)

## Configuration

=== ".distill.toml"

    ```toml
    [ghost]
    url = "https://your-blog.ghost.io"
    admin_api_key = "abc123:def456..."
    newsletter_slug = "your-newsletter"  # optional: auto-send to subscribers
    auto_publish = true
    blog_as_draft = false
    ```

=== "Environment variables"

    ```bash
    export GHOST_URL=https://your-blog.ghost.io
    export GHOST_ADMIN_API_KEY=abc123:def456...
    export GHOST_NEWSLETTER_SLUG=your-newsletter
    ```

## Usage

### Publish intake digest to Ghost

```bash
uv run python -m distill intake --output ./insights --publish ghost
```

### Publish blog posts to Ghost

```bash
uv run python -m distill blog --output ./insights --publish ghost
```

### Multiple Ghost sites

Name your targets in the config:

```toml
[ghost]
default = "personal"

[ghost.personal]
url = "https://personal-blog.ghost.io"
admin_api_key = "abc:123..."

[ghost.work]
url = "https://work-blog.ghost.io"
admin_api_key = "def:456..."
```

Use a specific target:

```bash
uv run python -m distill blog --output ./insights --publish ghost --target work
```

## What gets published

- Blog posts are created as Ghost posts with proper HTML formatting
- Tags from the digest/post are mapped to Ghost tags
- Newsletter sending is triggered automatically if `newsletter_slug` is set
- Duplicate detection: Ghost integration checks for existing posts by slug
