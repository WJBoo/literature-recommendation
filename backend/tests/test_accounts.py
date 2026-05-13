import json

from app.schemas.accounts import (
    AccountFeedbackRequest,
    AccountLoginRequest,
    AccountRegisterRequest,
    MessageCreateRequest,
    PreferenceProfile,
    ProfileUpdateRequest,
    SavedExcerptSaveRequest,
    SavedFolderCreateRequest,
    UserPostCreateRequest,
    UserPostMediaRequest,
)
from app.services.accounts import AccountConflictError, AccountService, AuthenticationError
from app.services.processed_corpus import ProcessedCorpusService


def test_account_register_login_and_update_preferences(tmp_path):
    service = AccountService(store_path=tmp_path / "accounts.json")

    registered = service.register(
        AccountRegisterRequest(
            email="Reader@Example.com",
            password="long-enough-password",
            display_name="Reader",
            preferences=PreferenceProfile(
                genres=["Romance", "romance", " Gothic "],
                forms=["poetry"],
                authors=["Austen"],
            ),
        )
    )

    assert registered.user.email == "reader@example.com"
    assert registered.user.preferences.genres == ["Romance", "Gothic"]
    assert registered.user.preferences.forms == ["poetry"]

    logged_in = service.login(
        AccountLoginRequest(email="reader@example.com", password="long-enough-password")
    )
    assert logged_in.user.id == registered.user.id
    assert logged_in.token != registered.token

    updated = service.update_preferences(
        logged_in.token,
        PreferenceProfile(genres=["Satire"], themes=["courtship"], authors=["Jane Austen"]),
    )
    assert updated.preferences.genres == ["Satire"]
    assert updated.preferences.themes == ["courtship"]
    assert service.get_user_for_token(logged_in.token).preferences.authors == ["Jane Austen"]

    profiled = service.update_profile(
        logged_in.token,
        ProfileUpdateRequest(
            display_name="Language Lover",
            bio="Reader, writer, marginal-note enthusiast.",
            avatar_data_url="data:image/png;base64,abc123",
            account_visibility="private",
        ),
    )
    assert profiled.display_name == "Language Lover"
    assert profiled.bio == "Reader, writer, marginal-note enthusiast."
    assert profiled.avatar_data_url == "data:image/png;base64,abc123"
    assert profiled.account_visibility == "private"


def test_account_rejects_duplicate_email_and_bad_password(tmp_path):
    service = AccountService(store_path=tmp_path / "accounts.json")
    request = AccountRegisterRequest(
        email="reader@example.com",
        password="long-enough-password",
        display_name="Reader",
    )
    service.register(request)

    try:
        service.register(request)
    except AccountConflictError:
        pass
    else:
        raise AssertionError("Duplicate email should be rejected.")

    try:
        service.login(AccountLoginRequest(email="reader@example.com", password="wrong-password"))
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Invalid password should be rejected.")


def test_account_saved_folders_and_feedback_context(tmp_path):
    excerpts_path = tmp_path / "excerpts.jsonl"
    write_excerpt_records(excerpts_path)
    service = AccountService(
        store_path=tmp_path / "accounts.json",
        corpus_service=ProcessedCorpusService(excerpts_path=excerpts_path),
    )
    registered = service.register(
        AccountRegisterRequest(
            email="reader@example.com",
            password="long-enough-password",
            display_name="Reader",
        )
    )

    folders = service.list_saved_folders(registered.token)
    assert {folder.name for folder in folders} >= {"Read Later", "Annotations", "Favorites", "Poetry"}

    custom_folder = service.create_saved_folder(
        registered.token, SavedFolderCreateRequest(name="Sonnets")
    )
    updated_folder = service.save_excerpt(
        registered.token,
        custom_folder.id,
        SavedExcerptSaveRequest(excerpt_id="excerpt-1", note="Return to this."),
    )
    assert updated_folder.items[0].title == "The Sonnets"
    assert updated_folder.items[0].saved_kind == "excerpt"
    assert updated_folder.items[0].excerpt_id == "excerpt-1"
    assert updated_folder.items[0].note == "Return to this."
    saved_state = service.excerpt_state(registered.token, "excerpt-1")
    assert saved_state.saved is True
    assert saved_state.saved_folder_ids == [custom_folder.id]
    assert saved_state.saved_item_ids == ["excerpt-1"]
    assert saved_state.feedback is None

    selected_folder = service.save_excerpt(
        registered.token,
        custom_folder.id,
        SavedExcerptSaveRequest(
            excerpt_id="excerpt-1",
            save_scope="selection",
            selected_text="compare thee",
            selection_start=8,
            selection_end=20,
            highlight_color="blue",
            note="This is the central comparison.",
        ),
    )
    saved_selection = selected_folder.items[0]
    assert saved_selection.saved_kind == "selection"
    assert saved_selection.excerpt_id == "excerpt-1"
    assert saved_selection.preview == "compare thee"
    assert saved_selection.selection_start == 8
    assert saved_selection.selection_end == 20
    assert saved_selection.highlight_color == "blue"
    assert saved_selection.note == "This is the central comparison."

    selected_folder = service.save_excerpt(
        registered.token,
        custom_folder.id,
        SavedExcerptSaveRequest(
            excerpt_id="excerpt-1",
            save_scope="selection",
            selected_text="compare thee",
            selection_start=8,
            selection_end=20,
            highlight_color="green",
            note="A second annotation on the same words.",
        ),
    )
    repeated_annotations = [
        item for item in selected_folder.items if item.saved_kind == "selection"
    ]
    assert len(repeated_annotations) == 2
    assert {item.note for item in repeated_annotations} == {
        "This is the central comparison.",
        "A second annotation on the same words.",
    }

    work_folder = service.save_excerpt(
        registered.token,
        custom_folder.id,
        SavedExcerptSaveRequest(excerpt_id="excerpt-1", save_scope="work"),
    )
    assert any(item.saved_kind == "work" for item in work_folder.items)

    service.record_feedback(
        registered.token, AccountFeedbackRequest(event_type="like", excerpt_id="excerpt-2")
    )
    liked_state = service.excerpt_state(registered.token, "excerpt-2")
    assert liked_state.saved is False
    assert liked_state.feedback == "like"
    context = service.recommendation_context(registered.token)
    assert "excerpt-1" in context.positive_excerpt_ids
    assert "excerpt-2" in context.positive_excerpt_ids
    library = service.library(registered.token)
    assert len(library.annotations) == 2
    assert any(item.excerpt_id == "excerpt-2" for item in library.liked)
    assert any(item.saved_kind == "work" for item in library.saved)

    cleared_state = service.clear_feedback(registered.token, "excerpt-2")
    assert cleared_state.feedback is None
    context = service.recommendation_context(registered.token)
    assert "excerpt-2" not in context.positive_excerpt_ids
    assert "excerpt-2" not in context.negative_excerpt_ids

    service.record_feedback(
        registered.token, AccountFeedbackRequest(event_type="skip", excerpt_id="excerpt-2")
    )
    skipped_state = service.excerpt_state(registered.token, "excerpt-2")
    assert skipped_state.feedback == "skip"
    context = service.recommendation_context(registered.token)
    assert "excerpt-2" in context.negative_excerpt_ids
    assert "excerpt-2" not in context.positive_excerpt_ids

    emptied_folder = service.remove_saved_excerpt_everywhere(registered.token, "excerpt-1")
    assert emptied_folder.saved is False
    remaining_library = service.library(registered.token)
    assert len(remaining_library.annotations) == 2

    followed = service.follow_author(registered.token, "william-shakespeare")
    assert followed.name == "William Shakespeare"
    assert service.followed_authors(registered.token)[0].id == "william-shakespeare"
    assert "william-shakespeare" in service.followed_author_ids(registered.token)
    assert service.unfollow_author(registered.token, "william-shakespeare") == []


def test_account_posts_and_messages(tmp_path):
    excerpts_path = tmp_path / "gutenberg_excerpts.jsonl"
    write_excerpt_records(excerpts_path)
    service = AccountService(
        store_path=tmp_path / "accounts.json",
        corpus_service=ProcessedCorpusService(excerpts_path=excerpts_path),
    )
    first = service.register(
        AccountRegisterRequest(
            email="first@example.com",
            password="long-enough-password",
            display_name="First Reader",
        )
    )
    second = service.register(
        AccountRegisterRequest(
            email="second@example.com",
            password="long-enough-password",
            display_name="Second Reader",
        )
    )

    post = service.create_post(
        first.token,
        UserPostCreateRequest(
            title="A small beginning",
            body="The page waited, and the sentence arrived.",
            form="prose",
            media=[
                UserPostMediaRequest(
                    id="cover-image",
                    media_type="image",
                    data_url="data:image/png;base64,abc123",
                    alt_text="A page",
                    caption="Opening image.",
                )
            ],
        ),
    )
    assert post.author_display_name == "First Reader"
    assert post.word_count == 7
    assert post.media[0].caption == "Opening image."
    assert service.list_posts(first.token)[0].title == "A small beginning"
    post_excerpts = ProcessedCorpusService(
        excerpts_path=tmp_path / "gutenberg_excerpts.jsonl"
    ).list_user_post_excerpts()
    assert post_excerpts[0].id == post.id
    assert post_excerpts[0].title == "A small beginning"
    assert post_excerpts[0].media[0]["media_type"] == "image"

    try:
        service.send_message(
            first.token,
            MessageCreateRequest(
                recipient_email="second@example.com",
                subject="A passage",
                body="What do you think of this line?",
            ),
        )
    except Exception as exc:
        assert "Follow this reader" in str(exc)
    else:
        raise AssertionError("Messages should require following the recipient.")

    directory = service.follow_user(first.token, second.user.id)
    assert directory[0].followed_by_me is True
    assert directory[0].can_message is True
    assert directory[0].can_send_initial_message is True

    initial_thread = service.send_message(
        first.token,
        MessageCreateRequest(
            recipient_email="second@example.com",
            subject="A passage",
            body="What do you think of this line?",
        ),
    )
    assert initial_thread.messages[0].sender_display_name == "First Reader"

    try:
        service.send_message(
            first.token,
            MessageCreateRequest(thread_id=initial_thread.id, body="One more thought."),
        )
    except Exception as exc:
        assert "already sent one message" in str(exc)
    else:
        raise AssertionError("One-way follows should allow one initial message only.")

    profile = service.reader_profile(first.token, second.user.id)
    assert profile.reader.profile_role == "reader"
    assert profile.reader.message_limit_reached is True

    reverse_directory = service.follow_user(second.token, first.user.id)
    assert reverse_directory[0].followed_by_me is True
    assert reverse_directory[0].can_message is True

    thread = service.send_message(
        first.token,
        MessageCreateRequest(thread_id=initial_thread.id, body="What do you think now?"),
    )
    assert thread.subject == "A passage"
    assert [participant.email for participant in thread.participants] == [
        "first@example.com",
        "second@example.com",
    ]
    assert len(thread.messages) == 2

    replied = service.send_message(
        second.token,
        MessageCreateRequest(thread_id=thread.id, body="It has a nice quiet rhythm."),
    )
    assert len(replied.messages) == 3
    assert service.list_message_threads(first.token)[0].id == thread.id

    service.record_read_event(first.token, "excerpt-1", "read_complete")
    service.record_feedback(
        first.token, AccountFeedbackRequest(event_type="like", excerpt_id="excerpt-1")
    )
    service.save_excerpt(
        first.token,
        "read-later",
        SavedExcerptSaveRequest(excerpt_id="excerpt-1"),
    )
    service.save_excerpt(
        first.token,
        "annotations",
        SavedExcerptSaveRequest(
            excerpt_id="excerpt-1",
            save_scope="selection",
            selected_text="compare thee",
            selection_start=8,
            selection_end=20,
            highlight_color="pink",
            annotation_visibility="public",
            note="A friend-visible annotation.",
        ),
    )
    followed_activity = service.followed_user_activity(second.token)
    assert any(item.activity_type == "posted" for item in followed_activity)
    assert any(item.activity_type == "read" for item in followed_activity)
    assert any(
        item.activity_type == "annotated" and item.note == "A friend-visible annotation."
        for item in followed_activity
    )
    social = service.excerpt_social_context(second.token, "excerpt-1")
    assert social.like_count == 1
    assert social.save_count == 1
    assert social.annotation_count == 1
    assert social.annotations[0].selected_text == "compare thee"


def write_excerpt_records(path):
    records = [
        {
            "id": "excerpt-1",
            "work_id": "work-1",
            "gutenberg_id": "1",
            "title": "The Sonnets",
            "author": "William Shakespeare",
            "form": "poetry",
            "subjects": ["love poetry"],
            "labels": [{"label_type": "genre", "label": "romance"}],
            "text": "Shall I compare thee to a summer day?",
            "chunk_type": "full_poem",
            "word_count": 8,
        },
        {
            "id": "excerpt-2",
            "work_id": "work-2",
            "gutenberg_id": "2",
            "title": "Pride and Prejudice",
            "author": "Jane Austen",
            "form": "prose",
            "subjects": ["courtship"],
            "labels": [{"label_type": "genre", "label": "romance"}],
            "text": "It is a truth universally acknowledged.",
            "chunk_type": "excerpt",
            "word_count": 6,
        },
    ]
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
