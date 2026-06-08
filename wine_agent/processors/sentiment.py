"""Sentiment analysis and review aggregation utilities."""
import re
import logging
from collections import Counter
from typing import Optional
from wine_agent.models.wine import ConsumerSentiment, CriticScore

logger = logging.getLogger(__name__)

# Critic name normalisation map
_CRITIC_ALIASES: dict[str, str] = {
    "wa": "Wine Advocate", "rp": "Wine Advocate", "robert parker": "Wine Advocate",
    "wine advocate": "Wine Advocate",
    "ws": "Wine Spectator", "wine spectator": "Wine Spectator",
    "jr": "Jancis Robinson", "jancis robinson": "Jancis Robinson",
    "js": "James Suckling", "james suckling": "James Suckling",
    "vinous": "Vinous", "antonio galloni": "Vinous",
    "decanter": "Decanter",
    "bh": "Burghound", "allen meadows": "Burghound",
}

# Positive/negative sentiment word lists for simple keyword scoring
_POS_WORDS = {
    "excellent", "outstanding", "exceptional", "great", "brilliant", "superb",
    "elegant", "complex", "refined", "smooth", "velvety", "balanced", "long",
    "beautiful", "impressive", "concentrated", "deep", "luscious", "silky",
    "profound", "benchmark", "classic", "best",
}
_NEG_WORDS = {
    "thin", "light", "simple", "short", "harsh", "tannic", "bitter",
    "overpriced", "flat", "disappointing", "mediocre", "average", "rough",
    "acidic", "astringent", "coarse",
}


def normalise_critic_name(raw: str) -> str:
    return _CRITIC_ALIASES.get(raw.lower().strip(), raw.strip())


def score_tasting_note(note: str) -> float:
    """Return a -1…1 sentiment score from a tasting note using keyword counting."""
    words = re.findall(r"\w+", note.lower())
    pos = sum(1 for w in words if w in _POS_WORDS)
    neg = sum(1 for w in words if w in _NEG_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def aggregate_critic_scores(scores: list[CriticScore]) -> dict:
    """Return summary statistics across all critic scores."""
    numeric = [cs.score for cs in scores if cs.score is not None]
    if not numeric:
        return {"average": None, "min": None, "max": None, "count": 0, "consensus": "No data"}

    avg = sum(numeric) / len(numeric)
    consensus = _score_to_consensus(avg)

    return {
        "average": round(avg, 1),
        "min": min(numeric),
        "max": max(numeric),
        "count": len(numeric),
        "consensus": consensus,
        "by_critic": {cs.critic: cs.score for cs in scores if cs.score is not None},
    }


def _score_to_consensus(avg: float) -> str:
    if avg >= 96:
        return "Iconic / Perfect"
    if avg >= 93:
        return "Outstanding"
    if avg >= 90:
        return "Excellent"
    if avg >= 87:
        return "Very Good"
    if avg >= 83:
        return "Good"
    return "Average / Below Average"


def extract_top_keywords(texts: list[str], top_n: int = 10) -> list[str]:
    """Extract the most frequent meaningful words from a list of review texts."""
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "is", "are", "was", "were", "be", "been", "this", "that",
        "it", "as", "by", "from", "wine", "vintage", "bottle", "glass",
    }
    words = []
    for text in texts:
        tokens = re.findall(r"\b[a-z]{4,}\b", text.lower())
        words.extend(t for t in tokens if t not in stop_words)

    counter = Counter(words)
    return [word for word, _ in counter.most_common(top_n)]


def build_sentiment_summary(sentiment: Optional[ConsumerSentiment]) -> str:
    """Return a short human-readable summary of consumer sentiment."""
    if sentiment is None:
        return "No consumer data available."

    lines = []
    if sentiment.average_rating:
        stars = "★" * round(sentiment.average_rating) + "☆" * (5 - round(sentiment.average_rating))
        lines.append(f"Vivino: {sentiment.average_rating:.1f}/5 {stars} ({sentiment.rating_count:,} ratings)")

    if sentiment.flavour_tags:
        lines.append(f"Top flavours: {', '.join(sentiment.flavour_tags[:6])}")

    if sentiment.positive_keywords:
        lines.append(f"Praised for: {', '.join(sentiment.positive_keywords[:5])}")

    if sentiment.negative_keywords:
        lines.append(f"Concerns: {', '.join(sentiment.negative_keywords[:3])}")

    return "\n".join(lines) if lines else "Limited consumer data."
