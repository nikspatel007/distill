-- Distill Product Schema

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  display_name TEXT NOT NULL,
  avatar_url TEXT,
  preferences JSONB DEFAULT '{"notificationsEnabled": true, "shareHighlights": true, "shareSessions": false}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shared_urls (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  url TEXT NOT NULL,
  title TEXT,
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  processed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS content_items (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  source TEXT NOT NULL,
  url TEXT,
  title TEXT NOT NULL,
  summary TEXT,
  full_text TEXT,
  tags JSONB DEFAULT '[]'::jsonb,
  entities JSONB DEFAULT '[]'::jsonb,
  image_url TEXT,
  image_prompt TEXT,
  published_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reading_briefs (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  date DATE NOT NULL,
  highlights JSONB DEFAULT '[]'::jsonb,
  drafts JSONB DEFAULT '[]'::jsonb,
  connection JSONB,
  learning_pulse JSONB DEFAULT '[]'::jsonb,
  discoveries JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS reading_briefs_user_date_idx ON reading_briefs(user_id, date);

CREATE TABLE IF NOT EXISTS follows (
  follower_id UUID NOT NULL REFERENCES users(id),
  following_id UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (follower_id, following_id)
);

CREATE TABLE IF NOT EXISTS feed_items (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  url TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS default_feeds (
  id SERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  name TEXT,
  category TEXT,
  active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  session_id TEXT NOT NULL,
  project TEXT NOT NULL,
  summary TEXT,
  duration_minutes INTEGER NOT NULL,
  lines_added INTEGER DEFAULT 0,
  lines_removed INTEGER DEFAULT 0,
  files_changed JSONB DEFAULT '[]'::jsonb,
  session_timestamp TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS sessions_user_session_idx ON sessions(user_id, session_id);

-- Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_urls ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE reading_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE follows ENABLE ROW LEVEL SECURITY;
ALTER TABLE feed_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE default_feeds ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Users can read/write their own data
CREATE POLICY "users_own_data" ON users FOR ALL USING (id = auth.uid());
CREATE POLICY "users_own_shared" ON shared_urls FOR ALL USING (user_id = auth.uid());
CREATE POLICY "users_own_content" ON content_items FOR ALL USING (user_id = auth.uid());
CREATE POLICY "users_own_briefs" ON reading_briefs FOR ALL USING (user_id = auth.uid());
CREATE POLICY "users_own_sessions" ON sessions FOR ALL USING (user_id = auth.uid());

-- Follows: users manage their own follows
CREATE POLICY "users_own_follows" ON follows FOR ALL USING (follower_id = auth.uid());

-- Feed items: visible to self and followers
CREATE POLICY "feed_visible_to_followers" ON feed_items FOR SELECT USING (
  user_id = auth.uid() OR
  user_id IN (SELECT following_id FROM follows WHERE follower_id = auth.uid())
);
CREATE POLICY "users_own_feed_items" ON feed_items FOR INSERT WITH CHECK (user_id = auth.uid());

-- Default feeds: readable by all authenticated users
CREATE POLICY "default_feeds_readable" ON default_feeds FOR SELECT USING (true);

-- Service role bypass for pipeline operations
CREATE POLICY "service_role_users" ON users FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_content" ON content_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_briefs" ON reading_briefs FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_feed" ON feed_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_sessions" ON sessions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_shares" ON shared_urls FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_default_feeds" ON default_feeds FOR ALL USING (auth.role() = 'service_role');

-- Seed default RSS feeds (top tech/AI blogs)
INSERT INTO default_feeds (url, name, category) VALUES
  ('https://simonwillison.net/atom/everything/', 'Simon Willison', 'ai'),
  ('https://lilianweng.github.io/index.xml', 'Lilian Weng', 'ai'),
  ('https://blog.langchain.dev/rss/', 'LangChain', 'ai'),
  ('https://openai.com/blog/rss.xml', 'OpenAI', 'ai'),
  ('https://www.anthropic.com/feed.xml', 'Anthropic', 'ai'),
  ('https://huggingface.co/blog/feed.xml', 'Hugging Face', 'ai'),
  ('https://martinfowler.com/feed.atom', 'Martin Fowler', 'engineering'),
  ('https://blog.pragmaticengineer.com/rss/', 'Pragmatic Engineer', 'engineering'),
  ('https://danluu.com/atom.xml', 'Dan Luu', 'engineering'),
  ('https://research.google/blog/rss/', 'Google Research', 'ai'),
  ('https://engineering.atspotify.com/feed/', 'Spotify Engineering', 'engineering'),
  ('https://netflixtechblog.com/feed', 'Netflix Tech Blog', 'engineering'),
  ('https://discord.com/blog/rss.xml', 'Discord Engineering', 'engineering'),
  ('https://github.blog/feed/', 'GitHub Blog', 'engineering'),
  ('https://newsletter.pragmaticengineer.com/feed', 'Pragmatic Engineer Newsletter', 'engineering'),
  ('https://stratechery.com/feed/', 'Stratechery', 'strategy'),
  ('https://www.joelonsoftware.com/feed/', 'Joel on Software', 'engineering'),
  ('https://charity.wtf/feed/', 'Charity Majors', 'engineering'),
  ('https://lethain.com/feeds/', 'Will Larson', 'engineering'),
  ('https://www.kalzumeus.com/feed/', 'patio11', 'startups')
ON CONFLICT (url) DO NOTHING;
