"""Tests for Mermaid diagram extraction and validation."""

from session_insights.blog.diagrams import (
    clean_diagrams,
    extract_mermaid_blocks,
    validate_mermaid,
)


class TestExtractMermaidBlocks:
    def test_extracts_single_block(self):
        prose = """\
Some text before.

```mermaid
graph TD
    A --> B
```

Some text after.
"""
        blocks = extract_mermaid_blocks(prose)
        assert len(blocks) == 1
        assert "graph TD" in blocks[0]

    def test_extracts_multiple_blocks(self):
        prose = """\
```mermaid
graph TD
    A --> B
```

Middle text.

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        blocks = extract_mermaid_blocks(prose)
        assert len(blocks) == 2
        assert "graph TD" in blocks[0]
        assert "sequenceDiagram" in blocks[1]

    def test_no_blocks(self):
        prose = "Just regular text with no diagrams."
        assert extract_mermaid_blocks(prose) == []

    def test_ignores_non_mermaid_code_blocks(self):
        prose = """\
```python
print("hello")
```

```mermaid
pie title Pets
    "Dogs" : 386
    "Cats" : 85
```
"""
        blocks = extract_mermaid_blocks(prose)
        assert len(blocks) == 1
        assert "pie" in blocks[0]


class TestValidateMermaid:
    def test_valid_graph(self):
        assert validate_mermaid("graph TD\n    A --> B")

    def test_valid_flowchart(self):
        assert validate_mermaid("flowchart LR\n    A --> B")

    def test_valid_sequence_diagram(self):
        assert validate_mermaid("sequenceDiagram\n    Alice->>Bob: Hello")

    def test_valid_gantt(self):
        assert validate_mermaid("gantt\n    title A Gantt Diagram")

    def test_valid_pie(self):
        assert validate_mermaid('pie title Pets\n    "Dogs" : 386')

    def test_valid_timeline(self):
        assert validate_mermaid("timeline\n    title History")

    def test_valid_mindmap(self):
        assert validate_mermaid("mindmap\n  root((mindmap))")

    def test_invalid_empty(self):
        assert not validate_mermaid("")

    def test_invalid_random_text(self):
        assert not validate_mermaid("This is not a diagram\nJust text")

    def test_whitespace_only(self):
        assert not validate_mermaid("   \n   ")


class TestCleanDiagrams:
    def test_keeps_valid_blocks(self):
        prose = """\
Text before.

```mermaid
graph TD
    A --> B
```

Text after."""

        result = clean_diagrams(prose)
        assert "```mermaid" in result
        assert "graph TD" in result
        assert "Text before." in result
        assert "Text after." in result

    def test_removes_invalid_blocks(self):
        prose = """\
Text before.

```mermaid
This is not valid mermaid content
at all.
```

Text after."""

        result = clean_diagrams(prose)
        assert "```mermaid" not in result
        assert "not valid" not in result
        assert "Text before." in result
        assert "Text after." in result

    def test_mixed_valid_and_invalid(self):
        prose = """\
```mermaid
graph TD
    A --> B
```

Middle.

```mermaid
Invalid stuff here
```

End."""

        result = clean_diagrams(prose)
        assert result.count("```mermaid") == 1
        assert "graph TD" in result
        assert "Invalid stuff" not in result

    def test_cleans_extra_blank_lines(self):
        prose = """\
Before.

```mermaid
bad diagram here
```

After."""

        result = clean_diagrams(prose)
        assert "\n\n\n" not in result
