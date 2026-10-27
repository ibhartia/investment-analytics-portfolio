---
name: analyze-earnings-sentiment
description: >
  Analyze earnings call transcripts for investor sentiment. Use when the user asks
  to "analyze an earnings call", "score sentiment on this transcript", "rate management
  tone", "assess investor sentiment", "evaluate this earnings transcript", or provides
  an earnings call transcript file for sentiment analysis.
metadata:
  version: "0.1.0"
---

# Earnings Call Sentiment Analyzer

Analyze earnings call transcripts and produce quantified investor sentiment scores across six key dimensions. Read the detailed scoring rubric from `references/scoring-rubric.md` before beginning analysis.

## Process

1. **Identify transcript structure.** Locate the prepared remarks section and the Q&A section. Note the speakers (CEO, CFO, analysts, etc.).

2. **Read the scoring rubric.** Load `references/scoring-rubric.md` for the detailed criteria for each sentiment dimension.

3. **Analyze each dimension.** Score every dimension on a scale from **-5** (very negative) to **+5** (very positive), using the rubric criteria. Each score must include a 1-2 sentence justification citing specific language or patterns from the transcript.

4. **Compute composite score.** Calculate a weighted average:
   - Management Tone: 20%
   - Forward Guidance: 25%
   - Risk Language: 15%
   - Analyst Sentiment: 20%
   - Financial Health Signals: 10%
   - Strategic Clarity: 10%

5. **Produce the scorecard.** Format results as a structured table followed by a brief narrative summary.

## Sentiment Dimensions

| Dimension | What to Evaluate |
|-----------|-----------------|
| Management Tone | Confidence vs. defensiveness; clarity vs. evasiveness; energy and conviction |
| Forward Guidance | Strength of outlook statements; specificity of projections; qualifier frequency |
| Risk Language | Frequency and severity of hedging, uncertainty, and risk mentions |
| Analyst Sentiment | Tone of analyst questions; skepticism vs. support; follow-up aggressiveness |
| Financial Health Signals | Language around revenue, margins, cash flow, debt; growth vs. contraction framing |
| Strategic Clarity | Coherence of strategy narrative; specificity of initiatives; alignment of priorities |

## Output Format

Present the analysis in this structure:

### Scorecard Header
- Company name and ticker (if identifiable)
- Quarter and fiscal year
- Date of call (if available)

### Sentiment Scores Table
| Dimension | Score (-5 to +5) | Weight | Weighted Score | Key Evidence |
|-----------|-------------------|--------|----------------|--------------|
| (each row) | | | | (brief quote or pattern) |
| **Composite** | | | **(weighted avg)** | |

### Narrative Summary
Write 3-5 sentences synthesizing the overall sentiment picture: what stands out, what changed from typical patterns, and what to watch.

### Notable Signals
Flag any specific phrases or exchanges that are particularly bullish or bearish, with brief context.

## Guidelines

- Be objective. Anchor scores to specific language, not general impressions.
- Treat hedging phrases ("we believe", "we expect") as mildly positive unless contradicted by context.
- Strong qualifiers ("significantly", "dramatically", "unprecedented") shift scores more than mild ones.
- Analyst interruptions, repeated follow-ups, or skeptical restatements indicate negative analyst sentiment.
- If the transcript only contains prepared remarks (no Q&A), note this and score Analyst Sentiment as N/A.
- When multiple transcripts are provided, produce a comparison table showing scores side by side.
