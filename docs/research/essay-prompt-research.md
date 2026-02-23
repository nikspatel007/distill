# Essay Prompt Research: Diagnosing and Fixing Structural Monotony

**Date:** 2026-02-14
**Scope:** Analysis of `src/blog/prompts.py`, `src/intake/prompts.py`, `src/journal/prompts.py`
**Corpus:** 6 weekly essays, 1 thematic essay, 3 intake digests, 5 journal entries

---

## 1. Diagnosis: What the Published Output Actually Looks Like

### 1.1 Title Repetition and Self-Referential Gravity

The 8 published titles cluster into two failure modes:

**Self-referential loop (3/8):**
- "When the Pipeline Reads Itself"
- "The Machine That Reads Itself"
- "The Pipeline That Watches Itself"

These are not just similar; they are structurally identical: `The [System Noun] That [Self-Referential Verb] Itself`. The LLM has found a title formula that sounds clever and keeps reusing it.

**"The Week I [Verb Phrase]" opener (3/8):**
- "The Week I Proved My Own Framework Wrong"
- "The Week I Couldn't Stop Testing"
- "The Week I Proved Myself Wrong About Productivity"
- "The Week I Stopped Arguing With Myself"

Four of six weekly essays use this exact pattern. It produces a confessional, inward-looking framing that the prompt explicitly tries to avoid ("not a diary of what happened").

**What works (2/8):**
- "Letting the Robots Practice on String Functions" (concrete, specific, intriguing)
- "Killing Your Darlings, 842 Lines at a Time" (borrows a known phrase, adds specificity)
- "Cognitive Debt and the Refactoring Step You Skip" (concept + action, externally relevant)
- "The Monolith Extraction Pattern: When Implicit Dependencies Become Explicit" (teaches something)

The good titles share a property: they name a concept or technique, not a personal experience.

### 1.2 Opening Sentence Patterns

Every weekly essay opens with one of two shapes:

**Shape A: "I built X" / "I spent time on X" preamble**
> "I've been building a multi-agent orchestration platform for months."
> "I built an orchestration system for coordinating multiple AI agents."
> "I built a multi-agent orchestration framework."

**Shape B: "There's a particular kind of..." philosophical setup**
> "There's a particular kind of hell reserved for engineers who build monitoring systems."
> "There's a particular kind of paralysis that only engineers know."
> "There's a particular kind of frustration that comes from watching yourself make the same mistake..."

Shape B appears in 3 of 6 weekly posts, making it the dominant opener. It is a strong sentence form, but when every essay starts this way, it becomes a signature tell of LLM generation.

### 1.3 Structural Shape: The Confession Arc

Every weekly essay follows an identical narrative arc:

1. **Setup:** I built an impressive system (1-2 paragraphs)
2. **Problem:** The system has a fundamental flaw I kept ignoring (2-3 paragraphs)
3. **Evidence:** Day-by-day walkthrough of the week proving the flaw exists (2-4 paragraphs)
4. **Break:** One session / one day where something shifted (1-2 paragraphs)
5. **Reflection:** What this means, with a self-deprecating admission (1-2 paragraphs)
6. **Coda:** Next week, things will be different (1 paragraph)

This is the "developer confessional" structure. It reads well once. By the fourth repetition, the reader knows the shape before finishing the first paragraph. The prompt says "not a diary" and "never frame as a failure or confession," but the confession arc persists because:

- The source data (journal entries) is inherently confessional. The journal prompt encourages honest self-reflection.
- The weekly prompt says "find the most interesting PATTERN, TECHNIQUE, or ARCHITECTURE" but does not enforce external framing. The LLM finds the self-referential pattern more interesting than any technique.
- The "NEVER DO THESE" list bans surface-level symptoms (specific phrases) but not the underlying structural tendency.

### 1.4 Paragraph Rhythm

Paragraphs in the weekly essays are remarkably uniform in length: 4-7 sentences each, with sentences averaging 15-25 words. There are almost no single-sentence paragraphs, no two-sentence paragraphs, no extended multi-paragraph arguments. The rhythm is flat. Compare this to Paul Graham, whose essays use single-sentence paragraphs as percussion, or Tim Urban, who alternates between 1-line zingers and 200-word explorations.

### 1.5 The Intake Digest Problem

The intake digests (daily reading essays) have their own distinct failure mode. Despite the prompt saying "write like a human, not a research analyst" and banning headers like "What I Read" and "Emerging Themes," the Feb 13 digest contains:

- "## What I Built"
- "## What I Consumed"
- "## Connections"
- "## Emerging Themes"
- "## Threads to Watch"

These are the exact banned headers, word for word. The LLM is ignoring the anti-pattern list entirely. The Feb 9 digest has the same structure. The Feb 14 digest (which went to Ghost) is the only one that avoids this, suggesting the Ghost prompt or context is different, or that the system prompt was recently updated.

This reveals a critical finding: **anti-pattern lists in the form "never do X" are unreliable for Claude**. The model acknowledges them during initial processing but defaults to trained patterns when generating long output.

### 1.6 The Em-Dash Ban

The em-dash ban appears in every single prompt across all three files (journal, intake, blog) -- 11 separate occurrences. Review of the output shows it is largely working: the published essays contain very few em-dashes. However, the ban has a side effect: it produces slightly awkward constructions where an em-dash would be natural. Sentences that should be parenthetical asides instead use semicolons or full stops, making the prose feel more formal than conversational.

The em-dash ban is effective but heavy-handed. A more nuanced instruction would be "use em-dashes sparingly, no more than 2 per essay."

---

## 2. Root Cause Analysis

### 2.1 The Prompt Is Too Focused on Voice, Not Enough on Structure

The weekly blog prompt spends 400+ words on voice, tone, framing, and anti-patterns. It spends zero words on essay structure or shape. The only structural guidance is:

> "Target {word_count} words. Headers are optional; use them only if the essay genuinely needs them."

This leaves the LLM to invent structure from scratch each time, and it consistently picks the same one (confession arc) because that shape most naturally emerges from confessional journal source data.

### 2.2 The Anti-Pattern List Is Fighting Symptoms, Not Causes

The current approach:
- Ban: "Never open with 'I spent [time period] doing [activity]'"
- Ban: "Never use 'the real lesson was'"
- Ban: "Never cite specific dates as structural anchors"
- Ban: "Never list advice as numbered or bulleted takeaways"

These target specific phrases, but the LLM can rephrase around any of them while preserving the underlying structure. Banning "I spent Monday doing X" does not prevent the model from writing a day-by-day chronological walkthrough. Banning "the real lesson" does not prevent the confession-to-epiphany arc.

Effective anti-pattern guidance should target structural tendencies, not lexical choices.

### 2.3 No Variety Mechanism Exists

The prompt is deterministic. Same system prompt, same type of source data, same structural affordances. The only variation mechanism is BlogMemory's example dedup ("DO NOT REUSE These Examples"), which prevents recycling specific anecdotes but does nothing about essay shape, title pattern, or narrative arc.

The prompt does not:
- Suggest different essay shapes to try
- Vary its own instructions based on what has been written before
- Provide structural diversity targets
- Reference the titles of previous posts for dedup

### 2.4 Source Data Gravitational Pull

The journal entries themselves are deeply self-referential. Nearly every entry discusses:
- The orchestration framework
- Coordination overhead
- Meta-analysis of meta-analysis
- The same two projects (VerMAS, Distill)

When you ask an LLM to "find the most interesting PATTERN" from data that is 80% about one pattern (coordination overhead), it will write about coordination overhead. The prompt needs to actively push against the gravitational center of the source data.

### 2.5 The Intake Prompt Contradicts Itself

The daily intake prompt asks for "a personal essay about today's reading" written like "a letter to a smart friend," but then provides structure guidance that steers toward analytical frameworks: "Bridge them," "Find the thread," "The last paragraph should echo the first." These are essay-craft instructions, not letter-writing instructions. The result is an awkward hybrid that reads like neither a personal letter nor a well-structured essay.

---

## 3. What Good Looks Like: Lessons from Human Writers

### 3.1 Paul Graham's Structural Variety

Graham's essays use at least four distinct shapes:
- **Thesis-evidence**: State a claim, provide escalating evidence (e.g., "Do Things That Don't Scale")
- **Exploration**: Start with a question, follow it to an unexpected conclusion (e.g., "What You Can't Say")
- **Redefinition**: Take a familiar concept and show it means something different (e.g., "Maker's Schedule, Manager's Schedule")
- **Historical narrative**: Trace the evolution of an idea through time (e.g., "The Submarine")

His titles are concepts, not experiences: "How to Do Great Work," "The Bus Ticket Theory of Genius," "Superlinear Returns." The title names the idea the reader will take away.

### 3.2 Stratechery's Analytical Framework

Ben Thompson at Stratechery maintains voice consistency through a stable analytical lens (aggregation theory, disruption theory) while achieving structural variety by applying that lens to different subjects each week. The subject changes; the analytical framework stays constant. This is the inverse of the current Distill approach, where the subject stays constant (the same two projects) and the structure stays constant (confession arc).

### 3.3 Wait But Why's Engagement Techniques

Tim Urban achieves variety through format shifts within pieces: prose alternates with hand-drawn illustrations, lists, nested asides, dialogues, and thought experiments. The key principle is that variety comes from mixing modes within a piece, not just between pieces.

### 3.4 Common Thread

All three writers share one property: **the essay's organizing principle is an external idea, not a personal experience**. The personal experience appears as evidence supporting the idea, not as the subject itself. This is exactly what the Distill prompt claims to want ("The PATTERN is the subject") but fails to enforce.

---

## 4. Proposed Improvements

### 4.1 Essay Shape Rotation for Weekly Posts

Replace the current structural non-guidance with an explicit menu of essay shapes. Each generation should pick a shape that differs from the previous 2-3 posts.

**Proposed shapes:**

1. **The Pattern Essay**: "Here is a technique I discovered. Here is how it works. Here is when to use it and when not to. Here is what it connects to beyond my specific project." (Closest to current intent, but focused outward.)

2. **The Comparison Essay**: "Two approaches to the same problem. Where each one wins. The surprising factor that determines which is better." (Forces external framing by requiring a contrast.)

3. **The Threshold Essay**: "Below this line, X behaves one way. Above it, X behaves completely differently. Here is where the line is and why it matters." (Extracts a specific, teachable insight.)

4. **The Artifact Essay**: "I am going to show you one specific piece of code / architecture / config / protocol and explain everything it reveals about the problem it solves." (Forces concreteness.)

5. **The Connection Essay**: "Something I read this week illuminated something I built. Here is the connection and why it matters for anyone working in this space." (Forces engagement with external reading.)

6. **The Contrarian Essay**: "The conventional wisdom about X is wrong, or at least incomplete. Here is what I found by actually building it." (Forces an argument with the outside world.)

Implementation: Add a `previous_shapes` field to BlogMemory. The prompt includes: "Your previous essays used these shapes: [list]. Choose a DIFFERENT shape from the following menu for this essay: [menu]."

### 4.2 Title Generation as a Separate Step

Current approach: title is generated as part of the essay, using the same prompt.

Proposed approach: Generate the essay body first, then generate 5 candidate titles with specific constraints:

```
Generate 5 title candidates for this essay. Each must:
- Name a concept, technique, or pattern (NOT a personal experience)
- Be 6-10 words
- Not use "The [Noun] That [Verbs] Itself" or any self-referential framing
- Not start with "The Week I..."
- Not duplicate the structure of these previous titles: {previous_titles}

Candidate styles to try:
1. [Concept]: [Specific Implication] (e.g., "Coordination Overhead: The Tax Nobody Budgets For")
2. [Provocative Claim] (e.g., "Most Agent Tasks Don't Need Agents")
3. [Concrete Detail] as Metaphor (e.g., "Ninety Seconds of Ceremony, Thirty Seconds of Code")
4. [Question Form] (e.g., "When Does Orchestration Earn Its Keep?")
5. [Borrowed Frame] Applied to Tech (e.g., "The Pareto Principle of Agent Coordination")
```

### 4.3 Structural Guardrails, Not Phrase Bans

Replace the current NEVER list with structural constraints:

**Current (ineffective):**
```
- Never open with 'I spent [time period] doing [activity]'
- Never use 'the real lesson was' or 'the hardest lesson'
- Never cite specific dates as structural anchors
```

**Proposed (structural):**
```
STRUCTURAL RULES:
- The essay must teach an external reader something they can apply.
  Test: Could someone who works on a completely different project
  use the insight from this essay? If not, reframe until they could.
- The opening paragraph must name the IDEA, not the personal
  experience. Your experience enters as evidence in paragraph 2 or
  later, not as the essay's frame.
- Do NOT walk through the week chronologically. The essay is
  organized by argument, not by calendar.
- The essay must contain at least one reference to an idea, article,
  technique, or concept from OUTSIDE the author's own projects.
  Internal experience alone is not enough.
- Vary paragraph length deliberately: include at least one
  single-sentence paragraph and at least one paragraph of 6+
  sentences.
```

### 4.4 Fixing the Intake Digest

The intake prompt's anti-pattern list is being completely ignored. Two changes:

**A. Move the anti-pattern guidance into the structure specification (positive framing):**

Instead of:
```
## Anti-patterns (NEVER do these)
- "What I Read" / "What I'm Thinking About" / "Connections" as section headers.
```

Use:
```
## Structure
Your essay should have 2-4 sections. Each section header must be:
- Specific to the content (not a generic category)
- Interesting enough that a reader would want to click on it
- NEVER a meta-label like "What I Read" or "Connections" or "Threads to Watch"

Good headers: "The Parser That Forgave Too Much," "Martin Fowler's Junior Thesis"
Bad headers: "What I Built," "What I Consumed," "Emerging Themes"
```

**B. Enforce blended structure through example:**

Add a brief structural example showing what a good intake essay looks like. Not a full essay, but a skeleton:

```
## Example Structure (for reference, not copying)

# [Compelling Title About the Day's Central Idea]

[Open with the most interesting thing. One article, one idea, one
connection. Make the reader care in the first 2 sentences.]

## [Section about that interesting thing, weaving in what you built]

[The reading and the building should blend. An article made you
think differently about something you coded. A coding decision
validated something you read.]

## [Section that develops or complicates the opening idea]

[Bring in other reading. Disagree with something. Connect two
articles that the authors didn't connect themselves.]

[End with a question or an unresolved tension, not a summary.]
```

### 4.5 Voice Refinement for the Em-Dash Ban

Replace the blanket ban with a calibrated constraint:

**Current:**
```
NEVER use em-dashes or double-hyphens as punctuation.
```

**Proposed:**
```
Use em-dashes sparingly: maximum 2 per essay. When you reach for
an em-dash, first try: a period and new sentence, a colon, or
parentheses. If none of those work naturally, the em-dash is fine.
```

This preserves the intent (reducing the LLM's em-dash addiction) while allowing the occasional natural use that makes prose feel human.

### 4.6 Blog Memory: Title and Structure Dedup

Extend the BlogMemory `render_for_prompt` method to include not just example dedup but also:

1. **Previous titles** (already partially there via post summaries, but not formatted as a dedup constraint)
2. **Previous essay shapes** (new field: `essay_shape: str` on `BlogPostSummary`)
3. **Previous opening sentence patterns** (new field: `opening_type: str`)

The rendered prompt section would look like:

```
## Previous Posts (avoid repetition)

Recent titles: "The Week I Stopped Arguing With Myself,"
"The Monolith Extraction Pattern," ...
DO NOT use similar title structures.

Recent essay shapes: confession-arc, confession-arc, pattern-essay
DO NOT use the confession-arc shape again. Choose from:
comparison, threshold, artifact, connection, or contrarian.

Recent opening types: "There's a particular kind of...",
"I built X", "There's a particular kind of..."
DO NOT open with "There's a particular kind of..." again.
```

### 4.7 External Relevance Enforcement

Add to the weekly prompt:

```
EXTERNAL GROUNDING (required):
Your essay must connect your experience to at least ONE of:
- A published article, paper, or talk by someone else
- A well-known engineering principle or pattern (name it)
- A trend visible across the industry, not just your project
- A counter-argument someone might make, and your response

If the week's reading digests are provided, draw from them.
If not, connect your experience to established engineering
concepts (CAP theorem, Conway's Law, Goodhart's Law, etc.)
that illuminate why the pattern matters beyond your codebase.
```

This forces the essay outward. The current prompt says "write for engineers who build things" but does not require engagement with the engineering world beyond the author's own projects.

### 4.8 Journal Prompt: Breaking the Confession Seed

The journal prompt (dev-journal style) inadvertently seeds the confession arc by saying:

> "When something didn't work, frame it as a discovery or a puzzle you solved, not a failure."

This sounds positive but still makes the essay about things that didn't work. The journal data then feeds into the weekly blog prompt, which tries to find a pattern, and the most salient pattern is always the failure-reframed-as-discovery.

Add to the journal prompt:

```
Focus on what you MADE, not what you realized. A journal entry
about building a parser is more useful downstream than a journal
entry about realizing you've been building parsers wrong. The
realization can be one sentence. The parser should be the story.
```

This shifts the raw material itself, so the blog prompt has richer, more concrete source data to work with.

---

## 5. Implementation Priority

Ranked by expected impact on output quality:

| Priority | Change | File | Effort |
|----------|--------|------|--------|
| 1 | Structural guardrails replacing phrase bans | `blog/prompts.py` | Medium |
| 2 | Essay shape rotation menu | `blog/prompts.py` + `blog/blog_memory.py` | Medium |
| 3 | Title generation as separate step | `blog/synthesizer.py` + `blog/prompts.py` | High |
| 4 | Fix intake anti-pattern enforcement | `intake/prompts.py` | Low |
| 5 | External relevance enforcement | `blog/prompts.py` | Low |
| 6 | Blog memory title/structure dedup | `blog/blog_memory.py` | Medium |
| 7 | Em-dash ban calibration | All three prompt files | Low |
| 8 | Journal prompt rebalancing | `journal/prompts.py` | Low |

---

## 6. Testing the Changes

### 6.1 Before/After Evaluation

Generate 3 essays with the current prompts and 3 with the proposed prompts, using the same source data. Evaluate on:

1. **Title uniqueness**: Do the new titles avoid the "The [Noun] That [Verbs] Itself" pattern?
2. **Opening sentence variety**: Do the new essays open differently from each other?
3. **Structural shape**: Do the new essays use different arc structures?
4. **External relevance**: Does each essay connect to something outside the author's projects?
5. **Paragraph rhythm variation**: Do paragraph lengths vary within each essay?
6. **Anti-pattern compliance**: Does the intake digest avoid banned headers?

### 6.2 Automated Checks

Add a post-generation validation step (could be a simple Python function or a separate LLM call) that checks:

- Title does not match `The [Noun] That [Verbs] Itself` regex
- Title does not match `The Week I [Verb]` regex
- Title does not duplicate structure of any title in BlogMemory
- First paragraph does not start with "I built" or "There's a particular kind of"
- Essay does not contain a chronological day-by-day walkthrough
- At least one external reference (URL, named author, or named concept) exists
- Intake digest headers do not match banned list

These could be implemented as a measurer in `src/measurers/` with the same pattern as existing KPI measurers.

---

## 7. Summary of Key Findings

1. **The same essay shape (confession arc) is used in every weekly post.** The prompt bans phrases but not structures. Fix: provide an explicit menu of essay shapes and rotate.

2. **Titles cluster around two patterns** ("The Week I..." and "The [Noun] That [Verbs] Itself"). Fix: generate titles separately with structural constraints and dedup against previous titles.

3. **Anti-pattern lists are unreliable for Claude.** The intake digest ignores banned headers word-for-word. Fix: use positive structural specification instead of negative phrase bans. Show what good looks like, not just what bad looks like.

4. **No variety mechanism exists.** Same prompt, same data shape, same output shape. Fix: BlogMemory should track and enforce diversity across titles, shapes, and openings.

5. **Source data gravity is stronger than prompt instructions.** When journal entries are 80% about coordination overhead, the essay will be about coordination overhead regardless of what the prompt says. Fix: require external grounding and shift journal prompts to emphasize what was built over what was realized.

6. **The em-dash ban works but is too aggressive.** Fix: allow 2 per essay instead of zero.

7. **The best published outputs** (the Feb 14 Ghost intake essay and the W07 weekly) succeed because they have concrete external subject matter (Martin Fowler article, monolith extraction pattern) rather than pure self-reflection.

---

## Sources

### Web Research
- [Lakera: Prompt Engineering Guide 2026](https://www.lakera.ai/blog/prompt-engineering-guide)
- [Grammarly: Common AI Words and Phrases](https://www.grammarly.com/blog/ai/common-ai-words/)
- [Hastewire: Reduce Repetitiveness in AI Essays](https://hastewire.com/blog/reduce-repetitiveness-in-ai-essays-top-strategies)
- [IBM: The 2026 Guide to Prompt Engineering](https://www.ibm.com/think/prompt-engineering)
- [Anthropic: Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Paul Graham: Good Writing](https://paulgraham.com/goodwriting.html)
- [Common Reader: Paul Graham's Plain Rhetoric](https://www.commonreader.co.uk/p/paul-grahams-plain-rhetoric)
- [Ellen Fishbein: What Makes Paul Graham a Great Writer](https://ellenrhymes.com/paul-graham)
- [First Round Review: Tim Urban on Parsing and Transmitting Complex Ideas](https://review.firstround.com/wait-but-whys-tim-urban-on-parsing-and-transmitting-complex-ideas/)
- [Constantly Thinking: Detecting AI Patterns](https://constantlythinking.com/posts/humanizer-detecting-ai-patterns/)
- [ProductiveShop: How to Avoid AI Writing Patterns](https://productiveshop.com/how-to-avoid-ai-writing-patterns/)

### Analyzed Corpus
- `src/blog/prompts.py` (weekly, thematic, reading list, social prompts)
- `src/intake/prompts.py` (daily intake, unified intake prompts)
- `src/journal/prompts.py` (4 journal styles)
- `src/blog/blog_memory.py` (BlogMemory, BlogPostSummary)
- `src/blog/context.py` (WeeklyBlogContext, ThematicBlogContext)
- 6 published weekly essays (W02 through W07)
- 1 published thematic essay (self-referential-loop)
- 3 intake digests (Feb 9, 13, 14)
- 5 journal entries (Feb 6, 9, 12, 14 and others)
