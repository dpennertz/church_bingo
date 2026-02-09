import json
import re
from collections import Counter

import anthropic

from config import Config

SYSTEM_PROMPT = """You are a helpful assistant that extracts meaningful words from \
church bulletins and service programs. These words will be used in a "Sermon BINGO" \
game where children listen for specific words during the church service.

Your task:
1. Read the bulletin text carefully.
2. Identify words that are likely to be SPOKEN during the church service.
3. Focus on:
   - Theological and biblical terms (grace, salvation, covenant, etc.)
   - Names of biblical figures mentioned in readings or sermon topics
   - Key theme words from the sermon title or scripture passages
   - Worship-related words (praise, glory, hallelujah, amen, etc.)
   - Seasonal or liturgical words if applicable (advent, lent, resurrection, etc.)
   - Specific place names or concepts from scripture readings listed
   - Words that children can recognize when they hear them
4. Exclude:
   - Common filler words (the, and, but, is, are, etc.)
   - Administrative words (page, number, please, visit, welcome, etc.)
   - Words too obscure for children to recognize
   - Proper names of church staff or committee members (unless biblical figures)
   - Very short words (1-2 letters)
   - Service structure labels and section headings — these are parts of the printed \
bulletin layout, NOT words spoken during the service. Exclude words like: hymn, hymns, \
sermon, prelude, postlude, offertory, benediction, doxology, litany, liturgy, \
invocation, processional, recessional, introit, anthem, interlude, meditation, \
responsive, unison, congregation, announcements, bulletin, reading, readings, \
testament, scripture, psalter, gloria, passing, greeting, assurance, confession, \
pardon, affirmation, creed, concerns, joys, dismissal, charge, choral, response

Return ONLY a JSON array of lowercase single words, no duplicates.
Aim for approximately {target_count} words but return between {min_count} and {max_count}.
Order them from most likely to be heard to least likely.

Example output format:
["grace", "salvation", "psalm", "covenant", "mercy", "faith", "shepherds", "kingdom"]"""

USER_PROMPT = """Extract meaningful church service words from this bulletin:

---
{bulletin_text}
---

Return a JSON array of approximately {target_count} words."""


# Service structure words that are section labels in bulletins, not spoken content.
# These get filtered out even if the AI returns them.
SERVICE_SECTION_WORDS = {
    "hymn", "hymns", "sermon", "prelude", "postlude", "offertory", "benediction",
    "doxology", "litany", "liturgy", "invocation", "processional", "recessional",
    "introit", "anthem", "interlude", "meditation", "responsive", "unison",
    "congregation", "announcements", "bulletin", "reading", "readings",
    "testament", "scripture", "psalter", "gloria", "passing", "greeting",
    "assurance", "confession", "pardon", "affirmation", "creed", "concerns",
    "joys", "dismissal", "charge", "choral", "response", "call", "worship",
    "opening", "closing", "prayer", "prayers", "old", "new",
}


def extract_words(bulletin_text, target_count=50):
    if not Config.ANTHROPIC_API_KEY or Config.ANTHROPIC_API_KEY == "your-api-key-here":
        raise ValueError(
            "Anthropic API key not configured. Please add your key to the .env file."
        )

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    min_count = max(20, target_count - 10)
    max_count = target_count + 15

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT.format(
            target_count=target_count,
            min_count=min_count,
            max_count=max_count,
        ),
        messages=[
            {
                "role": "user",
                "content": USER_PROMPT.format(
                    bulletin_text=bulletin_text[:8000],
                    target_count=target_count,
                ),
            }
        ],
    )

    response_text = message.content[0].text

    # Parse JSON from response, handling potential markdown code fences
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        words = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: try to extract quoted strings
        words = re.findall(r'"([a-zA-Z]{3,})"', response_text)
        if not words:
            raise ValueError(
                "Could not parse word list from AI response. Please try again or add words manually."
            )

    # Deduplicate, lowercase, and filter out service section words
    seen = set()
    unique = []
    for w in words:
        w_lower = w.strip().lower()
        if (w_lower and w_lower not in seen and len(w_lower) >= 3
                and w_lower not in SERVICE_SECTION_WORDS):
            seen.add(w_lower)
            unique.append(w_lower)

    return unique


def compute_word_frequencies(text, words):
    """Count how many times each word appears in the bulletin text.

    Uses case-insensitive whole-word matching so 'grace' matches 'Grace'
    but not 'disgrace'.
    """
    text_lower = text.lower()
    # Tokenize the text into words (letters and apostrophes only)
    tokens = re.findall(r"[a-z']+", text_lower)
    token_counts = Counter(tokens)

    frequencies = {}
    for word in words:
        w = word.lower()
        frequencies[w] = token_counts.get(w, 0)

    return frequencies
