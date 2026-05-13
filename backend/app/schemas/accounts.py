from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PreferenceProfile(BaseModel):
    genres: list[str] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    books: list[str] = Field(default_factory=list)


class AccountUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    preferences: PreferenceProfile
    bio: str | None = None
    avatar_data_url: str | None = None
    account_visibility: Literal["public", "private"] = "public"
    created_at: datetime
    updated_at: datetime


class AccountDirectoryUserResponse(BaseModel):
    id: str
    display_name: str
    bio: str | None = None
    avatar_data_url: str | None = None
    account_visibility: Literal["public", "private"] = "public"
    profile_role: Literal["reader", "writer", "writer_reader"] = "reader"
    followed_by_me: bool = False
    follows_me: bool = False
    can_message: bool = False
    can_send_initial_message: bool = False
    message_limit_reached: bool = False
    post_count: int = 0


class AccountRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)
    preferences: PreferenceProfile = Field(default_factory=PreferenceProfile)


class AccountLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class AccountAuthResponse(BaseModel):
    token: str
    user: AccountUserResponse


class PreferenceUpdateRequest(BaseModel):
    preferences: PreferenceProfile


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    avatar_data_url: str | None = Field(default=None, max_length=500_000)
    account_visibility: Literal["public", "private"] | None = None


PostMediaKind = Literal["image", "video"]


class UserPostMediaRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    media_type: PostMediaKind
    data_url: str = Field(min_length=1, max_length=2_750_000)
    alt_text: str | None = Field(default=None, max_length=180)
    caption: str | None = Field(default=None, max_length=240)


class UserPostMediaResponse(BaseModel):
    id: str
    media_type: PostMediaKind
    data_url: str
    alt_text: str | None = None
    caption: str | None = None


class UserPostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=20_000)
    form: str = Field(default="prose", max_length=64)
    visibility: str = Field(default="public", max_length=32)
    media: list[UserPostMediaRequest] = Field(default_factory=list, max_length=4)


class UserPostResponse(BaseModel):
    id: str
    author_user_id: str
    author_display_name: str
    title: str
    body: str
    form: str
    visibility: str
    word_count: int
    media: list[UserPostMediaResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MessageParticipantResponse(BaseModel):
    id: str
    display_name: str
    email: str
    avatar_data_url: str | None = None


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    sender_user_id: str
    sender_display_name: str
    body: str
    created_at: datetime


class MessageThreadResponse(BaseModel):
    id: str
    subject: str | None = None
    participants: list[MessageParticipantResponse] = Field(default_factory=list)
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    recipient_email: str | None = Field(default=None, max_length=320)
    recipient_user_id: str | None = Field(default=None, max_length=128)
    subject: str | None = Field(default=None, max_length=160)
    thread_id: str | None = Field(default=None, max_length=128)


SavedItemKind = Literal["work", "excerpt", "selection"]
HighlightColor = Literal["yellow", "green", "blue", "pink", "lavender"]
AnnotationVisibility = Literal["private", "public"]


class SavedExcerptSaveRequest(BaseModel):
    excerpt_id: str = Field(min_length=1, max_length=128)
    save_scope: SavedItemKind = "excerpt"
    selected_text: str | None = Field(default=None, max_length=4000)
    selection_start: int | None = Field(default=None, ge=0)
    selection_end: int | None = Field(default=None, ge=0)
    highlight_color: HighlightColor = "yellow"
    annotation_visibility: AnnotationVisibility = "private"
    note: str | None = Field(default=None, max_length=500)


class SavedExcerptResponse(BaseModel):
    id: str
    excerpt_id: str
    saved_kind: SavedItemKind = "excerpt"
    title: str
    author: str
    form: str
    preview: str
    word_count: int
    selected_text: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    highlight_color: HighlightColor | None = None
    annotation_visibility: AnnotationVisibility | None = None
    note: str | None = None
    created_at: datetime


class SavedFolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)


class SavedFolderResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    items: list[SavedExcerptResponse] = Field(default_factory=list)


class AccountLibraryResponse(BaseModel):
    saved: list[SavedExcerptResponse] = Field(default_factory=list)
    annotations: list[SavedExcerptResponse] = Field(default_factory=list)
    liked: list[SavedExcerptResponse] = Field(default_factory=list)


class AccountReadingProgressRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    work_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=240)
    author: str = Field(min_length=1, max_length=240)
    form: str = Field(min_length=1, max_length=64)
    work_title: str | None = Field(default=None, max_length=240)
    section_title: str | None = Field(default=None, max_length=240)
    excerpt_label: str | None = Field(default=None, max_length=240)


class AccountReadingProgressResponse(AccountReadingProgressRequest):
    saved_at: datetime


class MusicPreferenceRequest(BaseModel):
    tones: list[str] = Field(default_factory=list, max_length=12)
    composers: list[str] = Field(default_factory=list, max_length=20)


class MusicPreferenceResponse(MusicPreferenceRequest):
    updated_at: datetime | None = None


class MusicPlaylistTrackRequest(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    composer: str = Field(min_length=1, max_length=240)
    performer: str = Field(min_length=1, max_length=240)
    duration: str = Field(min_length=1, max_length=32)
    tone_tags: list[str] = Field(default_factory=list, max_length=12)
    audio_url: str = Field(min_length=1, max_length=1000)
    source_url: str = Field(min_length=1, max_length=1000)
    license: str = Field(min_length=1, max_length=240)
    reason: str = Field(default="", max_length=500)


class MusicPlaylistTrackResponse(MusicPlaylistTrackRequest):
    added_at: datetime


class MusicPlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=240)


class MusicPlaylistResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    tracks: list[MusicPlaylistTrackResponse] = Field(default_factory=list)


AccountActivityType = Literal["posted", "saved", "liked", "annotated", "read"]


class AccountActivityItemResponse(BaseModel):
    id: str
    activity_type: AccountActivityType
    user_id: str
    user_display_name: str
    title: str
    author: str | None = None
    excerpt_id: str | None = None
    post_id: str | None = None
    preview: str
    selected_text: str | None = None
    note: str | None = None
    created_at: datetime


class AccountReaderProfileResponse(BaseModel):
    reader: AccountDirectoryUserResponse
    posts: list[UserPostResponse] = Field(default_factory=list)
    activity: list[AccountActivityItemResponse] = Field(default_factory=list)
    can_view_activity: bool = True


class AccountSocialUserResponse(BaseModel):
    id: str
    display_name: str
    avatar_data_url: str | None = None
    profile_role: Literal["reader", "writer", "writer_reader"] = "reader"


class AccountPublicAnnotationResponse(BaseModel):
    id: str
    excerpt_id: str
    user: AccountSocialUserResponse
    selected_text: str
    selection_start: int | None = None
    selection_end: int | None = None
    highlight_color: HighlightColor = "yellow"
    note: str | None = None
    created_at: datetime


class AccountExcerptSocialResponse(BaseModel):
    excerpt_id: str
    like_count: int = 0
    save_count: int = 0
    annotation_count: int = 0
    liked_by: list[AccountSocialUserResponse] = Field(default_factory=list)
    saved_by: list[AccountSocialUserResponse] = Field(default_factory=list)
    annotations: list[AccountPublicAnnotationResponse] = Field(default_factory=list)


class FollowedAuthorResponse(BaseModel):
    id: str
    name: str
    followed_at: datetime


AccountFeedbackEventType = Literal["like", "dislike", "skip"]


class AccountFeedbackRequest(BaseModel):
    event_type: AccountFeedbackEventType
    excerpt_id: str = Field(min_length=1, max_length=128)


class AccountFeedbackResponse(BaseModel):
    event_type: AccountFeedbackEventType
    excerpt_id: str
    accepted: bool = True


class AccountExcerptStateResponse(BaseModel):
    excerpt_id: str
    saved: bool = False
    saved_folder_ids: list[str] = Field(default_factory=list)
    saved_item_ids: list[str] = Field(default_factory=list)
    feedback: AccountFeedbackEventType | None = None
