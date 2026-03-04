# Mobile Access (PWA)

Distill can be installed as a Progressive Web App on your phone for a native app-like experience.

## Prerequisites

- Distill dashboard running on your Mac
- [Tailscale](https://tailscale.com) installed on both Mac and phone (free for personal use)
- Both devices on the same Tailnet

## Step 1: Install Tailscale

=== "Mac"

    ```bash
    brew install tailscale
    # Or download from https://tailscale.com/download/mac
    tailscale up
    ```

=== "iPhone"

    Download [Tailscale from the App Store](https://apps.apple.com/app/tailscale/id1470499037) and sign in with the same account.

## Step 2: Find your Mac's Tailscale hostname

```bash
tailscale status
```

Look for your machine name — it'll be something like `your-macbook.tail12345.ts.net` or a `100.x.x.x` IP address.

## Step 3: Start the dashboard

```bash
uv run python -m distill serve --output ./insights
```

The server listens on port **6107** by default.

## Step 4: Open on your phone

On your iPhone, open Safari and navigate to:

```
http://your-macbook.tail12345.ts.net:6107
```

!!! tip "Use the Tailscale IP if hostname doesn't resolve"
    ```
    http://100.x.x.x:6107
    ```

## Step 5: Add to Home Screen

1. Tap the **Share** button in Safari (square with arrow)
2. Scroll down and tap **Add to Home Screen**
3. Name it "Distill" and tap **Add**

The app now launches in standalone mode (no Safari chrome) with the Distill icon.

## Optional: HTTPS with Tailscale certs

For a more secure setup:

```bash
# On your Mac
tailscale cert your-macbook.tail12345.ts.net

# Start with TLS
uv run python -m distill serve --output ./insights \
  --tls-cert your-macbook.tail12345.ts.net.crt \
  --tls-key your-macbook.tail12345.ts.net.key
```

Then access via `https://your-macbook.tail12345.ts.net:6117` on your phone.

## Offline support

The PWA includes a service worker that caches static assets. If your Mac is unreachable, you'll see a basic offline page. Content requires a live connection to the server.

## Troubleshooting

**Can't reach the server from phone?**

- Verify both devices show as connected in the Tailscale app
- Try pinging your Mac from the phone: open Safari, go to `http://100.x.x.x:6107`
- Make sure the Distill server is running (`lsof -i :6107`)

**PWA not updating?**

- Open the PWA, pull down to refresh
- If stale, clear the site data in Safari Settings > Advanced > Website Data
