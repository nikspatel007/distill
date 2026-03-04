# Sharing from Phone

Share articles from any app on your phone directly into your next intake digest. The flow:

**Copy URL** → **Run Shortcut (Back Tap)** → **Distill saves it** → **Next intake digest includes it**

## How it works

1. You copy a URL on your phone (from X, Safari, LinkedIn, etc.)
2. An iOS Shortcut reads your clipboard and sends it to the Distill API
3. The URL is saved to `.distill-shares.json` in your output directory
4. When the next intake pipeline runs, it fetches the full article text and includes it with priority in the digest
5. You can read the extracted content in the Shares page of the dashboard

## Prerequisites

- Distill dashboard running on your Mac
- Tailscale connecting your phone and Mac (see [PWA setup](pwa.md))
- Your server's Tailscale address (e.g., `100.x.x.x` or `your-mac.ts.net`)

## Step 1: Find your sharing URL

Your sharing endpoint is:

```
http://<your-tailscale-address>:6107/api/shares?url=
```

For example: `http://100.64.0.1:6107/api/shares?url=`

!!! tip "Store this in your config"
    Add your hostname to `.distill.toml` so the Settings page shows the correct URL:

    ```toml
    [server]
    hostname = "100.64.0.1"
    ```

## Step 2: Create the iOS Shortcut

1. Open the **Shortcuts** app on your iPhone
2. Tap **+** to create a new shortcut
3. Add these actions in order:

### Action 1: Get Clipboard

- Search for **"Get Clipboard"** and add it

### Action 2: Get Contents of URL

- Search for **"Get Contents of URL"**
- Set the URL to:

```
http://<your-tailscale-address>:6107/api/shares?url=
```

- Tap on the URL field and **append** the Clipboard variable after `?url=`
- The final URL should look like: `http://100.64.0.1:6107/api/shares?url=[Clipboard]`

### Action 3: Show Notification

- Search for **"Show Notification"**
- Set the message to: `Saved to Distill`

4. Name the shortcut **"Send to Distill"**
5. Tap **Done**

## Step 3: Set up Back Tap (optional, recommended)

Instead of opening the Shortcuts app each time, trigger it with a double-tap on the back of your phone:

1. Go to **Settings** > **Accessibility** > **Touch** > **Back Tap**
2. Choose **Double Tap** or **Triple Tap**
3. Scroll down to **Shortcuts** and select **"Send to Distill"**

Now the workflow is:

1. See an interesting article in any app
2. **Copy the URL** (long-press the link, tap Copy)
3. **Double-tap the back of your phone**
4. See the "Saved to Distill" notification

## What happens to shared URLs

### During intake pipeline

When `distill intake` or `distill run` executes:

1. Shared URLs are loaded from `.distill-shares.json`
2. Full article text is extracted (using trafilatura for web articles, FixTweet API for X/Twitter posts)
3. Content is auto-tagged and classified
4. **Shared links get priority** — they're always covered in the digest, before feed items
5. Extracted content (title, author, full text) is saved back to the share record
6. Shares are marked as "used" after being included in a digest

### In the dashboard

The **Shares** page (`/shares`) shows:

- **Pending shares** — waiting for the next intake run
- **Processed shares** — already included in a digest, with extracted content

Click any card to open the full article reader with formatted markdown content.

## X/Twitter support

Sharing X/Twitter links works automatically. Distill uses the FixTweet API to extract:

- Tweet text
- X Articles (long-form posts)
- Linked article content (resolves t.co redirects and fetches the real article)

No Twitter API key needed.

## CLI alternative

You can also share URLs from your terminal:

```bash
uv run python -m distill share "https://example.com/article" --note "great read"
```

List pending shares:

```bash
uv run python -m distill shares
```

## API reference

The shares API accepts both GET (for iOS Shortcuts) and POST (for programmatic use):

```bash
# Save a URL (GET — for iOS Shortcuts)
curl "http://localhost:6107/api/shares?url=https://example.com/article"

# Save a URL (POST — with note)
curl -X POST http://localhost:6107/api/shares \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "note": "check this out"}'

# List all shares
curl http://localhost:6107/api/shares

# Delete a share
curl -X DELETE http://localhost:6107/api/shares/<id>
```

## Troubleshooting

**Shortcut says "Could not connect to server"**

- Make sure Tailscale is connected on both devices
- Verify the server is running: `curl http://<tailscale-ip>:6107/api/shares`
- Try using the numeric IP instead of hostname

**URL not appearing in dashboard?**

- Open `http://<your-address>:6107/shares` and check if it's listed
- The shortcut uses the clipboard — make sure you copied the URL before running it

**Content shows "not fetched"?**

- Content is extracted during the intake pipeline run, not at share time
- Run `uv run python -m distill intake --output ./insights` to trigger enrichment
- Some sites block scraping — the article text may not be extractable
