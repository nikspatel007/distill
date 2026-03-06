/**
 * Secret redaction for session content.
 *
 * Scans text for common secret patterns (API keys, passwords, tokens, etc.)
 * and replaces the values with [REDACTED] while preserving structure.
 */

/** Pattern definitions: each has a regex and a replacement function. */
const SECRET_PATTERNS: Array<{ pattern: RegExp; replacer: (match: string, ...groups: string[]) => string }> = [
  // Key-value patterns: API_KEY=value, password=value, token=value, secret=value
  // Handles optional quotes around values, = or : as separator
  {
    pattern: /\b(api[_-]?key|apikey|api[_-]?secret|secret[_-]?key|access[_-]?key|private[_-]?key|password|passwd|pwd|token|auth[_-]?token|access[_-]?token|refresh[_-]?token|secret|client[_-]?secret|app[_-]?secret)\s*[=:]\s*["']?([^\s"',;}{]+)["']?/gi,
    replacer: (_match: string, key: string, _value: string) => `${key}=[REDACTED]`,
  },

  // Bearer tokens in Authorization headers
  {
    pattern: /\b(Bearer)\s+([A-Za-z0-9._\-/+=]{20,})/g,
    replacer: (_match: string, prefix: string, _token: string) => `${prefix} [REDACTED]`,
  },

  // AWS access key IDs (AKIA...)
  {
    pattern: /\b(AKIA[A-Z0-9]{16})\b/g,
    replacer: () => `[REDACTED]`,
  },

  // AWS secret access keys (40 char base64-ish following a key ID context)
  {
    pattern: /\b(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*["']?([A-Za-z0-9/+=]{40})["']?/gi,
    replacer: (_match: string, key: string) => `${key}=[REDACTED]`,
  },

  // SSH private keys (multi-line block)
  {
    pattern: /-----BEGIN\s+(RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END\s+(RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/g,
    replacer: () => `[REDACTED SSH PRIVATE KEY]`,
  },

  // .env file lines (KEY=value where KEY is all uppercase with underscores)
  {
    pattern: /^([A-Z][A-Z0-9_]{2,})\s*=\s*["']?([^\s"'#]+)["']?/gm,
    replacer: (_match: string, key: string, value: string) => {
      // Only redact if the value looks secret-ish (long enough, not a simple number/boolean/url-scheme)
      if (value.length >= 16 || /key|secret|token|password|pwd/i.test(key)) {
        return `${key}=[REDACTED]`;
      }
      return `${key}=${value}`;
    },
  },

  // Generic long hex/base64 strings that look like secrets (32+ chars)
  {
    pattern: /\b(sk-[A-Za-z0-9]{32,})\b/g,
    replacer: () => `[REDACTED]`,
  },

  // GitHub personal access tokens
  {
    pattern: /\b(ghp_[A-Za-z0-9]{36,})\b/g,
    replacer: () => `[REDACTED]`,
  },

  // GitHub fine-grained tokens
  {
    pattern: /\b(github_pat_[A-Za-z0-9_]{22,})\b/g,
    replacer: () => `[REDACTED]`,
  },

  // Slack tokens
  {
    pattern: /\b(xox[bpras]-[A-Za-z0-9-]{10,})\b/g,
    replacer: () => `[REDACTED]`,
  },
];

/**
 * Redact secrets from content string.
 *
 * Applies all secret patterns and replaces matched values with [REDACTED].
 * Preserves the key/label so the structure remains readable.
 */
export function redactSecrets(content: string): string {
  let result = content;
  for (const { pattern, replacer } of SECRET_PATTERNS) {
    // Reset lastIndex for stateful regexes
    pattern.lastIndex = 0;
    result = result.replace(pattern, replacer as (...args: string[]) => string);
  }
  return result;
}
