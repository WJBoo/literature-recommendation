from __future__ import annotations

from datetime import UTC, datetime
from hashlib import pbkdf2_hmac, sha1
import hmac
import json
from pathlib import Path
import re
import secrets
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.accounts import (
    AccountActivityItemResponse,
    AccountAuthResponse,
    AccountDirectoryUserResponse,
    AccountExcerptSocialResponse,
    AccountExcerptStateResponse,
    AccountFeedbackEventType,
    AccountFeedbackRequest,
    AccountFeedbackResponse,
    AccountLibraryResponse,
    AccountLoginRequest,
    AccountPublicAnnotationResponse,
    AccountReaderProfileResponse,
    AccountReadingProgressRequest,
    AccountReadingProgressResponse,
    AccountRegisterRequest,
    AccountSocialUserResponse,
    AccountUserResponse,
    MusicPlaylistCreateRequest,
    MusicPlaylistResponse,
    MusicPlaylistTrackRequest,
    MusicPreferenceRequest,
    MusicPreferenceResponse,
    FollowedAuthorResponse,
    MessageCreateRequest,
    MessageParticipantResponse,
    MessageResponse,
    MessageThreadResponse,
    PreferenceProfile,
    ProfileUpdateRequest,
    SavedExcerptResponse,
    SavedExcerptSaveRequest,
    SavedFolderCreateRequest,
    SavedFolderResponse,
    UserPostCreateRequest,
    UserPostMediaResponse,
    UserPostResponse,
)
from app.schemas.recommendations import RecommendationFeedbackContext
from app.services.processed_corpus import (
    ProcessedCorpusService,
    ProcessedExcerpt,
    clear_processed_corpus_cache,
)
from app.services.storage import (
    ObjectStorageService,
    StorageConfigurationError,
    StorageUploadError,
    is_renderable_media_reference,
)


PASSWORD_ITERATIONS = 210_000
DEFAULT_SAVED_FOLDERS = (
    ("read-later", "Read Later", "Excerpts to return to soon."),
    ("annotations", "Annotations", "Highlighted passages with reader notes."),
    ("favorites", "Favorites", "Excerpts worth keeping close."),
    ("poetry", "Poetry", "Poems and poetic fragments."),
)


class AccountConflictError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class SavedFolderNotFoundError(Exception):
    pass


class ExcerptNotFoundError(Exception):
    pass


class SavedSelectionError(Exception):
    pass


class MessageRecipientNotFoundError(Exception):
    pass


class MessagePermissionError(Exception):
    pass


class MessageThreadNotFoundError(Exception):
    pass


class PostMediaError(Exception):
    pass


class PostNotFoundError(Exception):
    pass


class MusicPlaylistNotFoundError(Exception):
    pass


class AccountService:
    """File-backed prototype account store.

    The SQL tables are already modeled for the durable database path. This store
    gives the local app working accounts while Postgres is unavailable here.
    """

    def __init__(
        self,
        store_path: Path | None = None,
        corpus_service: ProcessedCorpusService | None = None,
        media_storage: ObjectStorageService | None = None,
    ) -> None:
        self.store_path = store_path or settings.account_store_path or settings.processed_data_dir / "accounts.json"
        self.corpus_service = corpus_service or ProcessedCorpusService()
        self.media_storage = media_storage or ObjectStorageService()

    def register(self, request: AccountRegisterRequest) -> AccountAuthResponse:
        store = self._read_store()
        email = normalize_email(request.email)
        if email in store["users_by_email"]:
            raise AccountConflictError("An account with that email already exists.")

        now = datetime.now(UTC).isoformat()
        user_id = f"user-{uuid4()}"
        token = secrets.token_urlsafe(32)
        user_record = {
            "id": user_id,
            "email": email,
            "display_name": request.display_name.strip(),
            "password_hash": hash_password(request.password),
            "preferences": clean_preferences(request.preferences).model_dump(),
            "profile_metadata": default_profile_metadata(),
            "followed_authors": {},
            "followed_users": {},
            "saved_folders": default_saved_folders(now),
            "feedback": default_feedback(),
            "reading_progress": None,
            "music_preferences": default_music_preferences(now),
            "music_playlists": {},
            "created_at": now,
            "updated_at": now,
        }
        store["users"][user_id] = user_record
        store["users_by_email"][email] = user_id
        store["sessions"][token] = {"user_id": user_id, "created_at": now}
        self._write_store(store)
        return AccountAuthResponse(token=token, user=to_user_response(user_record))

    def login(self, request: AccountLoginRequest) -> AccountAuthResponse:
        store = self._read_store()
        email = normalize_email(request.email)
        user_id = store["users_by_email"].get(email)
        if user_id is None:
            raise AuthenticationError("Invalid email or password.")

        user_record = store["users"][user_id]
        if not verify_password(request.password, user_record["password_hash"]):
            raise AuthenticationError("Invalid email or password.")

        token = secrets.token_urlsafe(32)
        store["sessions"][token] = {
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._write_store(store)
        return AccountAuthResponse(token=token, user=to_user_response(user_record))

    def get_user_for_token(self, token: str) -> AccountUserResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        return to_user_response(user_record)

    def update_preferences(self, token: str, preferences: PreferenceProfile) -> AccountUserResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        user_record["preferences"] = clean_preferences(preferences).model_dump()
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        return to_user_response(user_record)

    def update_profile(self, token: str, request: ProfileUpdateRequest) -> AccountUserResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        if request.display_name is not None:
            user_record["display_name"] = clean_display_name(request.display_name)
        profile_metadata = user_record.setdefault("profile_metadata", default_profile_metadata())
        if request.bio is not None:
            profile_metadata["bio"] = clean_bio(request.bio)
        if request.avatar_data_url is not None:
            profile_metadata["avatar_data_url"] = self._store_avatar_reference(
                user_record["id"],
                request.avatar_data_url,
            )
        if request.account_visibility is not None:
            profile_metadata["account_visibility"] = request.account_visibility
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        return to_user_response(user_record)

    def reading_progress(self, token: str) -> AccountReadingProgressResponse | None:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        progress = user_record.get("reading_progress")
        return to_reading_progress_response(progress) if isinstance(progress, dict) else None

    def update_reading_progress(
        self, token: str, request: AccountReadingProgressRequest
    ) -> AccountReadingProgressResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(request.id)
        now = datetime.now(UTC).isoformat()
        progress = {
            "id": excerpt.id,
            "work_id": excerpt.work_id,
            "title": clean_optional_string(request.title) or excerpt.work_title or excerpt.title,
            "author": clean_optional_string(request.author) or excerpt.author,
            "form": clean_optional_string(request.form) or excerpt.form,
            "work_title": clean_optional_string(request.work_title) or getattr(excerpt, "work_title", None),
            "section_title": clean_optional_string(request.section_title)
            or getattr(excerpt, "section_title", None),
            "excerpt_label": clean_optional_string(request.excerpt_label)
            or getattr(excerpt, "excerpt_label", None),
            "saved_at": now,
        }
        user_record["reading_progress"] = progress
        user_record["updated_at"] = now
        self._write_store(store)
        return to_reading_progress_response(progress)

    def music_preferences(self, token: str) -> MusicPreferenceResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        return to_music_preference_response(user_record.get("music_preferences"))

    def update_music_preferences(
        self, token: str, request: MusicPreferenceRequest
    ) -> MusicPreferenceResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        now = datetime.now(UTC).isoformat()
        preferences = {
            "tones": clean_music_preference_values(request.tones),
            "composers": clean_music_preference_values(request.composers),
            "updated_at": now,
        }
        user_record["music_preferences"] = preferences
        user_record["updated_at"] = now
        self._write_store(store)
        return to_music_preference_response(preferences)

    def list_music_playlists(self, token: str) -> list[MusicPlaylistResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        playlists = user_record.setdefault("music_playlists", {})
        return [
            to_music_playlist_response(playlist)
            for playlist in sorted(
                playlists.values(),
                key=lambda candidate: candidate.get("updated_at", candidate.get("created_at", "")),
                reverse=True,
            )
        ]

    def create_music_playlist(
        self, token: str, request: MusicPlaylistCreateRequest
    ) -> MusicPlaylistResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        now = datetime.now(UTC).isoformat()
        playlists = user_record.setdefault("music_playlists", {})
        playlist_id = unique_playlist_id(request.name, playlists)
        playlist = {
            "id": playlist_id,
            "name": clean_playlist_name(request.name),
            "description": clean_optional_string(request.description) or "",
            "created_at": now,
            "updated_at": now,
            "tracks": {},
        }
        playlists[playlist_id] = playlist
        user_record["updated_at"] = now
        self._write_store(store)
        return to_music_playlist_response(playlist)

    def delete_music_playlist(self, token: str, playlist_id: str) -> None:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        playlists = user_record.setdefault("music_playlists", {})
        if playlist_id not in playlists:
            raise MusicPlaylistNotFoundError("Playlist not found.")
        playlists.pop(playlist_id, None)
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)

    def add_music_playlist_track(
        self, token: str, playlist_id: str, request: MusicPlaylistTrackRequest
    ) -> MusicPlaylistResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        playlist = self._music_playlist_for_user(user_record, playlist_id)
        now = datetime.now(UTC).isoformat()
        track = clean_music_track(request, now)
        playlist.setdefault("tracks", {})[track["id"]] = track
        playlist["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return to_music_playlist_response(playlist)

    def remove_music_playlist_track(
        self, token: str, playlist_id: str, track_id: str
    ) -> MusicPlaylistResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        playlist = self._music_playlist_for_user(user_record, playlist_id)
        playlist.setdefault("tracks", {}).pop(track_id, None)
        now = datetime.now(UTC).isoformat()
        playlist["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return to_music_playlist_response(playlist)

    def list_saved_folders(self, token: str) -> list[SavedFolderResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        return [
            self._folder_response(folder)
            for folder in sorted(
                user_record["saved_folders"].values(),
                key=lambda candidate: candidate["created_at"],
            )
        ]

    def library(self, token: str) -> AccountLibraryResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpts = self.corpus_service.list_excerpts()
        excerpts_by_id = {excerpt.id: excerpt for excerpt in excerpts}
        excerpts_by_work_id: dict[str, list[ProcessedExcerpt]] = {}
        for excerpt in excerpts:
            excerpts_by_work_id.setdefault(excerpt.work_id, []).append(excerpt)

        saved: list[SavedExcerptResponse] = []
        annotations: list[SavedExcerptResponse] = []
        for folder in user_record["saved_folders"].values():
            for item in folder.get("items", {}).values():
                response = to_saved_excerpt_response(item, excerpts_by_id, excerpts_by_work_id)
                if response.saved_kind == "selection":
                    annotations.append(response)
                else:
                    saved.append(response)

        saved.sort(key=lambda item: item.created_at, reverse=True)
        annotations.sort(key=lambda item: item.created_at, reverse=True)

        liked = [
            to_feedback_excerpt_response(excerpts_by_id[excerpt_id], user_record)
            for excerpt_id in reversed(user_record["feedback"].get("liked", []))
            if excerpt_id in excerpts_by_id
        ]
        return AccountLibraryResponse(saved=saved, annotations=annotations, liked=liked)

    def followed_authors(self, token: str) -> list[FollowedAuthorResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        return followed_author_responses(user_record)

    def followed_author_ids(self, token: str) -> set[str]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        return set(user_record.get("followed_authors", {}).keys())

    def follow_author(self, token: str, author_id: str) -> FollowedAuthorResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        author_name = self.corpus_service.find_author_name(author_id)
        if author_name is None:
            raise ExcerptNotFoundError("Author not found.")
        now = datetime.now(UTC).isoformat()
        user_record.setdefault("followed_authors", {})[author_id] = {
            "id": author_id,
            "name": author_name,
            "followed_at": now,
        }
        user_record["updated_at"] = now
        self._write_store(store)
        return FollowedAuthorResponse(
            id=author_id,
            name=author_name,
            followed_at=datetime.fromisoformat(now),
        )

    def unfollow_author(self, token: str, author_id: str) -> list[FollowedAuthorResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        user_record.setdefault("followed_authors", {}).pop(author_id, None)
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        return followed_author_responses(user_record)

    def list_posts(self, token: str) -> list[UserPostResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        posts = [
            post
            for post in store["posts"].values()
            if post["author_user_id"] == user_record["id"]
        ]
        posts.sort(key=lambda candidate: candidate["created_at"], reverse=True)
        return [to_user_post_response(post, user_record) for post in posts]

    def create_post(self, token: str, request: UserPostCreateRequest) -> UserPostResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        now = datetime.now(UTC).isoformat()
        body = clean_post_body(request.body)
        post_id = f"post-{uuid4()}"
        post = {
            "id": post_id,
            "author_user_id": user_record["id"],
            "title": clean_post_title(request.title),
            "body": body,
            "form": clean_post_form(request.form),
            "visibility": clean_post_visibility(request.visibility),
            "word_count": count_words(body),
            "media": self._clean_post_media_for_storage(
                request.media,
                user_id=user_record["id"],
                post_id=post_id,
            ),
            "created_at": now,
            "updated_at": now,
        }
        store["posts"][post["id"]] = post
        user_record["updated_at"] = now
        self._write_store(store)
        clear_processed_corpus_cache()
        return to_user_post_response(post, user_record)

    def update_post(
        self, token: str, post_id: str, request: UserPostCreateRequest
    ) -> UserPostResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        post = store.get("posts", {}).get(post_id)
        if post is None or post.get("author_user_id") != user_record["id"]:
            raise PostNotFoundError("Post not found.")

        body = clean_post_body(request.body)
        now = datetime.now(UTC).isoformat()
        post["title"] = clean_post_title(request.title)
        post["body"] = body
        post["form"] = clean_post_form(request.form)
        post["visibility"] = clean_post_visibility(request.visibility)
        post["word_count"] = count_words(body)
        post["media"] = self._clean_post_media_for_storage(
            request.media,
            user_id=user_record["id"],
            post_id=post_id,
        )
        post["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        clear_processed_corpus_cache()
        return to_user_post_response(post, user_record)

    def delete_post(self, token: str, post_id: str) -> None:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        post = store.get("posts", {}).get(post_id)
        if post is None or post.get("author_user_id") != user_record["id"]:
            raise PostNotFoundError("Post not found.")
        del store["posts"][post_id]
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        clear_processed_corpus_cache()

    def _store_avatar_reference(self, user_id: str, value: str | None) -> str | None:
        cleaned = clean_avatar_data_url(value)
        if not cleaned:
            return None
        if not self.media_storage.should_store_reference(cleaned):
            return cleaned
        try:
            stored = self.media_storage.store_data_url(
                cleaned,
                key_prefix=f"users/{user_id}/avatar",
                filename_hint="avatar",
                allowed_content_prefixes=("image/",),
            )
        except (StorageConfigurationError, StorageUploadError) as exc:
            raise PostMediaError(str(exc)) from exc
        return stored.url

    def _clean_post_media_for_storage(
        self,
        media_items: list[Any],
        *,
        user_id: str,
        post_id: str,
    ) -> list[dict[str, str | None]]:
        return clean_post_media(
            media_items,
            media_storage=self.media_storage,
            key_prefix=f"users/{user_id}/posts/{post_id}",
        )

    def directory(self, token: str) -> list[AccountDirectoryUserResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        users = [
            to_directory_user_response(candidate, store, user_record)
            for candidate in store["users"].values()
            if candidate["id"] != user_record["id"] and can_show_directory_user(candidate, user_record)
        ]
        return sorted(users, key=lambda candidate: candidate.display_name.lower())

    def reader_profile(self, token: str, user_id: str) -> AccountReaderProfileResponse:
        store = self._read_store()
        viewer_record = self._user_record_for_token(store, token)
        target_record = store["users"].get(user_id)
        if target_record is None or target_record["id"] == viewer_record["id"]:
            raise AccountNotFoundError("Reader not found.")
        ensure_user_state(target_record)
        if not can_show_directory_user(target_record, viewer_record):
            raise AccountNotFoundError("Reader not found.")

        posts = visible_posts_for_user(store, target_record, viewer_record)
        can_view_activity = can_view_reader_activity(target_record, viewer_record)
        activity = (
            build_reader_activity(
                store=store,
                target_record=target_record,
                viewer_record=viewer_record,
                corpus_service=self.corpus_service,
                limit=18,
            )
            if can_view_activity
            else []
        )
        return AccountReaderProfileResponse(
            reader=to_directory_user_response(target_record, store, viewer_record),
            posts=[to_user_post_response(post, target_record) for post in posts],
            activity=activity,
            can_view_activity=can_view_activity,
        )

    def followed_user_activity(self, token: str) -> list[AccountActivityItemResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        activity: list[AccountActivityItemResponse] = []
        for followed in user_record.get("followed_users", {}).values():
            target_record = store["users"].get(followed.get("id"))
            if target_record is None:
                continue
            ensure_user_state(target_record)
            if not can_show_directory_user(target_record, user_record):
                continue
            if not can_view_reader_activity(target_record, user_record):
                continue
            activity.extend(
                build_reader_activity(
                    store=store,
                    target_record=target_record,
                    viewer_record=user_record,
                    corpus_service=self.corpus_service,
                    limit=8,
                )
            )
        activity.sort(key=lambda item: item.created_at, reverse=True)
        return activity[:24]

    def excerpt_social_context(
        self, token: str | None, excerpt_id: str
    ) -> AccountExcerptSocialResponse:
        store = self._read_store()
        viewer_record: dict[str, Any] | None = None
        if token:
            viewer_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(excerpt_id)
        liked_by: list[AccountSocialUserResponse] = []
        saved_by: list[AccountSocialUserResponse] = []
        annotations: list[AccountPublicAnnotationResponse] = []

        for user_record in store["users"].values():
            ensure_user_state(user_record)
            if not can_view_social_user(user_record, viewer_record):
                continue

            if excerpt.id in user_record.get("feedback", {}).get("liked", []):
                liked_by.append(to_social_user_response(user_record, store))

            has_visible_save = False
            for item in saved_items_for_record(user_record):
                saved_kind = clean_saved_kind(item.get("saved_kind"))
                if not saved_item_applies_to_excerpt(item, excerpt):
                    continue
                if saved_kind == "selection":
                    if public_annotation_visible_to_viewer(item, user_record, viewer_record):
                        annotations.append(
                            to_public_annotation_response(item, user_record, store, excerpt)
                        )
                    continue
                has_visible_save = True
            if has_visible_save:
                saved_by.append(to_social_user_response(user_record, store))

        annotations.sort(key=lambda item: item.created_at, reverse=True)
        liked_by.sort(key=lambda user: user.display_name.lower())
        saved_by.sort(key=lambda user: user.display_name.lower())
        return AccountExcerptSocialResponse(
            excerpt_id=excerpt.id,
            like_count=len(liked_by),
            save_count=len(saved_by),
            annotation_count=len(annotations),
            liked_by=liked_by,
            saved_by=saved_by,
            annotations=annotations,
        )

    def follow_user(self, token: str, user_id: str) -> list[AccountDirectoryUserResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        target = store["users"].get(user_id)
        if target is None or target["id"] == user_record["id"]:
            raise AccountNotFoundError("Reader not found.")
        now = datetime.now(UTC).isoformat()
        user_record.setdefault("followed_users", {})[target["id"]] = {
            "id": target["id"],
            "display_name": target["display_name"],
            "followed_at": now,
        }
        user_record["updated_at"] = now
        self._write_store(store)
        return self.directory(token)

    def unfollow_user(self, token: str, user_id: str) -> list[AccountDirectoryUserResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        user_record.setdefault("followed_users", {}).pop(user_id, None)
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        return self.directory(token)

    def list_message_threads(self, token: str) -> list[MessageThreadResponse]:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        threads = [
            thread
            for thread in store["message_threads"].values()
            if user_record["id"] in thread.get("participant_user_ids", [])
        ]
        threads.sort(key=lambda candidate: candidate["updated_at"], reverse=True)
        return [to_message_thread_response(thread, store) for thread in threads]

    def send_message(
        self, token: str, request: MessageCreateRequest
    ) -> MessageThreadResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        now = datetime.now(UTC).isoformat()
        thread = self._message_thread_for_request(store, user_record, request, now)
        message = {
            "id": f"message-{uuid4()}",
            "thread_id": thread["id"],
            "sender_user_id": user_record["id"],
            "body": clean_message_body(request.body),
            "created_at": now,
        }
        thread.setdefault("messages", []).append(message)
        thread["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return to_message_thread_response(thread, store)

    def create_saved_folder(
        self, token: str, request: SavedFolderCreateRequest
    ) -> SavedFolderResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        now = datetime.now(UTC).isoformat()
        folder_id = unique_folder_id(request.name, user_record["saved_folders"])
        folder = {
            "id": folder_id,
            "name": clean_folder_name(request.name),
            "description": (request.description or "").strip(),
            "created_at": now,
            "updated_at": now,
            "items": {},
        }
        user_record["saved_folders"][folder_id] = folder
        user_record["updated_at"] = now
        self._write_store(store)
        return self._folder_response(folder)

    def save_excerpt(
        self, token: str, folder_id: str, request: SavedExcerptSaveRequest
    ) -> SavedFolderResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        folder = self._folder_for_user(user_record, folder_id)
        excerpt = self._excerpt_or_raise(request.excerpt_id)
        now = datetime.now(UTC).isoformat()
        item = build_saved_item(excerpt, request, now)
        folder["items"][item["id"]] = item
        folder["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return self._folder_response(folder)

    def remove_saved_excerpt(self, token: str, folder_id: str, excerpt_id: str) -> SavedFolderResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        folder = self._folder_for_user(user_record, folder_id)
        remove_saved_items_from_folder(folder, excerpt_id)
        now = datetime.now(UTC).isoformat()
        folder["updated_at"] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return self._folder_response(folder)

    def remove_saved_excerpt_everywhere(
        self, token: str, excerpt_id: str
    ) -> AccountExcerptStateResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(excerpt_id)
        now = datetime.now(UTC).isoformat()
        removed_any = False
        for folder in user_record["saved_folders"].values():
            removed_count = remove_saved_items_from_folder(
                folder, excerpt.id, work_id=excerpt.work_id, include_annotations=False
            )
            if removed_count:
                folder["updated_at"] = now
                removed_any = True
        if removed_any:
            user_record["updated_at"] = now
        self._write_store(store)
        return self.excerpt_state(token, excerpt.id)

    def record_feedback(
        self, token: str, request: AccountFeedbackRequest
    ) -> AccountFeedbackResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(request.excerpt_id)
        feedback = user_record["feedback"]
        remove_from_feedback(feedback, excerpt.id)
        feedback_timestamps = user_record.setdefault("feedback_timestamps", {})
        now = datetime.now(UTC).isoformat()

        if request.event_type == "like":
            feedback["liked"].append(excerpt.id)
        elif request.event_type == "dislike":
            feedback["disliked"].append(excerpt.id)
        else:
            feedback["skipped"].append(excerpt.id)

        feedback_timestamps[excerpt.id] = now
        user_record["updated_at"] = now
        self._write_store(store)
        return AccountFeedbackResponse(event_type=request.event_type, excerpt_id=excerpt.id)

    def clear_feedback(self, token: str, excerpt_id: str) -> AccountExcerptStateResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(excerpt_id)
        remove_from_feedback(user_record["feedback"], excerpt.id)
        user_record.setdefault("feedback_timestamps", {}).pop(excerpt.id, None)
        user_record["updated_at"] = datetime.now(UTC).isoformat()
        self._write_store(store)
        return self.excerpt_state(token, excerpt.id)

    def record_read_event(self, token: str, excerpt_id: str, event_type: str) -> None:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(excerpt_id)
        now = datetime.now(UTC).isoformat()
        user_record.setdefault("read_history", {})[excerpt.id] = {
            "excerpt_id": excerpt.id,
            "event_type": event_type,
            "last_read_at": now,
        }
        user_record["updated_at"] = now
        self._write_store(store)

    def excerpt_state(self, token: str, excerpt_id: str) -> AccountExcerptStateResponse:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        excerpt = self._excerpt_or_raise(excerpt_id)
        saved_folder_ids: list[str] = []
        saved_item_ids: list[str] = []
        for folder in user_record["saved_folders"].values():
            matching_item_ids = [
                saved_item_id(item, item_key)
                for item_key, item in folder.get("items", {}).items()
                if clean_saved_kind(item.get("saved_kind")) != "selection"
                and saved_item_applies_to_excerpt(item, excerpt, item_key)
            ]
            if matching_item_ids:
                saved_folder_ids.append(folder["id"])
                saved_item_ids.extend(matching_item_ids)
        feedback = feedback_for_excerpt(user_record["feedback"], excerpt.id)
        return AccountExcerptStateResponse(
            excerpt_id=excerpt.id,
            saved=bool(saved_folder_ids),
            saved_folder_ids=saved_folder_ids,
            saved_item_ids=saved_item_ids,
            feedback=feedback,
        )

    def recommendation_context(self, token: str) -> RecommendationFeedbackContext:
        store = self._read_store()
        user_record = self._user_record_for_token(store, token)
        saved_ids = saved_excerpt_ids(user_record)
        feedback = user_record["feedback"]
        positive_ids = unique_list([*saved_ids, *feedback["liked"]])
        negative_ids = unique_list([*feedback["disliked"], *feedback["skipped"]])
        return RecommendationFeedbackContext(
            positive_excerpt_ids=positive_ids,
            liked_excerpt_ids=feedback["liked"],
            negative_excerpt_ids=negative_ids,
            saved_excerpt_ids=saved_ids,
        )

    def _read_store(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {
                "users": {},
                "users_by_email": {},
                "sessions": {},
                "posts": {},
                "message_threads": {},
            }
        with self.store_path.open("r", encoding="utf-8") as store_file:
            store = json.load(store_file)
        store.setdefault("users", {})
        store.setdefault("users_by_email", {})
        store.setdefault("sessions", {})
        store.setdefault("posts", {})
        store.setdefault("message_threads", {})
        for user_record in store["users"].values():
            ensure_user_state(user_record)
        return store

    def _write_store(self, store: dict[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.store_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as store_file:
            json.dump(store, store_file, ensure_ascii=True, indent=2, sort_keys=True)
        temporary_path.replace(self.store_path)

    def _user_record_for_token(self, store: dict[str, Any], token: str) -> dict[str, Any]:
        session = store["sessions"].get(token)
        if session is None:
            raise AuthenticationError("Invalid or expired session.")

        user_record = store["users"].get(session["user_id"])
        if user_record is None:
            raise AccountNotFoundError("Account not found.")
        ensure_user_state(user_record)
        return user_record

    def _folder_for_user(self, user_record: dict[str, Any], folder_id: str) -> dict[str, Any]:
        folder = user_record["saved_folders"].get(folder_id)
        if folder is None:
            raise SavedFolderNotFoundError("Saved folder not found.")
        return folder

    def _music_playlist_for_user(
        self, user_record: dict[str, Any], playlist_id: str
    ) -> dict[str, Any]:
        playlist = user_record.setdefault("music_playlists", {}).get(playlist_id)
        if playlist is None:
            raise MusicPlaylistNotFoundError("Playlist not found.")
        playlist.setdefault("tracks", {})
        return playlist

    def _message_thread_for_request(
        self,
        store: dict[str, Any],
        user_record: dict[str, Any],
        request: MessageCreateRequest,
        timestamp: str,
    ) -> dict[str, Any]:
        if request.thread_id:
            thread = store["message_threads"].get(request.thread_id)
            if thread is None or user_record["id"] not in thread.get("participant_user_ids", []):
                raise MessageThreadNotFoundError("Message thread not found.")
            ensure_can_message_thread(store, user_record, thread)
            return thread

        recipient_id = request.recipient_user_id
        if recipient_id:
            recipient_id = recipient_id.strip()
            if recipient_id not in store["users"]:
                raise MessageRecipientNotFoundError("No account exists for that reader.")
        elif request.recipient_email:
            recipient_id = store["users_by_email"].get(normalize_email(request.recipient_email))
        else:
            raise MessageRecipientNotFoundError("Choose a reader.")
        if recipient_id is None:
            raise MessageRecipientNotFoundError("No account exists for that reader.")
        if recipient_id == user_record["id"]:
            raise MessageRecipientNotFoundError("Choose another reader to message.")
        ensure_can_message_user(store, user_record, recipient_id)

        existing_thread = existing_direct_thread(store, user_record["id"], recipient_id)
        if existing_thread is not None:
            return existing_thread

        thread = {
            "id": f"thread-{uuid4()}",
            "subject": clean_message_subject(request.subject),
            "participant_user_ids": [user_record["id"], recipient_id],
            "messages": [],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        store["message_threads"][thread["id"]] = thread
        return thread

    def _excerpt_or_raise(self, excerpt_id: str) -> ProcessedExcerpt:
        normalized_id = self._normalize_excerpt_id(excerpt_id)
        excerpt = self.corpus_service.find_reader_item(normalized_id)
        if excerpt is None:
            raise ExcerptNotFoundError("Excerpt not found.")
        return excerpt

    def _normalize_excerpt_id(self, excerpt_id: str) -> str:
        return excerpt_id.removeprefix("work-")

    def _folder_response(self, folder: dict[str, Any]) -> SavedFolderResponse:
        excerpts = self.corpus_service.list_excerpts()
        excerpts_by_id = {excerpt.id: excerpt for excerpt in excerpts}
        excerpts_by_work_id: dict[str, list[ProcessedExcerpt]] = {}
        for excerpt in excerpts:
            excerpts_by_work_id.setdefault(excerpt.work_id, []).append(excerpt)
        items = [
            to_saved_excerpt_response(item, excerpts_by_id, excerpts_by_work_id)
            for item in sorted(
                folder.get("items", {}).values(),
                key=lambda candidate: candidate["created_at"],
                reverse=True,
            )
        ]
        return SavedFolderResponse(
            id=folder["id"],
            name=folder["name"],
            description=folder.get("description", ""),
            created_at=datetime.fromisoformat(folder["created_at"]),
            updated_at=datetime.fromisoformat(folder["updated_at"]),
            items=items,
        )


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False

    candidate = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations),
    )
    return hmac.compare_digest(candidate.hex(), digest_hex)


def clean_preferences(preferences: PreferenceProfile) -> PreferenceProfile:
    return PreferenceProfile(
        genres=clean_list(preferences.genres),
        forms=clean_list(preferences.forms),
        themes=clean_list(preferences.themes),
        moods=clean_list(preferences.moods),
        authors=clean_list(preferences.authors),
        books=clean_list(preferences.books),
    )


def clean_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(value.strip().split())
        key = normalized.lower()
        if normalized and key not in seen:
            cleaned.append(normalized)
            seen.add(key)
    return cleaned


def clean_folder_name(name: str) -> str:
    return " ".join(name.strip().split())


def clean_display_name(name: str) -> str:
    return " ".join(name.strip().split())


def clean_bio(bio: str | None) -> str | None:
    cleaned = clean_optional_multiline_string(bio)
    return cleaned or None


def clean_avatar_data_url(value: str | None) -> str | None:
    cleaned = clean_optional_raw_string(value)
    if not cleaned:
        return None
    if is_renderable_media_reference(cleaned, media_type="image"):
        return cleaned
    return None


def clean_account_visibility(value: object) -> str:
    return "private" if value == "private" else "public"


def clean_post_title(title: str) -> str:
    return " ".join(title.strip().split())


def clean_post_body(body: str) -> str:
    return body.strip()


def clean_post_form(form: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 -]+", "", form).strip().lower()
    return cleaned or "prose"


def clean_post_visibility(visibility: str) -> str:
    return visibility if visibility in {"public", "followers", "private"} else "public"


def clean_post_media(
    media_items: list[Any],
    *,
    media_storage: ObjectStorageService | None = None,
    key_prefix: str = "posts",
) -> list[dict[str, str | None]]:
    cleaned_items: list[dict[str, str | None]] = []
    total_chars = 0
    for item in media_items[:4]:
        media_type = item.media_type
        data_url = item.data_url.strip()
        if not is_renderable_media_reference(data_url, media_type=media_type):
            if media_type == "image":
                raise PostMediaError("Images must be uploaded as image files.")
            raise PostMediaError("Videos must be uploaded as video files.")
        total_chars += len(data_url)
        if total_chars > 6_000_000:
            raise PostMediaError("Post media is too large for the configured upload flow.")

        stored_url = data_url
        if media_storage is not None and media_storage.should_store_reference(data_url):
            try:
                stored = media_storage.store_data_url(
                    data_url,
                    key_prefix=key_prefix,
                    filename_hint=clean_media_id(item.id),
                    allowed_content_prefixes=(f"{media_type}/",),
                )
            except (StorageConfigurationError, StorageUploadError) as exc:
                raise PostMediaError(str(exc)) from exc
            stored_url = stored.url

        cleaned_items.append(
            {
                "id": clean_media_id(item.id),
                "media_type": media_type,
                "data_url": stored_url,
                "alt_text": clean_media_text(item.alt_text, 180),
                "caption": clean_media_text(item.caption, 240),
            }
        )
    return cleaned_items


def clean_post_media_records(value: Any) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        return []
    cleaned_items: list[dict[str, str | None]] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        media_type = str(item.get("media_type") or "")
        data_url = str(item.get("data_url") or "")
        if media_type not in {"image", "video"}:
            continue
        cleaned_items.append(
            {
                "id": clean_media_id(str(item.get("id") or f"media-{len(cleaned_items) + 1}")),
                "media_type": media_type,
                "data_url": data_url,
                "alt_text": clean_media_text(item.get("alt_text"), 180),
                "caption": clean_media_text(item.get("caption"), 240),
            }
        )
    return cleaned_items


def clean_media_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return cleaned[:128] or f"media-{uuid4().hex[:8]}"


def clean_media_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned[:limit] or None


def clean_message_body(body: str) -> str:
    return body.strip()


def clean_message_subject(subject: str | None) -> str | None:
    cleaned = " ".join((subject or "").split())
    return cleaned or None


def unique_folder_id(name: str, folders: dict[str, Any]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", clean_folder_name(name).lower()).strip("-")
    if not base:
        base = "folder"
    folder_id = base
    counter = 2
    while folder_id in folders:
        folder_id = f"{base}-{counter}"
        counter += 1
    return folder_id


def default_saved_folders(timestamp: str) -> dict[str, dict[str, Any]]:
    return {
        folder_id: {
            "id": folder_id,
            "name": name,
            "description": description,
            "created_at": timestamp,
            "updated_at": timestamp,
            "items": {},
        }
        for folder_id, name, description in DEFAULT_SAVED_FOLDERS
    }


def default_feedback() -> dict[str, list[str]]:
    return {"liked": [], "disliked": [], "skipped": []}


def default_profile_metadata() -> dict[str, str | None]:
    return {"bio": None, "avatar_data_url": None, "account_visibility": "public"}


def default_music_preferences(timestamp: str) -> dict[str, Any]:
    return {"tones": [], "composers": [], "updated_at": timestamp}


def clean_music_preferences_record(value: Any, timestamp: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return default_music_preferences(timestamp)
    return {
        "tones": clean_music_preference_values(value.get("tones", [])),
        "composers": clean_music_preference_values(value.get("composers", [])),
        "updated_at": str(value.get("updated_at") or timestamp),
    }


def clean_music_preference_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return clean_list([str(value) for value in values])[:20]


def clean_playlist_name(name: str) -> str:
    return clean_folder_name(name)[:100] or "Playlist"


def unique_playlist_id(name: str, playlists: dict[str, Any]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", clean_playlist_name(name).lower()).strip("-")
    if not base:
        base = "playlist"
    playlist_id = base
    counter = 2
    while playlist_id in playlists:
        playlist_id = f"{base}-{counter}"
        counter += 1
    return playlist_id


def clean_music_track(request: MusicPlaylistTrackRequest, timestamp: str) -> dict[str, Any]:
    return {
        "id": re.sub(r"[^a-zA-Z0-9_.:-]+", "-", request.id.strip()).strip("-")[:160]
        or f"track-{uuid4().hex[:8]}",
        "title": " ".join(request.title.split())[:240],
        "composer": " ".join(request.composer.split())[:240],
        "performer": " ".join(request.performer.split())[:240],
        "duration": " ".join(request.duration.split())[:32],
        "tone_tags": clean_music_preference_values(request.tone_tags)[:12],
        "audio_url": request.audio_url.strip()[:1000],
        "source_url": request.source_url.strip()[:1000],
        "license": " ".join(request.license.split())[:240],
        "reason": " ".join((request.reason or "").split())[:500],
        "added_at": timestamp,
    }


def ensure_user_state(record: dict[str, Any]) -> None:
    now = datetime.now(UTC).isoformat()
    record.setdefault("profile_metadata", default_profile_metadata())
    record["profile_metadata"].setdefault("bio", None)
    record["profile_metadata"].setdefault("avatar_data_url", None)
    record["profile_metadata"].setdefault("account_visibility", "public")
    record.setdefault("followed_authors", {})
    record.setdefault("followed_users", {})
    record.setdefault("saved_folders", default_saved_folders(now))
    for folder_id, name, description in DEFAULT_SAVED_FOLDERS:
        record["saved_folders"].setdefault(
            folder_id,
            {
                "id": folder_id,
                "name": name,
                "description": description,
                "created_at": record.get("created_at", now),
                "updated_at": record.get("created_at", now),
                "items": {},
            },
        )
        record["saved_folders"][folder_id].setdefault("items", {})
    for folder in record["saved_folders"].values():
        for item_key, item in list(folder.get("items", {}).items()):
            if not isinstance(item, dict):
                folder["items"].pop(item_key, None)
                continue
            item.setdefault("id", item_key)
            item.setdefault("excerpt_id", item_key)
            item.setdefault("saved_kind", "excerpt")
            if item.get("saved_kind") == "selection":
                item.setdefault("highlight_color", "yellow")
                item.setdefault("selection_start", None)
                item.setdefault("selection_end", None)
                item.setdefault("annotation_visibility", "private")
    record.setdefault("feedback", default_feedback())
    for key in ("liked", "disliked", "skipped"):
        record["feedback"].setdefault(key, [])
    record.setdefault("feedback_timestamps", {})
    record.setdefault("read_history", {})
    progress = record.get("reading_progress")
    if progress is not None and not isinstance(progress, dict):
        record["reading_progress"] = None
    record.setdefault("music_preferences", default_music_preferences(now))
    record["music_preferences"] = clean_music_preferences_record(record.get("music_preferences"), now)
    record.setdefault("music_playlists", {})
    if not isinstance(record["music_playlists"], dict):
        record["music_playlists"] = {}
    for playlist_key, playlist in list(record["music_playlists"].items()):
        if not isinstance(playlist, dict):
            record["music_playlists"].pop(playlist_key, None)
            continue
        playlist.setdefault("id", playlist_key)
        playlist.setdefault("name", "Playlist")
        playlist.setdefault("description", "")
        playlist.setdefault("created_at", record.get("created_at", now))
        playlist.setdefault("updated_at", playlist.get("created_at", now))
        if not isinstance(playlist.get("tracks"), dict):
            playlist["tracks"] = {}
        for track_key, track in list(playlist["tracks"].items()):
            if not isinstance(track, dict):
                playlist["tracks"].pop(track_key, None)
                continue
            track.setdefault("id", track_key)
            track.setdefault("added_at", playlist.get("updated_at", now))


def to_user_response(record: dict[str, Any]) -> AccountUserResponse:
    profile_metadata = record.get("profile_metadata", {})
    return AccountUserResponse(
        id=record["id"],
        email=record["email"],
        display_name=record["display_name"],
        preferences=PreferenceProfile(**record.get("preferences", {})),
        bio=clean_optional_multiline_string(profile_metadata.get("bio")),
        avatar_data_url=clean_optional_raw_string(profile_metadata.get("avatar_data_url")),
        account_visibility=clean_account_visibility(profile_metadata.get("account_visibility")),
        created_at=datetime.fromisoformat(record["created_at"]),
        updated_at=datetime.fromisoformat(record["updated_at"]),
    )


def to_directory_user_response(
    record: dict[str, Any], store: dict[str, Any], viewer_record: dict[str, Any]
) -> AccountDirectoryUserResponse:
    profile_metadata = record.get("profile_metadata", {})
    followed_by_me = follows_user(viewer_record, record["id"])
    follows_me = follows_user(record, viewer_record["id"])
    post_count = sum(
        1
        for post in store.get("posts", {}).values()
        if post.get("author_user_id") == record["id"] and post.get("visibility") == "public"
    )
    existing_thread = existing_direct_thread(store, viewer_record["id"], record["id"])
    permission = message_permission_status(store, viewer_record, record["id"], existing_thread)
    return AccountDirectoryUserResponse(
        id=record["id"],
        display_name=record["display_name"],
        bio=clean_optional_multiline_string(profile_metadata.get("bio")),
        avatar_data_url=clean_optional_raw_string(profile_metadata.get("avatar_data_url")),
        account_visibility=clean_account_visibility(profile_metadata.get("account_visibility")),
        profile_role=profile_role(record, store),
        followed_by_me=followed_by_me,
        follows_me=follows_me,
        can_message=permission in {"mutual", "initial"},
        can_send_initial_message=permission == "initial",
        message_limit_reached=permission == "limit_reached",
        post_count=post_count,
    )


def followed_author_responses(record: dict[str, Any]) -> list[FollowedAuthorResponse]:
    authors = [
        FollowedAuthorResponse(
            id=author["id"],
            name=author["name"],
            followed_at=datetime.fromisoformat(author["followed_at"]),
        )
        for author in record.get("followed_authors", {}).values()
    ]
    return sorted(authors, key=lambda author: author.name.lower())


def to_reading_progress_response(record: dict[str, Any]) -> AccountReadingProgressResponse:
    return AccountReadingProgressResponse(
        id=str(record.get("id") or record.get("excerpt_id") or ""),
        work_id=str(record.get("work_id") or ""),
        title=str(record.get("title") or "Untitled"),
        author=str(record.get("author") or "Unknown author"),
        form=str(record.get("form") or "prose"),
        work_title=clean_optional_string(record.get("work_title")),
        section_title=clean_optional_string(record.get("section_title")),
        excerpt_label=clean_optional_string(record.get("excerpt_label")),
        saved_at=datetime.fromisoformat(str(record.get("saved_at"))),
    )


def build_reading_progress_record(excerpt: ProcessedExcerpt, timestamp: str) -> dict[str, Any]:
    return {
        "id": excerpt.id,
        "work_id": excerpt.work_id,
        "title": excerpt.title,
        "author": excerpt.author,
        "form": excerpt.form,
        "work_title": getattr(excerpt, "work_title", None),
        "section_title": getattr(excerpt, "section_title", None),
        "excerpt_label": getattr(excerpt, "excerpt_label", None),
        "saved_at": timestamp,
    }


def to_music_preference_response(record: Any) -> MusicPreferenceResponse:
    cleaned = clean_music_preferences_record(record, datetime.now(UTC).isoformat())
    updated_at = cleaned.get("updated_at")
    return MusicPreferenceResponse(
        tones=cleaned["tones"],
        composers=cleaned["composers"],
        updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
    )


def to_music_playlist_response(playlist: dict[str, Any]) -> MusicPlaylistResponse:
    tracks = [
        to_music_playlist_track_response(track)
        for track in sorted(
            playlist.get("tracks", {}).values(),
            key=lambda candidate: candidate.get("added_at", ""),
            reverse=True,
        )
    ]
    return MusicPlaylistResponse(
        id=str(playlist.get("id") or "playlist"),
        name=clean_playlist_name(str(playlist.get("name") or "Playlist")),
        description=clean_optional_string(playlist.get("description")) or "",
        created_at=datetime.fromisoformat(str(playlist.get("created_at"))),
        updated_at=datetime.fromisoformat(str(playlist.get("updated_at"))),
        tracks=tracks,
    )


def to_music_playlist_track_response(track: dict[str, Any]):
    return {
        "id": str(track.get("id") or "track"),
        "title": str(track.get("title") or "Untitled"),
        "composer": str(track.get("composer") or "Unknown composer"),
        "performer": str(track.get("performer") or "Unknown performer"),
        "duration": str(track.get("duration") or "0:00"),
        "tone_tags": clean_music_preference_values(track.get("tone_tags", []))[:12],
        "audio_url": str(track.get("audio_url") or ""),
        "source_url": str(track.get("source_url") or ""),
        "license": str(track.get("license") or "Unknown license"),
        "reason": str(track.get("reason") or ""),
        "added_at": datetime.fromisoformat(str(track.get("added_at"))),
    }


def to_user_post_response(
    post: dict[str, Any], author_record: dict[str, Any]
) -> UserPostResponse:
    return UserPostResponse(
        id=post["id"],
        author_user_id=post["author_user_id"],
        author_display_name=author_record["display_name"],
        title=post["title"],
        body=post["body"],
        form=post["form"],
        visibility=post["visibility"],
        word_count=int(post.get("word_count") or count_words(post["body"])),
        media=[
            UserPostMediaResponse(
                id=item["id"],
                media_type=item["media_type"],
                data_url=item["data_url"],
                alt_text=item.get("alt_text"),
                caption=item.get("caption"),
            )
            for item in clean_post_media_records(post.get("media"))
        ],
        created_at=datetime.fromisoformat(post["created_at"]),
        updated_at=datetime.fromisoformat(post["updated_at"]),
    )


def to_message_thread_response(
    thread: dict[str, Any], store: dict[str, Any]
) -> MessageThreadResponse:
    users = store["users"]
    participants = [
        to_message_participant_response(users[user_id])
        for user_id in thread.get("participant_user_ids", [])
        if user_id in users
    ]
    return MessageThreadResponse(
        id=thread["id"],
        subject=thread.get("subject"),
        participants=participants,
        messages=[
            to_message_response(message, users)
            for message in thread.get("messages", [])
            if message.get("sender_user_id") in users
        ],
        created_at=datetime.fromisoformat(thread["created_at"]),
        updated_at=datetime.fromisoformat(thread["updated_at"]),
    )


def to_message_participant_response(record: dict[str, Any]) -> MessageParticipantResponse:
    profile_metadata = record.get("profile_metadata", {})
    return MessageParticipantResponse(
        id=record["id"],
        display_name=record["display_name"],
        email=record["email"],
        avatar_data_url=clean_optional_raw_string(profile_metadata.get("avatar_data_url")),
    )


def to_message_response(message: dict[str, Any], users: dict[str, Any]) -> MessageResponse:
    sender = users[message["sender_user_id"]]
    return MessageResponse(
        id=message["id"],
        thread_id=message["thread_id"],
        sender_user_id=message["sender_user_id"],
        sender_display_name=sender["display_name"],
        body=message["body"],
        created_at=datetime.fromisoformat(message["created_at"]),
    )


def profile_role(record: dict[str, Any], store: dict[str, Any]) -> str:
    authored_posts = [
        post
        for post in store.get("posts", {}).values()
        if post.get("author_user_id") == record["id"]
    ]
    return "writer_reader" if authored_posts else "reader"


def to_social_user_response(
    record: dict[str, Any], store: dict[str, Any]
) -> AccountSocialUserResponse:
    profile_metadata = record.get("profile_metadata", {})
    return AccountSocialUserResponse(
        id=record["id"],
        display_name=record["display_name"],
        avatar_data_url=clean_optional_raw_string(profile_metadata.get("avatar_data_url")),
        profile_role=profile_role(record, store),
    )


def visible_posts_for_user(
    store: dict[str, Any], target_record: dict[str, Any], viewer_record: dict[str, Any]
) -> list[dict[str, Any]]:
    posts = [
        post
        for post in store.get("posts", {}).values()
        if post.get("author_user_id") == target_record["id"]
        and can_view_post(post, target_record, viewer_record)
    ]
    return sorted(posts, key=lambda post: post["created_at"], reverse=True)


def can_view_post(
    post: dict[str, Any], target_record: dict[str, Any], viewer_record: dict[str, Any]
) -> bool:
    if target_record["id"] == viewer_record["id"]:
        return True
    visibility = clean_post_visibility(str(post.get("visibility", "public")))
    if visibility == "public":
        return True
    if visibility == "followers" and follows_user(viewer_record, target_record["id"]):
        return True
    return False


def can_view_reader_activity(target_record: dict[str, Any], viewer_record: dict[str, Any]) -> bool:
    if target_record["id"] == viewer_record["id"]:
        return True
    visibility = clean_account_visibility(
        target_record.get("profile_metadata", {}).get("account_visibility")
    )
    if visibility == "public":
        return True
    return follows_user(viewer_record, target_record["id"]) and follows_user(
        target_record,
        viewer_record["id"],
    )


def can_view_social_user(
    target_record: dict[str, Any], viewer_record: dict[str, Any] | None
) -> bool:
    if viewer_record is None:
        visibility = clean_account_visibility(
            target_record.get("profile_metadata", {}).get("account_visibility")
        )
        return visibility == "public"
    if target_record["id"] == viewer_record["id"]:
        return True
    return can_show_directory_user(target_record, viewer_record)


def public_annotation_visible_to_viewer(
    item: dict[str, Any],
    target_record: dict[str, Any],
    viewer_record: dict[str, Any] | None,
) -> bool:
    if viewer_record is not None and target_record["id"] == viewer_record["id"]:
        return True
    if viewer_record is None or clean_annotation_visibility(item.get("annotation_visibility")) != "public":
        return False
    return follows_user(viewer_record, target_record["id"]) and follows_user(
        target_record,
        viewer_record["id"],
    )


def build_reader_activity(
    *,
    store: dict[str, Any],
    target_record: dict[str, Any],
    viewer_record: dict[str, Any],
    corpus_service: ProcessedCorpusService,
    limit: int,
) -> list[AccountActivityItemResponse]:
    excerpts = corpus_service.list_excerpts()
    excerpts_by_id = {excerpt.id: excerpt for excerpt in excerpts}
    excerpts_by_work_id: dict[str, list[ProcessedExcerpt]] = {}
    for excerpt in excerpts:
        excerpts_by_work_id.setdefault(excerpt.work_id, []).append(excerpt)

    activity: list[AccountActivityItemResponse] = []
    for post in visible_posts_for_user(store, target_record, viewer_record):
        activity.append(
            AccountActivityItemResponse(
                id=f"activity-{post['id']}",
                activity_type="posted",
                user_id=target_record["id"],
                user_display_name=target_record["display_name"],
                title=post["title"],
                author=target_record["display_name"],
                post_id=post["id"],
                preview=trim_preview(post["body"]),
                created_at=datetime.fromisoformat(post["created_at"]),
            )
        )

    for item in saved_items_for_record(target_record):
        if not saved_activity_visible_to_viewer(item, target_record, viewer_record):
            continue
        response = to_saved_excerpt_response(item, excerpts_by_id, excerpts_by_work_id)
        activity_type = "annotated" if response.saved_kind == "selection" else "saved"
        activity.append(
            AccountActivityItemResponse(
                id=f"activity-{response.id}",
                activity_type=activity_type,
                user_id=target_record["id"],
                user_display_name=target_record["display_name"],
                title=response.title,
                author=response.author,
                excerpt_id=response.excerpt_id,
                preview=response.preview,
                selected_text=response.selected_text,
                note=response.note,
                created_at=response.created_at,
            )
        )

    feedback_timestamps = target_record.get("feedback_timestamps", {})
    for excerpt_id in target_record.get("feedback", {}).get("liked", []):
        excerpt = excerpts_by_id.get(excerpt_id)
        if excerpt is None:
            continue
        activity.append(
            AccountActivityItemResponse(
                id=f"activity-liked-{target_record['id']}-{excerpt.id}",
                activity_type="liked",
                user_id=target_record["id"],
                user_display_name=target_record["display_name"],
                title=excerpt.title,
                author=excerpt.author,
                excerpt_id=excerpt.id,
                preview=excerpt.preview,
                created_at=datetime.fromisoformat(
                    feedback_timestamps.get(excerpt.id, target_record["updated_at"])
                ),
            )
        )

    for read in target_record.get("read_history", {}).values():
        excerpt = excerpts_by_id.get(read.get("excerpt_id"))
        if excerpt is None:
            continue
        activity.append(
            AccountActivityItemResponse(
                id=f"activity-read-{target_record['id']}-{excerpt.id}",
                activity_type="read",
                user_id=target_record["id"],
                user_display_name=target_record["display_name"],
                title=excerpt.title,
                author=excerpt.author,
                excerpt_id=excerpt.id,
                preview=excerpt.preview,
                created_at=datetime.fromisoformat(
                    read.get("last_read_at", target_record["updated_at"])
                ),
            )
        )

    activity.sort(key=lambda item: item.created_at, reverse=True)
    return activity[:limit]


def saved_activity_visible_to_viewer(
    item: dict[str, Any],
    target_record: dict[str, Any],
    viewer_record: dict[str, Any],
) -> bool:
    if target_record["id"] == viewer_record["id"]:
        return True
    if clean_saved_kind(item.get("saved_kind")) != "selection":
        return True
    return public_annotation_visible_to_viewer(item, target_record, viewer_record)


def saved_items_for_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for folder in record.get("saved_folders", {}).values():
        items.extend(folder.get("items", {}).values())
    return items


def to_public_annotation_response(
    item: dict[str, Any],
    user_record: dict[str, Any],
    store: dict[str, Any],
    excerpt: ProcessedExcerpt,
) -> AccountPublicAnnotationResponse:
    return AccountPublicAnnotationResponse(
        id=saved_item_id(item),
        excerpt_id=excerpt.id,
        user=to_social_user_response(user_record, store),
        selected_text=clean_selected_text(str(item.get("selected_text") or "")),
        selection_start=clean_selection_offset(item.get("selection_start")),
        selection_end=clean_selection_offset(item.get("selection_end")),
        highlight_color=clean_highlight_color(item.get("highlight_color")),
        note=clean_optional_string(item.get("note")),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


def existing_direct_thread(
    store: dict[str, Any], user_id: str, recipient_id: str
) -> dict[str, Any] | None:
    target_participants = {user_id, recipient_id}
    for thread in store["message_threads"].values():
        participant_ids = set(thread.get("participant_user_ids", []))
        if participant_ids == target_participants:
            return thread
    return None


def can_show_directory_user(candidate: dict[str, Any], viewer_record: dict[str, Any]) -> bool:
    visibility = clean_account_visibility(
        candidate.get("profile_metadata", {}).get("account_visibility")
    )
    return visibility == "public" or follows_user(candidate, viewer_record["id"]) or follows_user(
        viewer_record,
        candidate["id"],
    )


def follows_user(record: dict[str, Any], user_id: str) -> bool:
    return user_id in record.get("followed_users", {})


def ensure_can_message_user(
    store: dict[str, Any],
    user_record: dict[str, Any],
    recipient_id: str,
    thread: dict[str, Any] | None = None,
) -> None:
    recipient_record = store["users"].get(recipient_id)
    if recipient_record is None:
        raise MessageRecipientNotFoundError("No account exists for that reader.")
    permission = message_permission_status(store, user_record, recipient_id, thread)
    if permission == "not_following":
        raise MessagePermissionError("Follow this reader before sending a message.")
    if permission == "limit_reached":
        raise MessagePermissionError(
            "You have already sent one message. They need to follow you back before you can send another."
        )
    if permission == "none":
        raise MessagePermissionError("You can message readers only after you follow each other.")


def ensure_can_message_thread(
    store: dict[str, Any], user_record: dict[str, Any], thread: dict[str, Any]
) -> None:
    for participant_id in thread.get("participant_user_ids", []):
        if participant_id != user_record["id"]:
            ensure_can_message_user(store, user_record, participant_id, thread)


def message_permission_status(
    store: dict[str, Any],
    user_record: dict[str, Any],
    recipient_id: str,
    thread: dict[str, Any] | None = None,
) -> str:
    recipient_record = store.get("users", {}).get(recipient_id)
    if recipient_record is None:
        return "none"
    if follows_user(user_record, recipient_id) and follows_user(recipient_record, user_record["id"]):
        return "mutual"
    if not follows_user(user_record, recipient_id):
        return "not_following"
    direct_thread = thread or existing_direct_thread(store, user_record["id"], recipient_id)
    if direct_thread is None or sent_message_count(direct_thread, user_record["id"]) == 0:
        return "initial"
    return "limit_reached"


def sent_message_count(thread: dict[str, Any], sender_user_id: str) -> int:
    return sum(
        1
        for message in thread.get("messages", [])
        if message.get("sender_user_id") == sender_user_id
    )


def to_saved_excerpt_response(
    item: dict[str, Any],
    excerpts_by_id: dict[str, ProcessedExcerpt],
    excerpts_by_work_id: dict[str, list[ProcessedExcerpt]],
) -> SavedExcerptResponse:
    item_id = saved_item_id(item)
    excerpt_id = item.get("excerpt_id", item_id)
    saved_kind = clean_saved_kind(item.get("saved_kind"))
    selected_text = clean_optional_string(item.get("selected_text"))
    selection_start = clean_selection_offset(item.get("selection_start"))
    selection_end = clean_selection_offset(item.get("selection_end"))
    highlight_color = (
        clean_highlight_color(item.get("highlight_color")) if saved_kind == "selection" else None
    )
    annotation_visibility = (
        clean_annotation_visibility(item.get("annotation_visibility"))
        if saved_kind == "selection"
        else None
    )
    excerpt = excerpts_by_id.get(excerpt_id)
    if excerpt is None:
        return SavedExcerptResponse(
            id=item_id,
            excerpt_id=excerpt_id,
            saved_kind=saved_kind,
            title="Saved item",
            author="Unknown author",
            form="unknown",
            preview=selected_text or "This saved item is no longer present in the local corpus.",
            word_count=count_words(selected_text or ""),
            selected_text=selected_text,
            selection_start=selection_start,
            selection_end=selection_end,
            highlight_color=highlight_color,
            annotation_visibility=annotation_visibility,
            note=item.get("note"),
            created_at=datetime.fromisoformat(item["created_at"]),
        )
    title = excerpt.title
    preview = excerpt.preview
    word_count = excerpt.word_count
    if saved_kind == "work":
        title = excerpt.work_title or excerpt.title
        word_count = sum(
            work_excerpt.word_count
            for work_excerpt in excerpts_by_work_id.get(item.get("work_id"), [excerpt])
        )
    elif saved_kind == "selection":
        title = f"{excerpt.title}: selection"
        preview = trim_preview(selected_text or excerpt.preview)
        word_count = count_words(selected_text or "")
    return SavedExcerptResponse(
        id=item_id,
        excerpt_id=excerpt.id,
        saved_kind=saved_kind,
        title=title,
        author=excerpt.author,
        form=excerpt.form,
        preview=preview,
        word_count=word_count,
        selected_text=selected_text,
        selection_start=selection_start,
        selection_end=selection_end,
        highlight_color=highlight_color,
        annotation_visibility=annotation_visibility,
        note=item.get("note"),
        created_at=datetime.fromisoformat(item["created_at"]),
    )


def to_feedback_excerpt_response(
    excerpt: ProcessedExcerpt, user_record: dict[str, Any]
) -> SavedExcerptResponse:
    return SavedExcerptResponse(
        id=excerpt.id,
        excerpt_id=excerpt.id,
        saved_kind="excerpt",
        title=excerpt.title,
        author=excerpt.author,
        form=excerpt.form,
        preview=excerpt.preview,
        word_count=excerpt.word_count,
        created_at=datetime.fromisoformat(user_record["updated_at"]),
    )


def saved_excerpt_ids(record: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for folder in record["saved_folders"].values():
        ids.extend(
            saved_item_excerpt_id(item, item_key)
            for item_key, item in folder.get("items", {}).items()
        )
    return unique_list(ids)


def build_saved_item(
    excerpt: ProcessedExcerpt, request: SavedExcerptSaveRequest, timestamp: str
) -> dict[str, Any]:
    note = request.note.strip() if request.note else None
    base_item = {
        "excerpt_id": excerpt.id,
        "work_id": excerpt.work_id,
        "note": note,
        "created_at": timestamp,
    }

    if request.save_scope == "work":
        return {
            **base_item,
            "id": f"{excerpt.work_id}-whole-work",
            "saved_kind": "work",
        }

    if request.save_scope == "selection":
        selected_text = clean_selected_text(request.selected_text)
        if not selected_text:
            raise SavedSelectionError("Highlight text before saving a selection.")
        if normalize_text_for_match(selected_text) not in normalize_text_for_match(excerpt.text):
            raise SavedSelectionError("The highlighted text was not found in this excerpt.")
        selection_start, selection_end = validated_selection_offsets(excerpt, request, selected_text)
        selection_hash = sha1(
            f"{excerpt.id}\0{selection_start}\0{selection_end}\0{selected_text}\0{timestamp}".encode(
                "utf-8"
            )
        ).hexdigest()[:8]
        return {
            **base_item,
            "id": f"{excerpt.id}-selection-{selection_hash}-{uuid4().hex[:8]}",
            "saved_kind": "selection",
            "selected_text": selected_text,
            "selection_start": selection_start,
            "selection_end": selection_end,
            "highlight_color": clean_highlight_color(request.highlight_color),
            "annotation_visibility": clean_annotation_visibility(request.annotation_visibility),
        }

    return {
        **base_item,
        "id": excerpt.id,
        "saved_kind": "excerpt",
    }


def remove_saved_items_from_folder(
    folder: dict[str, Any],
    target_id: str,
    work_id: str | None = None,
    include_annotations: bool = True,
) -> int:
    normalized_target_id = target_id.removeprefix("work-")
    removed_count = 0
    for item_key, item in list(folder.get("items", {}).items()):
        item_id = saved_item_id(item, item_key)
        excerpt_id = saved_item_excerpt_id(item, item_key)
        saved_kind = clean_saved_kind(item.get("saved_kind"))
        if not include_annotations and saved_kind == "selection":
            continue
        is_item_match = item_key == target_id or item_id == target_id
        is_legacy_item_match = item_key == normalized_target_id or item_id == normalized_target_id
        is_excerpt_match = excerpt_id == target_id or excerpt_id == normalized_target_id
        is_work_match = (
            work_id is not None
            and saved_kind == "work"
            and item.get("work_id") == work_id
        )
        if is_item_match or is_legacy_item_match or is_excerpt_match or is_work_match:
            folder["items"].pop(item_key, None)
            removed_count += 1
    return removed_count


def saved_item_applies_to_excerpt(
    item: dict[str, Any], excerpt: ProcessedExcerpt, item_key: str | None = None
) -> bool:
    if clean_saved_kind(item.get("saved_kind")) == "work" and item.get("work_id") == excerpt.work_id:
        return True
    return saved_item_excerpt_id(item, item_key) == excerpt.id


def saved_item_id(item: dict[str, Any], item_key: str | None = None) -> str:
    return str(item.get("id") or item_key or item.get("excerpt_id") or "")


def saved_item_excerpt_id(item: dict[str, Any], item_key: str | None = None) -> str:
    return str(item.get("excerpt_id") or item_key or item.get("id") or "")


def clean_saved_kind(value: Any) -> str:
    return value if value in {"work", "excerpt", "selection"} else "excerpt"


def clean_highlight_color(value: Any) -> str:
    return value if value in {"yellow", "green", "blue", "pink", "lavender"} else "yellow"


def clean_annotation_visibility(value: Any) -> str:
    return value if value in {"private", "public"} else "private"


def clean_selection_offset(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def validated_selection_offsets(
    excerpt: ProcessedExcerpt, request: SavedExcerptSaveRequest, selected_text: str
) -> tuple[int | None, int | None]:
    start = request.selection_start
    end = request.selection_end
    if start is None or end is None:
        return None, None
    if start >= end or end > len(excerpt.text):
        raise SavedSelectionError("The highlighted text position is outside this excerpt.")
    selected_excerpt_text = excerpt.text[start:end]
    if normalize_text_for_match(selected_excerpt_text) != normalize_text_for_match(selected_text):
        raise SavedSelectionError("The highlighted text position no longer matches this excerpt.")
    return start, end


def clean_selected_text(value: str | None) -> str:
    return " ".join((value or "").split())


def clean_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = clean_selected_text(value)
    return cleaned or None


def clean_optional_multiline_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = "\n".join(line.strip() for line in value.strip().splitlines())
    return cleaned or None


def clean_optional_raw_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_text_for_match(value: str) -> str:
    return " ".join(value.split()).casefold()


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def trim_preview(text: str, limit: int = 260) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return f"{single_line[: limit - 3].rstrip()}..."


def remove_from_feedback(feedback: dict[str, list[str]], excerpt_id: str) -> None:
    for key in ("liked", "disliked", "skipped"):
        feedback[key] = [stored_id for stored_id in feedback[key] if stored_id != excerpt_id]


def feedback_for_excerpt(
    feedback: dict[str, list[str]], excerpt_id: str
) -> AccountFeedbackEventType | None:
    if excerpt_id in feedback.get("liked", []):
        return "like"
    if excerpt_id in feedback.get("disliked", []):
        return "dislike"
    if excerpt_id in feedback.get("skipped", []):
        return "skip"
    return None


def unique_list(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values
