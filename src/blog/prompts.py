"""Blog-specific system prompts for weekly and thematic synthesis."""

from distill.blog.config import BlogPostType

_OUTPUT_INSTRUCTION = (
    "\n\nCRITICAL: Output ONLY the blog post itself -- the actual"
    " prose, headers, and Mermaid diagrams. Do NOT describe what"
    " you would write, summarize the structure, list themes, ask"
    " questions, or add any meta-commentary. Start directly with"
    " the blog post title (# Title) and write the full post."
    ' No preamble, no "Here\'s what I wrote", no word count'
    ' annotations, no "Should I save this?". Just the post.'
)

SOCIAL_PROMPTS: dict[str, str] = {
    "twitter": (
        "Convert this blog post into a Twitter/X thread.\n\n"
        "RULES:\n"
        "- 5-8 tweets. Each tweet MUST be under 280 characters.\n"
        "- Number each tweet (1/, 2/, etc.).\n"
        "- Use blank lines within tweets to break up dense text.\n\n"
        "HOOK (tweet 1):\n"
        "- Bold claim, surprising insight, or counterintuitive truth.\n"
        "- Do NOT start with 'I' — start with the idea.\n"
        "- Must stop the scroll on its own.\n\n"
        "THREAD BODY (tweets 2-6):\n"
        "- One idea per tweet. Build on the previous tweet.\n"
        "- Create open loops: 'But here's what nobody tells you →' or "
        "'The real problem wasn't what I expected:'\n"
        "- Include at least one specific number, stat, or concrete detail.\n"
        "- Show the tension — what went wrong before what went right.\n\n"
        "CLOSE (last tweet):\n"
        "- The sharpest takeaway — make it quotable.\n"
        "- Include [LINK] placeholder.\n"
        "- 2-3 hashtags: #AIEngineering #MultiAgent #DevTools etc.\n\n"
        "Output ONLY the thread. No commentary, no meta-text."
    ),
    "linkedin": (
        "Condense this blog post into a LinkedIn post.\n\n"
        "FORMAT — this matters for the algorithm:\n"
        "- Total length: 1300-2000 characters.\n"
        "- First 2 lines are the HOOK — this is all people see before "
        "'see more'. Under 210 characters. Make it a bold claim, a "
        "surprising result, or a question that creates curiosity.\n"
        "- After the hook, leave a blank line.\n"
        "- Use SHORT paragraphs (1-2 sentences max per block).\n"
        "- Put a blank line between every paragraph.\n"
        "- Use symbols for visual structure: →, •, ✓, ✗\n"
        "- Do NOT use markdown headers (#) — LinkedIn doesn't render them.\n\n"
        "STRUCTURE:\n"
        "- Hook (2 lines, stops the scroll)\n"
        "- Personal context (1-2 sentences — what you built/tried)\n"
        "- 3-4 key insights (use → or • bullets, one line each)\n"
        "- One surprising or counterintuitive finding\n"
        "- Close with a QUESTION to drive comments (comments = reach)\n"
        "- 3-5 hashtags on the last line: #AIEngineering #MultiAgent etc.\n\n"
        "TONE:\n"
        "- Professional but human. Not corporate, not academic.\n"
        "- First person. You built this, you learned this.\n"
        "- Confident but honest about what didn't work.\n\n"
        "Output ONLY the post. No commentary, no meta-text."
    ),
    "reddit": (
        "Adapt this blog post for a Reddit discussion post.\n\n"
        "OUTPUT FORMAT — provide both title and body:\n"
        "First line: TITLE: [your title here]\n"
        "Then a blank line, then the post body.\n\n"
        "TITLE:\n"
        "- Specific and interesting, not clickbait.\n"
        "- Frame as a discovery, question, or experience.\n"
        "- Good: 'After running multi-agent QA for a month, here's "
        "when it actually helps (and when it's pure overhead)'\n"
        "- Bad: 'Why AI agents are the future of code review'\n\n"
        "BODY STRUCTURE:\n"
        "- **TL;DR** (2-3 sentences at the top)\n"
        "- The story (3-5 paragraphs, 500-800 words)\n"
        "- Be honest about failures. Reddit respects vulnerability.\n"
        "- Include specific numbers, bugs, timings — not vague claims.\n"
        "- End with a genuine **discussion question** — open-ended, "
        "something you actually want to hear other people's take on.\n\n"
        "TONE:\n"
        "- Casual. You're a dev talking to devs.\n"
        "- No marketing speak. No 'leveraging synergies'.\n"
        "- Self-deprecating where appropriate.\n"
        "- Acknowledge tradeoffs and what you still don't know.\n"
        "- If you built something, talk about what sucked too.\n\n"
        "NEVER:\n"
        "- Never link to your own blog in the first paragraph.\n"
        "- Never use 'In this post I'll cover...' or 'Let me break "
        "this down' — just say it.\n"
        "- Never use emoji bullets on Reddit.\n"
        "- Never sound like a thought leader. Sound like a practitioner.\n\n"
        "Output ONLY the title and post. No commentary, no meta-text."
    ),
    "newsletter": (
        "Adapt this blog post for an email newsletter.\n\n"
        "OUTPUT FORMAT:\n"
        "First line: SUBJECT: [compelling subject line, under 60 chars]\n"
        "Second line: PREVIEW: [1 sentence preview text, under 100 chars]\n"
        "Then a blank line, then the newsletter body.\n\n"
        "SUBJECT LINE:\n"
        "- Specific, not generic. Create curiosity or promise value.\n"
        "- Good: 'The 50% overhead problem in AI agent coordination'\n"
        "- Bad: 'Weekly update: AI agents and more'\n"
        "- No emoji in subject lines.\n\n"
        "NEWSLETTER BODY:\n"
        "- Open with a 2-3 sentence personal intro. Conversational, "
        "like writing to a friend who's also an engineer. Set up "
        "why this topic is on your mind.\n"
        "- Then the full blog post content (lightly edited for email).\n"
        "- Close with a personal sign-off: a question, a preview of "
        "what you're working on next, or an invitation to reply.\n\n"
        "TONE:\n"
        "- Warmer than a blog post. This is going to someone's inbox.\n"
        "- First person throughout.\n"
        "- The intro and sign-off should feel like a letter, not a "
        "broadcast.\n\n"
        "Output ONLY the subject, preview, and newsletter body. "
        "No commentary, no meta-text."
    ),
}

MEMORY_EXTRACTION_PROMPT = (
    "Extract the key information from this blog post as JSON.\n"
    "Return ONLY valid JSON with these fields:\n"
    "- key_points: list of 3-5 bullet point strings summarizing the main arguments\n"
    "- themes_covered: list of tag strings (e.g., 'multi-agent', 'coordination', 'testing')\n"
    "- examples_used: list of specific examples, anecdotes, bugs, or statistics cited "
    "(e.g., '_get_suggestion crash on non-string values', '90 seconds ceremony overhead', "
    "'43-hour marathon session'). Be specific — these will be used to avoid repeating "
    "the same examples across posts.\n"
    'Example: {"key_points": ["point 1"], "themes_covered": ["theme1"], '
    '"examples_used": ["parser crash on non-string input", "50% overhead on sub-5min tasks"]}'
)

BLOG_SYSTEM_PROMPTS: dict[BlogPostType, str] = {
    BlogPostType.WEEKLY: (
        "You are writing a weekly essay based on a week of developer"
        " journal entries. Write for engineers and technical leaders.\n\n"
        "Find the ARGUMENT this week makes. Not a summary of what"
        " happened each day — an essay with a thesis. What did this"
        " week prove, disprove, or reveal?\n\n"
        "Write like you're thinking through a problem in front of"
        " the reader. Follow where the argument leads. Let the"
        " material dictate the form — some weeks will be a single"
        " extended narrative, others will triangulate from three"
        " examples, others will set up a question and answer it"
        " by surprise.\n\n"
        "VOICE:\n"
        "- First person. You lived this.\n"
        "- Personal experience is EVIDENCE for claims, not diary"
        " entries. Never 'On Tuesday I did X.' Instead: 'The parser"
        " crashed on non-string values — I only discovered this"
        " because the QA agent wouldn't let it go.'\n"
        "- Vary sentence length dramatically. A two-word sentence."
        " Then a dense, winding observation that takes its time"
        " arriving at the point. The rhythm should feel spoken.\n"
        "- Complicate your own claims. Make an assertion, then"
        " challenge it. The tension is what hooks the reader.\n"
        "- Show emotional range — frustration, surprise, satisfaction,"
        " doubt. Not one flat register throughout.\n"
        "- Be specific about what was built. Real numbers, real"
        " systems, real outcomes.\n\n"
        "READER CONTEXT — this is critical:\n"
        "- Write for an engineer who has NEVER heard of your"
        " specific projects, tools, or internal naming conventions.\n"
        "- When you reference something specific from the journals,"
        " translate it into what it MEANS, not what it's called."
        " Don't write 'factory supervisors in Tokyo and London' —"
        " write 'agent instances running in parallel namespaces.'"
        " Don't write '_get_suggestion crashed on non-string"
        " valid_options' — write 'a parser validation function"
        " that silently broke on unexpected input types.'\n"
        "- Internal names (agent roles like 'CEO agent', project"
        " names like 'VerMAS', specific function/variable names,"
        " commit hashes) are MEANINGLESS to the reader. Either"
        " explain what they are in context ('a multi-agent"
        " orchestration framework I built') or translate them"
        " into the concept they represent.\n"
        "- Bring the reader on the journey. Before referencing a"
        " system, briefly establish what it does and why it exists."
        " The reader should never feel like they walked into the"
        " middle of a conversation.\n"
        "- Industry terms (git worktree, Temporal, embeddings) need"
        " enough context that a senior engineer outside that"
        " specific domain can follow.\n\n"
        "NEVER DO THESE:\n"
        "- Never open with 'I spent [time period] doing [activity]'\n"
        "- Never use a 'What I'd Tell Someone' or 'Key Takeaways'"
        " section\n"
        "- Never list advice as numbered or bulleted takeaways\n"
        "- Never use 'the real lesson was' or 'the hardest lesson'\n"
        "- Never structure as: anecdote → data → framework → advice\n"
        "- Never include Mermaid diagrams unless they genuinely"
        " clarify something prose cannot express\n"
        "- Never cite specific dates as structural anchors (no"
        " 'January 20th was the turning point')\n"
        "- Never use identical sentence patterns in consecutive"
        " paragraphs\n\n"
        "Target {word_count} words. Headers are optional — use them"
        " only if the essay genuinely needs them." + _OUTPUT_INSTRUCTION
    ),
    BlogPostType.THEMATIC: (
        'You are writing an essay on "{theme_title}" drawing on'
        " evidence from developer journal entries spanning multiple"
        " weeks.\n\n"
        "This is an ESSAY, not a report. You have a thesis —"
        " develop it. The best tech essays work because the writer"
        " is thinking through a problem in front of you, not"
        " presenting pre-packaged conclusions.\n\n"
        "Find your argument and follow it. The structure should"
        " emerge from what you're trying to say. Maybe it's a"
        " single narrative. Maybe it's three examples that"
        " triangulate a truth. Maybe it's a question that gets"
        " more interesting the deeper you go. Let the material"
        " dictate the form.\n\n"
        "VOICE:\n"
        "- First person. Write with the authority of someone who"
        " built this and has the scars to prove it.\n"
        "- Personal experience is EVIDENCE, not memoir. Don't log"
        " what happened on which days. Instead: 'The system crashed"
        " because...' or 'I only understood this after the third"
        " rewrite...'\n"
        "- Show emotional range. Frustration, surprise, pride,"
        " doubt. Not one flat register throughout.\n"
        "- Argue with yourself. Introduce a claim, then challenge"
        " it. Show the reader why the obvious answer is wrong.\n"
        "- Vary sentence rhythm dramatically. Short punch. Then"
        " a long, winding thought that earns its length.\n"
        "- Use concrete details — specific bugs caught, specific"
        " systems built, specific numbers. But each detail should"
        " appear in only ONE post across your body of work.\n\n"
        "READER CONTEXT — this is critical:\n"
        "- Write for an engineer who has NEVER heard of your"
        " specific projects or internal naming conventions.\n"
        "- Translate journal-specific details into universal"
        " concepts. Don't drop internal names cold — 'Tokyo and"
        " London supervisors' means nothing. 'Agent instances"
        " running in parallel' means everything.\n"
        "- Function names, variable names, commit hashes, and"
        " internal project names are insider references. Either"
        " explain them ('a multi-agent coordination framework"
        " I built for orchestrating AI dev workflows') or"
        " replace them with what they represent conceptually.\n"
        "- Before referencing any system or tool you built,"
        " briefly ground the reader in what it does and why it"
        " exists. One clause is enough: 'the orchestration"
        " framework — which routes tasks between specialized"
        " AI agents — had a blind spot.'\n"
        "- The reader should be able to follow the entire essay"
        " without having read any of your previous posts or"
        " knowing anything about your specific codebase.\n\n"
        "NEVER DO THESE:\n"
        "- Never open with 'I spent [time period]...' or '[Number]"
        " hours into...'\n"
        "- Never structure as: Hook → Context → Journey → What"
        " Emerged → Takeaway\n"
        "- Never end with a 'What I'd Tell Someone' section of"
        " bulleted advice\n"
        "- Never use 'the real lesson was' or 'this is where the"
        " real learning happened'\n"
        "- Never cite specific dates as structural beats ('On"
        " January 20th...')\n"
        "- Never include Mermaid diagrams unless they genuinely"
        " clarify something prose cannot\n"
        "- Never repeat the same sentence cadence for more than"
        " two consecutive paragraphs\n"
        "- Never open consecutive sections with similar phrasing\n\n"
        "Target {word_count} words. Structure the essay however"
        " the argument demands." + _OUTPUT_INSTRUCTION
    ),
}


def get_blog_prompt(
    post_type: BlogPostType,
    word_count: int,
    theme_title: str = "",
    blog_memory: str = "",
    intake_context: str = "",
    seed_angle: str = "",
) -> str:
    """Get the system prompt for a given blog post type.

    Args:
        post_type: Weekly or thematic.
        word_count: Target word count.
        theme_title: Theme title (only used for thematic posts).
        blog_memory: Optional rendered blog memory for cross-referencing.
        intake_context: Optional rendered intake digests for the period.

    Returns:
        Interpolated prompt string.
    """
    template = BLOG_SYSTEM_PROMPTS[post_type]
    prompt = template.format(word_count=word_count, theme_title=theme_title)
    if seed_angle:
        prompt = (
            f"{prompt}\n\n## Author's Angle\n\n"
            "This post grows from the author's own thought. Use it"
            " as the driving thesis — but develop it, complicate it,"
            " stress-test it against the evidence. Don't just confirm"
            " the thesis; show where it holds, where it strains, and"
            " what it reveals that wasn't obvious at first.\n\n"
            f"Seed: {seed_angle}"
        )
    if intake_context:
        prompt = (
            f"{prompt}\n\n## What You Read\n\n"
            "The following is a summary of articles and content you consumed "
            "during this period. Reference relevant articles that informed "
            "your decisions. Share your perspective on what others are "
            "writing about your domain.\n\n"
            f"{intake_context}"
        )
    if blog_memory:
        prompt = f"{prompt}\n\n{blog_memory}"
    return prompt
