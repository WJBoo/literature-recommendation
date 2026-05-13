from fastapi import APIRouter, Header, HTTPException, Query, Response

from app.schemas.accounts import (
    AccountActivityItemResponse,
    AccountAuthResponse,
    AccountDirectoryUserResponse,
    AccountExcerptSocialResponse,
    AccountExcerptStateResponse,
    AccountFeedbackRequest,
    AccountFeedbackResponse,
    AccountLibraryResponse,
    AccountLoginRequest,
    AccountReaderProfileResponse,
    AccountReadingProgressRequest,
    AccountReadingProgressResponse,
    AccountRegisterRequest,
    AccountUserResponse,
    FollowedAuthorResponse,
    MusicPlaylistCreateRequest,
    MusicPlaylistResponse,
    MusicPlaylistTrackRequest,
    MusicPreferenceRequest,
    MusicPreferenceResponse,
    MessageCreateRequest,
    MessageThreadResponse,
    PreferenceUpdateRequest,
    ProfileUpdateRequest,
    SavedExcerptSaveRequest,
    SavedFolderCreateRequest,
    SavedFolderResponse,
    PreferenceProfile,
    UserPostCreateRequest,
    UserPostResponse,
)
from app.schemas.interactions import (
    InteractionLogRequest,
    InteractionLogResponse,
    InteractionSummaryResponse,
)
from app.schemas.recommendations import (
    AuthorProfileResponse,
    ListeningRecommendationResponse,
    MusicCatalogResponse,
    PoemOfTheDayResponse,
    ReaderItemResponse,
    RecommendationRequest,
    RecommendationResponse,
    SearchResultResponse,
)
from app.services.accounts import (
    AccountConflictError,
    AccountNotFoundError,
    AccountService,
    AuthenticationError,
    ExcerptNotFoundError,
    MessagePermissionError,
    MessageRecipientNotFoundError,
    MessageThreadNotFoundError,
    MusicPlaylistNotFoundError,
    PostMediaError,
    PostNotFoundError,
    SavedFolderNotFoundError,
    SavedSelectionError,
)
from app.services.daily_features import DailyFeatureService
from app.services.interaction_logging import InteractionLoggingService
from app.services.recommendations import RecommendationService

api_router = APIRouter()
recommendation_service = RecommendationService()
interaction_logging_service = InteractionLoggingService()
account_service = AccountService()
daily_feature_service = DailyFeatureService()


@api_router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@api_router.post("/recommendations", response_model=RecommendationResponse)
async def recommendations(
    payload: RecommendationRequest, authorization: str | None = Header(default=None)
) -> RecommendationResponse:
    if not authorization:
        return await recommendation_service.recommend_async(payload)

    try:
        token = extract_bearer_token(authorization)
        account = account_service.get_user_for_token(token)
        followed_authors = [
            author.name for author in account_service.followed_authors(token)
        ]
        request = merge_recommendation_request(payload, account.preferences, followed_authors)
        return await recommendation_service.recommend_async(
            request,
            account_service.recommendation_context(token),
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/music/catalog", response_model=MusicCatalogResponse)
async def music_catalog(
    tones: list[str] = Query(default=[]),
    composers: list[str] = Query(default=[]),
) -> MusicCatalogResponse:
    return daily_feature_service.music_catalog(tones, composers)


@api_router.get("/poem-of-the-day", response_model=PoemOfTheDayResponse)
async def poem_of_the_day() -> PoemOfTheDayResponse:
    poem = daily_feature_service.poem_of_the_day()
    if poem is None:
        raise HTTPException(status_code=404, detail="No poem of the day is available.")
    return poem


@api_router.get(
    "/reader-items/{item_id}/listening",
    response_model=ListeningRecommendationResponse,
)
async def listening_recommendation(item_id: str) -> ListeningRecommendationResponse:
    recommendation = daily_feature_service.listening_for_item(item_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Reader item not found.")
    return recommendation


@api_router.get("/reader-items/{item_id}", response_model=ReaderItemResponse)
async def reader_item(item_id: str) -> ReaderItemResponse:
    item = recommendation_service.reader_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Reader item not found.")
    return item


@api_router.get("/authors/{author_id}", response_model=AuthorProfileResponse)
async def author_profile(
    author_id: str, authorization: str | None = Header(default=None)
) -> AuthorProfileResponse:
    followed_author_ids: set[str] = set()
    if authorization:
        try:
            followed_author_ids = account_service.followed_author_ids(
                extract_bearer_token(authorization)
            )
        except (AccountNotFoundError, AuthenticationError):
            followed_author_ids = set()
    profile = recommendation_service.author_profile(author_id, followed_author_ids)
    if profile is None:
        raise HTTPException(status_code=404, detail="Author not found.")
    return profile


@api_router.get("/search", response_model=SearchResultResponse)
async def search(query: str, limit: int = 12) -> SearchResultResponse:
    return recommendation_service.search(query, limit=max(1, min(limit, 24)))


@api_router.post("/interactions", response_model=InteractionLogResponse)
async def log_interaction(
    payload: InteractionLogRequest, authorization: str | None = Header(default=None)
) -> InteractionLogResponse:
    response = interaction_logging_service.log_event(payload)
    if authorization and payload.event_type in {"like", "dislike", "skip"}:
        target_id = payload.excerpt_id or payload.work_id
        try:
            if target_id:
                account_service.record_feedback(
                    extract_bearer_token(authorization),
                    AccountFeedbackRequest(event_type=payload.event_type, excerpt_id=target_id),
                )
        except (AccountNotFoundError, AuthenticationError, ExcerptNotFoundError):
            pass
    if authorization and payload.event_type in {"open", "read_start", "read_complete"}:
        target_id = payload.excerpt_id or payload.work_id
        try:
            if target_id:
                account_service.record_read_event(
                    extract_bearer_token(authorization),
                    target_id,
                    payload.event_type,
                )
        except (AccountNotFoundError, AuthenticationError, ExcerptNotFoundError):
            pass
    return response


@api_router.get("/interactions/summary", response_model=InteractionSummaryResponse)
async def interaction_summary() -> InteractionSummaryResponse:
    return interaction_logging_service.summarize()


@api_router.post("/accounts/register", response_model=AccountAuthResponse)
async def register_account(payload: AccountRegisterRequest) -> AccountAuthResponse:
    try:
        return account_service.register(payload)
    except AccountConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api_router.post("/accounts/login", response_model=AccountAuthResponse)
async def login_account(payload: AccountLoginRequest) -> AccountAuthResponse:
    try:
        return account_service.login(payload)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/accounts/me", response_model=AccountUserResponse)
async def current_account(authorization: str | None = Header(default=None)) -> AccountUserResponse:
    try:
        return account_service.get_user_for_token(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.put("/accounts/preferences", response_model=AccountUserResponse)
async def update_preferences(
    payload: PreferenceUpdateRequest, authorization: str | None = Header(default=None)
) -> AccountUserResponse:
    try:
        return account_service.update_preferences(
            extract_bearer_token(authorization), payload.preferences
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.put("/accounts/profile", response_model=AccountUserResponse)
async def update_profile(
    payload: ProfileUpdateRequest, authorization: str | None = Header(default=None)
) -> AccountUserResponse:
    try:
        return account_service.update_profile(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get(
    "/accounts/reading-progress",
    response_model=AccountReadingProgressResponse | None,
)
async def account_reading_progress(
    authorization: str | None = Header(default=None),
) -> AccountReadingProgressResponse | None:
    try:
        return account_service.reading_progress(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.put(
    "/accounts/reading-progress",
    response_model=AccountReadingProgressResponse,
)
async def update_account_reading_progress(
    payload: AccountReadingProgressRequest,
    authorization: str | None = Header(default=None),
) -> AccountReadingProgressResponse:
    try:
        return account_service.update_reading_progress(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get(
    "/accounts/music/preferences",
    response_model=MusicPreferenceResponse,
)
async def account_music_preferences(
    authorization: str | None = Header(default=None),
) -> MusicPreferenceResponse:
    try:
        return account_service.music_preferences(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.put(
    "/accounts/music/preferences",
    response_model=MusicPreferenceResponse,
)
async def update_account_music_preferences(
    payload: MusicPreferenceRequest,
    authorization: str | None = Header(default=None),
) -> MusicPreferenceResponse:
    try:
        return account_service.update_music_preferences(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/accounts/music/playlists", response_model=list[MusicPlaylistResponse])
async def account_music_playlists(
    authorization: str | None = Header(default=None),
) -> list[MusicPlaylistResponse]:
    try:
        return account_service.list_music_playlists(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post(
    "/accounts/music/playlists",
    response_model=MusicPlaylistResponse,
    status_code=201,
)
async def create_account_music_playlist(
    payload: MusicPlaylistCreateRequest,
    authorization: str | None = Header(default=None),
) -> MusicPlaylistResponse:
    try:
        return account_service.create_music_playlist(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.delete("/accounts/music/playlists/{playlist_id}", status_code=204)
async def delete_account_music_playlist(
    playlist_id: str,
    authorization: str | None = Header(default=None),
) -> Response:
    try:
        account_service.delete_music_playlist(extract_bearer_token(authorization), playlist_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except MusicPlaylistNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@api_router.post(
    "/accounts/music/playlists/{playlist_id}/tracks",
    response_model=MusicPlaylistResponse,
)
async def add_account_music_playlist_track(
    playlist_id: str,
    payload: MusicPlaylistTrackRequest,
    authorization: str | None = Header(default=None),
) -> MusicPlaylistResponse:
    try:
        return account_service.add_music_playlist_track(
            extract_bearer_token(authorization), playlist_id, payload
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except MusicPlaylistNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.delete(
    "/accounts/music/playlists/{playlist_id}/tracks/{track_id}",
    response_model=MusicPlaylistResponse,
)
async def remove_account_music_playlist_track(
    playlist_id: str,
    track_id: str,
    authorization: str | None = Header(default=None),
) -> MusicPlaylistResponse:
    try:
        return account_service.remove_music_playlist_track(
            extract_bearer_token(authorization), playlist_id, track_id
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except MusicPlaylistNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/accounts/posts", response_model=list[UserPostResponse])
async def account_posts(authorization: str | None = Header(default=None)) -> list[UserPostResponse]:
    try:
        return account_service.list_posts(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post("/accounts/posts", response_model=UserPostResponse, status_code=201)
async def create_account_post(
    payload: UserPostCreateRequest, authorization: str | None = Header(default=None)
) -> UserPostResponse:
    try:
        return account_service.create_post(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PostMediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.put("/accounts/posts/{post_id}", response_model=UserPostResponse)
async def update_account_post(
    post_id: str,
    payload: UserPostCreateRequest,
    authorization: str | None = Header(default=None),
) -> UserPostResponse:
    try:
        return account_service.update_post(extract_bearer_token(authorization), post_id, payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PostMediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.delete("/accounts/posts/{post_id}", status_code=204)
async def delete_account_post(
    post_id: str, authorization: str | None = Header(default=None)
) -> Response:
    try:
        account_service.delete_post(extract_bearer_token(authorization), post_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except PostNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@api_router.get("/accounts/directory", response_model=list[AccountDirectoryUserResponse])
async def account_directory(
    authorization: str | None = Header(default=None),
) -> list[AccountDirectoryUserResponse]:
    try:
        return account_service.directory(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/accounts/directory/{user_id}", response_model=AccountReaderProfileResponse)
async def account_reader_profile(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> AccountReaderProfileResponse:
    try:
        return account_service.reader_profile(extract_bearer_token(authorization), user_id)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/accounts/followed-users/activity", response_model=list[AccountActivityItemResponse])
async def followed_user_activity(
    authorization: str | None = Header(default=None),
) -> list[AccountActivityItemResponse]:
    try:
        return account_service.followed_user_activity(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post("/accounts/followed-users/{user_id}", response_model=list[AccountDirectoryUserResponse])
async def follow_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> list[AccountDirectoryUserResponse]:
    try:
        return account_service.follow_user(extract_bearer_token(authorization), user_id)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.delete("/accounts/followed-users/{user_id}", response_model=list[AccountDirectoryUserResponse])
async def unfollow_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> list[AccountDirectoryUserResponse]:
    try:
        return account_service.unfollow_user(extract_bearer_token(authorization), user_id)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get("/accounts/messages", response_model=list[MessageThreadResponse])
async def message_threads(
    authorization: str | None = Header(default=None),
) -> list[MessageThreadResponse]:
    try:
        return account_service.list_message_threads(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post("/accounts/messages", response_model=MessageThreadResponse, status_code=201)
async def send_message(
    payload: MessageCreateRequest, authorization: str | None = Header(default=None)
) -> MessageThreadResponse:
    try:
        return account_service.send_message(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except (MessageRecipientNotFoundError, MessageThreadNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MessagePermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@api_router.get("/accounts/saved-folders", response_model=list[SavedFolderResponse])
async def saved_folders(authorization: str | None = Header(default=None)) -> list[SavedFolderResponse]:
    try:
        return account_service.list_saved_folders(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/accounts/library", response_model=AccountLibraryResponse)
async def account_library(authorization: str | None = Header(default=None)) -> AccountLibraryResponse:
    try:
        return account_service.library(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get("/accounts/followed-authors", response_model=list[FollowedAuthorResponse])
async def followed_authors(
    authorization: str | None = Header(default=None),
) -> list[FollowedAuthorResponse]:
    try:
        return account_service.followed_authors(extract_bearer_token(authorization))
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post(
    "/accounts/followed-authors/{author_id}",
    response_model=FollowedAuthorResponse,
    status_code=201,
)
async def follow_author(
    author_id: str, authorization: str | None = Header(default=None)
) -> FollowedAuthorResponse:
    try:
        return account_service.follow_author(extract_bearer_token(authorization), author_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.delete(
    "/accounts/followed-authors/{author_id}",
    response_model=list[FollowedAuthorResponse],
)
async def unfollow_author(
    author_id: str, authorization: str | None = Header(default=None)
) -> list[FollowedAuthorResponse]:
    try:
        return account_service.unfollow_author(extract_bearer_token(authorization), author_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.get(
    "/accounts/excerpts/{excerpt_id}/state",
    response_model=AccountExcerptStateResponse,
)
async def account_excerpt_state(
    excerpt_id: str, authorization: str | None = Header(default=None)
) -> AccountExcerptStateResponse:
    try:
        return account_service.excerpt_state(extract_bearer_token(authorization), excerpt_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.get(
    "/accounts/excerpts/{excerpt_id}/social",
    response_model=AccountExcerptSocialResponse,
)
async def account_excerpt_social(
    excerpt_id: str, authorization: str | None = Header(default=None)
) -> AccountExcerptSocialResponse:
    try:
        token = extract_bearer_token(authorization) if authorization else None
        return account_service.excerpt_social_context(token, excerpt_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/accounts/saved-folders", response_model=SavedFolderResponse, status_code=201)
async def create_saved_folder(
    payload: SavedFolderCreateRequest, authorization: str | None = Header(default=None)
) -> SavedFolderResponse:
    try:
        return account_service.create_saved_folder(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@api_router.post(
    "/accounts/saved-folders/{folder_id}/items",
    response_model=SavedFolderResponse,
)
async def save_excerpt_to_folder(
    folder_id: str,
    payload: SavedExcerptSaveRequest,
    authorization: str | None = Header(default=None),
) -> SavedFolderResponse:
    try:
        return account_service.save_excerpt(extract_bearer_token(authorization), folder_id, payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SavedFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SavedSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.delete(
    "/accounts/excerpts/{excerpt_id}/saved",
    response_model=AccountExcerptStateResponse,
)
async def remove_saved_excerpt_everywhere(
    excerpt_id: str, authorization: str | None = Header(default=None)
) -> AccountExcerptStateResponse:
    try:
        return account_service.remove_saved_excerpt_everywhere(
            extract_bearer_token(authorization), excerpt_id
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.delete(
    "/accounts/saved-folders/{folder_id}/items/{excerpt_id}",
    response_model=SavedFolderResponse,
)
async def remove_saved_excerpt(
    folder_id: str,
    excerpt_id: str,
    authorization: str | None = Header(default=None),
) -> SavedFolderResponse:
    try:
        return account_service.remove_saved_excerpt(
            extract_bearer_token(authorization), folder_id, excerpt_id
        )
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SavedFolderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.post("/accounts/feedback", response_model=AccountFeedbackResponse)
async def record_account_feedback(
    payload: AccountFeedbackRequest, authorization: str | None = Header(default=None)
) -> AccountFeedbackResponse:
    try:
        return account_service.record_feedback(extract_bearer_token(authorization), payload)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api_router.delete(
    "/accounts/feedback/{excerpt_id}",
    response_model=AccountExcerptStateResponse,
)
async def clear_account_feedback(
    excerpt_id: str, authorization: str | None = Header(default=None)
) -> AccountExcerptStateResponse:
    try:
        return account_service.clear_feedback(extract_bearer_token(authorization), excerpt_id)
    except (AccountNotFoundError, AuthenticationError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ExcerptNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Missing authorization token.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Invalid authorization token.")
    return token


def merge_recommendation_request(
    payload: RecommendationRequest,
    preferences: PreferenceProfile,
    followed_authors: list[str] | None = None,
) -> RecommendationRequest:
    return RecommendationRequest(
        user_id=payload.user_id,
        genres=merge_unique(payload.genres, preferences.genres),
        themes=merge_unique(payload.themes, preferences.themes),
        moods=merge_unique(payload.moods, preferences.moods),
        forms=merge_unique(payload.forms, preferences.forms),
        authors=merge_unique(payload.authors, [*preferences.authors, *(followed_authors or [])]),
        books=merge_unique(payload.books, preferences.books),
        limit=payload.limit,
    )


def merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*first, *second]:
        normalized = " ".join(value.strip().split())
        key = normalized.lower()
        if normalized and key not in seen:
            merged.append(normalized)
            seen.add(key)
    return merged
