# Distill Product — Setup Guide

## Prerequisites

- [Bun](https://bun.sh) v1.1+
- [Supabase account](https://supabase.com) (free tier works)
- Anthropic API key (for AI-powered highlights and drafts)
- Google AI API key (optional, for Gemini image generation)

## 1. Supabase Project Setup

### Create Project

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Click **New Project**
3. Choose a name (e.g., "distill"), set a database password, select a region
4. Wait for project to initialize (~2 minutes)

### Get Your Keys

From Supabase Dashboard > **Settings** > **API**:

| Key | Where to find it | Used for |
|-----|-------------------|----------|
| **Project URL** | Settings > API > Project URL | `SUPABASE_URL` |
| **anon key** | Settings > API > Project API keys > anon public | `SUPABASE_ANON_KEY` |
| **service_role key** | Settings > API > Project API keys > service_role (secret) | `SUPABASE_SERVICE_ROLE_KEY` |

### Get Database Connection String

From Supabase Dashboard > **Settings** > **Database** > **Connection string**:

1. Select **Transaction pooler** mode (recommended for serverless)
2. Copy the connection string — it looks like:
   ```
   postgresql://postgres.XXXXX:YOUR_PASSWORD@aws-0-us-east-2.pooler.supabase.com:6543/postgres
   ```
3. Replace `[YOUR-PASSWORD]` with your database password (set during project creation)

### Push Database Schema

```bash
cd product
supabase link --project-ref YOUR_PROJECT_REF
supabase db push --include-all
```

This creates all 8 tables, RLS policies, and seeds 20 default RSS feeds.

### Create Storage Bucket

From Supabase Dashboard > **Storage**:
1. Click **New Bucket**
2. Name: `images`
3. Check **Public bucket** (images need public CDN URLs)

Or via API:
```bash
curl -X POST "https://YOUR_PROJECT.supabase.co/storage/v1/bucket" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": "images", "name": "images", "public": true}'
```

### Enable OAuth Providers (Optional)

For Google and GitHub social login:

**Google OAuth:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 Client ID (Web application)
3. Set authorized redirect URI: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`
4. In Supabase Dashboard > **Authentication** > **Providers** > **Google**:
   - Enable Google
   - Paste Client ID and Client Secret

**GitHub OAuth:**
1. Go to [GitHub Settings > Developer Settings > OAuth Apps](https://github.com/settings/developers)
2. Create new OAuth App
3. Set callback URL: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`
4. In Supabase Dashboard > **Authentication** > **Providers** > **GitHub**:
   - Enable GitHub
   - Paste Client ID and Client Secret

**Without OAuth:** Email auth is enabled by default. Users can sign up with email + magic link.

## 2. API Keys

### Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Navigate to **API Keys**
3. Create a new key
4. Copy it — this powers highlight extraction, draft generation, and chat

### Google AI API Key (Optional)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click **Create API key**
3. Copy it — this powers Gemini image generation for highlight cards

Without this key, everything works — cards just render without images.

## 3. Environment Setup

### Server (.env)

```bash
cd product/packages/server
cp .env.example .env
```

Fill in:
```env
DATABASE_URL=postgresql://postgres.XXXXX:PASSWORD@aws-0-us-east-2.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://XXXXX.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=AIza...  # optional
PORT=6107
```

### Web App (.env.local)

```bash
cd product/packages/web
```

Create `.env.local`:
```env
VITE_SUPABASE_URL=https://XXXXX.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

### Mobile App (.env)

```bash
cd product/packages/mobile
```

Create `.env`:
```env
EXPO_PUBLIC_SUPABASE_URL=https://XXXXX.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJ...
EXPO_PUBLIC_API_URL=http://localhost:6107
```

## 4. Local Development

```bash
cd product

# Install all dependencies
bun install

# Start the API server (port 6107)
cd packages/server && bun run dev

# In another terminal — start the web app (port 6108)
cd packages/web && bun run dev

# In another terminal — start the mobile app
cd packages/mobile && npx expo start
```

Open http://localhost:6108 for the web app.

## 5. Deploy to Render

### Via Dashboard (Recommended)

1. Push code to GitHub
2. Go to [render.com/dashboard](https://render.com/dashboard)
3. Click **New** > **Blueprint**
4. Connect your GitHub repo
5. Select `product/render.yaml` as the blueprint file
6. Set environment variables (same as server .env above)
7. Deploy

### Via CLI

```bash
# After creating services in dashboard:
render deploys create --service YOUR_SERVICE_ID --confirm
```

The `render.yaml` creates:
- **Web service**: API server on port 6107
- **Cron job**: Daily pipeline at 6 AM ET (11 UTC)
- **Managed Postgres**: pg16 (backup for non-Supabase deployments)

Note: When using Supabase, the Render Postgres is optional — set `DATABASE_URL` to your Supabase connection string instead.

## 6. Self-Host (Docker)

For users who want everything on their own machine:

```bash
cd product

# Set environment variables
export SUPABASE_URL=https://XXXXX.supabase.co
export SUPABASE_ANON_KEY=eyJ...
export SUPABASE_SERVICE_ROLE_KEY=eyJ...
export ANTHROPIC_API_KEY=sk-ant-...

# Start all services
docker compose up -d

# The API runs on http://localhost:6107
```

Docker Compose starts:
- **pgvector** database (port 5432)
- **API server** (port 6107)
- **Cron job** (daily pipeline loop)

## 7. Expo Mobile App

```bash
cd product/packages/mobile

# Install dependencies
bun install

# Start Expo dev server
npx expo start

# Run on iOS simulator
npx expo run:ios

# Run on Android emulator
npx expo run:android

# Build for production
npx eas build --platform ios
npx eas build --platform android
```

### EAS Build Setup

1. Install EAS CLI: `npm install -g eas-cli`
2. Login: `eas login`
3. Configure: `eas build:configure`
4. Set secrets: `eas secret:create --name EXPO_PUBLIC_SUPABASE_URL --value "https://..." --type string`

## Troubleshooting

**"ANTHROPIC_API_KEY not configured"** — Set the key in your server .env file

**Auth not working** — Make sure SUPABASE_URL and SUPABASE_ANON_KEY are correct in both server and client .env files

**No highlights generated** — The pipeline needs content to work with. Share some URLs first, then trigger the pipeline: `POST /api/pipeline/run`

**Images not generating** — GOOGLE_AI_API_KEY is optional. Without it, cards render without images.

**Database connection failed** — Check DATABASE_URL uses the transaction pooler format (port 6543, not 5432)
