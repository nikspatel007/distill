"""Blog-specific system prompts for weekly and thematic synthesis."""

from distill.blog.config import BlogPostType

_OUTPUT_INSTRUCTION = (
    "\n\nCRITICAL: Output ONLY the blog post itself -- the actual"
    " prose, headers, and Mermaid diagrams. Do NOT describe what"
    " you would write, summarize the structure, list themes, ask"
    " questions, or add any meta-commentary. Start directly with"
    " the blog post title (# Title) and write the full post."
    " No preamble, no \"Here's what I wrote\", no word count"
    " annotations, no \"Should I save this?\". Just the post."
)

SOCIAL_PROMPTS: dict[str, str] = {
    "twitter": (
        "Convert this blog post into a Twitter/X thread of 5-8 tweets. "
        "Each tweet MUST be 280 characters or fewer. "
        "First tweet is the hook -- make it compelling and standalone. "
        "Number each tweet (1/, 2/, etc.). "
        "Each tweet should be standalone-readable. "
        "Last tweet: include [LINK] placeholder and a brief CTA. "
        "Output ONLY the thread, no commentary."
    ),
    "linkedin": (
        "Condense this blog post into a LinkedIn post (1000-1300 characters total). "
        "Professional tone. Structure: hook paragraph → 3 key takeaways (use emoji bullets) "
        "→ closing insight. Include 3-5 relevant hashtags at the end "
        "(#MultiAgent #AIEngineering #DevOps etc.). "
        "Output ONLY the post, no commentary."
    ),
    "reddit": (
        "Adapt this blog post for a Reddit r/programming discussion post. "
        "Structure: **TL;DR** (2-3 sentences) → **Key Points** (3-5 bullets) → "
        "brief narrative (2-3 paragraphs, ~500-800 words, more casual tone) → "
        "**Discussion question** (engaging, open-ended). "
        "Output ONLY the post, no commentary."
    ),
}

MEMORY_EXTRACTION_PROMPT = (
    "Extract the key information from this blog post as JSON.\n"
    "Return ONLY valid JSON with these fields:\n"
    "- key_points: list of 3-5 bullet point strings summarizing the main arguments\n"
    "- themes_covered: list of tag strings (e.g., 'multi-agent', 'coordination', 'testing')\n"
    'Example: {"key_points": ["point 1", "point 2"], "themes_covered": ["theme1"]}'
)

BLOG_SYSTEM_PROMPTS: dict[BlogPostType, str] = {
    BlogPostType.WEEKLY: (
        "You are writing a weekly synthesis blog post based on a week"
        " of developer journal entries.\n\n"
        "Synthesize these daily journal entries into one cohesive,"
        " publishable blog post. Write for a technical audience"
        " interested in AI-assisted development and multi-agent"
        " orchestration.\n\n"
        "Your job:\n"
        "- Extract the week's narrative arc: what was the story"
        " of this week?\n"
        "- Identify key decisions, turning points, and lessons"
        " learned\n"
        "- Reference specific days naturally (\"By Wednesday, the"
        ' pattern was clear..." or "Monday started with...")\n'
        "- Find the through-line connecting disparate daily work"
        " into a coherent theme\n"
        "- End with actionable insights, not just observations\n\n"
        "Include 1-2 Mermaid diagrams using ```mermaid fences."
        " Good diagram choices:\n"
        "- Architecture decisions or system evolution\n"
        "- Workflow changes or process improvements\n"
        "- Decision trees that emerged from the week's work\n"
        "- Timeline of how understanding evolved\n\n"
        'Write in first person ("I", "we"). Be specific with'
        " numbers and data points from the journals. This is thought"
        " leadership backed by real experience, not abstract"
        " advice.\n\n"
        "Target {word_count} words. Write flowing prose with natural"
        " paragraph breaks. Use headers sparingly (2-3 max for a"
        " post this length)."
        + _OUTPUT_INSTRUCTION
    ),
    BlogPostType.THEMATIC: (
        "You are writing a thematic deep-dive blog post on"
        ' "{theme_title}" based on evidence from multiple days of'
        " developer journal entries.\n\n"
        "Structure the post as:\n"
        "1. **Hook**: Open with a concrete, relatable scenario that"
        " illustrates the problem\n"
        "2. **Problem statement**: Define the challenge clearly,"
        " grounded in real experience\n"
        "3. **Evidence from experience**: Walk through what happened"
        " across multiple days -- the patterns, the failures, the"
        " discoveries\n"
        "4. **Analysis**: What does this mean? Why does it happen?"
        " What are the underlying dynamics?\n"
        "5. **Takeaway**: Actionable advice for other engineers"
        " facing similar decisions\n\n"
        "Include data points and specific examples: session counts,"
        " success rates, time spent, concrete numbers from the"
        " journal entries. These make the piece credible.\n\n"
        "Include 2-3 Mermaid diagrams using ```mermaid fences."
        " Good diagram choices:\n"
        "- The problem/solution architecture\n"
        "- Before/after comparisons\n"
        "- Decision flowcharts\n"
        "- System interaction patterns that reveal the issue\n\n"
        "Write with authority -- you lived this, you have the data."
        " Make it useful to other engineers building multi-agent"
        " systems or working with AI-assisted development.\n\n"
        'Write in first person ("I", "we"). Be honest about'
        " failures and wrong turns -- that's what makes thought"
        " leadership genuine.\n\n"
        "Target {word_count} words. Use headers to structure the"
        " piece (3-4 sections). Write flowing prose, not bullet"
        " lists."
        + _OUTPUT_INSTRUCTION
    ),
}


def get_blog_prompt(
    post_type: BlogPostType,
    word_count: int,
    theme_title: str = "",
    blog_memory: str = "",
) -> str:
    """Get the system prompt for a given blog post type.

    Args:
        post_type: Weekly or thematic.
        word_count: Target word count.
        theme_title: Theme title (only used for thematic posts).
        blog_memory: Optional rendered blog memory for cross-referencing.

    Returns:
        Interpolated prompt string.
    """
    template = BLOG_SYSTEM_PROMPTS[post_type]
    prompt = template.format(word_count=word_count, theme_title=theme_title)
    if blog_memory:
        prompt = f"{prompt}\n\n{blog_memory}"
    return prompt
