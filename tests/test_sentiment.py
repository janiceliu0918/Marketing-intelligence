"""Unit tests for sentiment analysis utilities."""
from wine_agent.processors.sentiment import (
    score_tasting_note, aggregate_critic_scores, normalise_critic_name, extract_top_keywords,
)
from wine_agent.models.wine import CriticScore


def test_positive_note():
    note = "An elegant and complex wine with a long, refined finish and silky tannins."
    score = score_tasting_note(note)
    assert score > 0


def test_negative_note():
    note = "Thin and flat with a short, bitter finish. Quite harsh on the palate."
    score = score_tasting_note(note)
    assert score < 0


def test_neutral_note():
    note = "The wine has red fruits and some oak on the nose."
    score = score_tasting_note(note)
    # No strong positive/negative words — score may be 0 or near 0
    assert -0.5 <= score <= 0.5


def test_critic_name_normalisation():
    assert normalise_critic_name("WA") == "Wine Advocate"
    assert normalise_critic_name("ws") == "Wine Spectator"
    assert normalise_critic_name("JR") == "Jancis Robinson"
    assert normalise_critic_name("Unknown Critic") == "Unknown Critic"


def test_aggregate_scores():
    scores = [
        CriticScore(critic="Wine Advocate", score=93),
        CriticScore(critic="Wine Spectator", score=91),
        CriticScore(critic="Jancis Robinson", score=17.5, score_max=20),
    ]
    # Only numeric 100-pt scores included
    result = aggregate_critic_scores([
        CriticScore(critic="Wine Advocate", score=93),
        CriticScore(critic="Wine Spectator", score=91),
    ])
    assert result["average"] == 92.0
    assert result["count"] == 2
    assert result["consensus"] == "Excellent"


def test_aggregate_no_scores():
    result = aggregate_critic_scores([])
    assert result["count"] == 0
    assert result["consensus"] == "No data"


def test_extract_keywords():
    texts = [
        "This wine has beautiful dark fruit and excellent structure.",
        "Excellent tannins and beautiful length on the palate.",
    ]
    kws = extract_top_keywords(texts, top_n=3)
    assert "excellent" in kws or "beautiful" in kws
