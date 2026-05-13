from __future__ import annotations

from app.schemas.recommendations import RecommendationRequest


def build_preference_profile_text(request: RecommendationRequest) -> str:
    parts = ["Personalized literature taste profile."]
    if request.genres:
        parts.append(f"Preferred genres: {', '.join(request.genres)}.")
    if request.forms:
        parts.append(f"Preferred literary forms: {', '.join(request.forms)}.")
    if request.themes:
        parts.append(f"Preferred themes: {', '.join(request.themes)}.")
    if request.moods:
        parts.append(f"Preferred moods and tones: {', '.join(request.moods)}.")
    if request.authors:
        parts.append(f"Preferred authors: {', '.join(request.authors)}.")
    if request.books:
        parts.append(f"Preferred books or works: {', '.join(request.books)}.")
    if len(parts) == 1:
        parts.append("Recommend varied classic literature with clear excerpts.")
    return " ".join(parts)
