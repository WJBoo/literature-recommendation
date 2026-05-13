from app.db.base import Base
import app.models  # noqa: F401
from sqlalchemy.orm import configure_mappers


def test_database_metadata_includes_core_storage_tables():
    configure_mappers()

    expected_tables = {
        "works",
        "excerpts",
        "excerpt_classifications",
        "excerpt_embeddings",
        "work_embeddings",
        "user_profile_embeddings",
        "users",
        "user_preferences",
        "interactions",
        "saved_folders",
        "saved_excerpts",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_excerpt_and_user_storage_columns_are_present():
    excerpts = Base.metadata.tables["excerpts"]
    users = Base.metadata.tables["users"]
    saved_excerpts = Base.metadata.tables["saved_excerpts"]

    assert "external_id" in excerpts.c
    assert "excerpt_index" in excerpts.c
    assert "source_metadata" in excerpts.c
    assert "profile_metadata" in users.c
    assert "folder_id" in saved_excerpts.c
    assert "saved_item_key" in saved_excerpts.c
    assert "saved_kind" in saved_excerpts.c
    assert "selected_text" in saved_excerpts.c
    assert "selection_start" in saved_excerpts.c
    assert "selection_end" in saved_excerpts.c
    assert "highlight_color" in saved_excerpts.c
