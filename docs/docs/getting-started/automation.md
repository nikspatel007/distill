# Daily Automation

Run Distill automatically every morning so a fresh digest is waiting when you start your day.

## macOS (launchd)

Distill ships with a launchd plist that runs the full pipeline daily at 6:00 AM.

### Step 1: Edit the plist

Copy and customize the template:

```bash
cp support/com.distill.daily.plist ~/Library/LaunchAgents/
```

Open `~/Library/LaunchAgents/com.distill.daily.plist` and update these paths:

```xml
<!-- Update this to your distill project path -->
<string>/path/to/distill</string>

<!-- Update the uv --project path -->
<string>uv</string>
<string>run</string>
<string>--project</string>
<string>/path/to/distill</string>
```

!!! tip "Find your paths"
    ```bash
    # Your distill project path
    pwd  # run from the distill directory

    # Your uv path
    which uv
    ```

### Step 2: Set your API key

The launchd environment doesn't inherit your shell's `export` statements. Add your API key to the plist's `EnvironmentVariables` section, or use a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Step 3: Load the agent

```bash
launchctl load ~/Library/LaunchAgents/com.distill.daily.plist
```

### Step 4: Verify

Check if it's loaded:

```bash
launchctl list | grep distill
```

View logs:

```bash
tail -f ~/Library/Logs/distill-daily.log
```

Trigger a manual run to test:

```bash
launchctl start com.distill.daily
```

### Unload

```bash
launchctl unload ~/Library/LaunchAgents/com.distill.daily.plist
```

## Linux (cron)

```bash
crontab -e
```

Add:

```
0 6 * * * cd /path/to/distill && ANTHROPIC_API_KEY=sk-ant-... /path/to/uv run python -m distill run --output ./insights --use-defaults >> ~/distill.log 2>&1
```

## Linux (systemd timer)

Create `~/.config/systemd/user/distill.service`:

```ini
[Unit]
Description=Distill daily pipeline

[Service]
Type=oneshot
WorkingDirectory=/path/to/distill
Environment=ANTHROPIC_API_KEY=sk-ant-...
ExecStart=/path/to/uv run python -m distill run --output ./insights --use-defaults
```

Create `~/.config/systemd/user/distill.timer`:

```ini
[Unit]
Description=Run Distill daily at 6am

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:

```bash
systemctl --user enable --now distill.timer
```

## What `distill run` does

The `run` command orchestrates the full pipeline:

1. **Sessions** — Parses Claude Code / Codex CLI sessions
2. **Journal** — Generates a dev journal entry from sessions
3. **Intake** — Fetches RSS feeds, enriches articles, synthesizes digest
4. **Blog** — Generates weekly/thematic blog posts from journal entries

You can skip steps:

```bash
# Only intake (reading digest), skip sessions/journal/blog
uv run python -m distill run --output ./insights --use-defaults --skip-sessions --skip-blog
```

## Web dashboard + automation

If you also want the web dashboard running permanently, use a separate launchd agent or run it in a tmux session:

```bash
# In a tmux session
uv run python -m distill serve --output ./insights
```

The dashboard reads from `./insights/` — it picks up new digests automatically when the daily pipeline completes.
