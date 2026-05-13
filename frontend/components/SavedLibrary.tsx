"use client";

import { FolderPlus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  createSavedFolder,
  fetchAccountLibrary,
  fetchSavedFolders,
  removeSavedExcerpt,
} from "../lib/api";
import { authorId } from "../lib/authorIds";
import type { AccountLibrary, SavedExcerpt, SavedFolder } from "../lib/types";

type LibrarySectionId = "saved" | "annotations" | "liked";
type FolderBackedItem = SavedExcerpt & { folderId?: string };

const initialLibrary: AccountLibrary = { saved: [], annotations: [], liked: [] };

export function SavedLibrary() {
  const [folders, setFolders] = useState<SavedFolder[]>([]);
  const [library, setLibrary] = useState<AccountLibrary>(initialLibrary);
  const [newFolderName, setNewFolderName] = useState("");
  const [expandedSections, setExpandedSections] = useState<Record<LibrarySectionId, boolean>>({
    saved: false,
    annotations: false,
    liked: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchSavedFolders(), fetchAccountLibrary()])
      .then(([folderItems, accountLibrary]) => {
        if (mounted) {
          setFolders(folderItems);
          setLibrary(accountLibrary);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Unable to load profile library.");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const savedItems = useMemo(() => flattenFolderItems(folders, "saved"), [folders]);
  const annotationItems = useMemo(() => flattenFolderItems(folders, "annotations"), [folders]);

  async function handleCreateFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!newFolderName.trim()) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const folder = await createSavedFolder({ name: newFolderName });
      setFolders((current) => [...current, folder]);
      setNewFolderName("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create folder.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(folderId: string, itemId: string) {
    setError(null);
    try {
      const updatedFolder = await removeSavedExcerpt({ folderId, excerptId: itemId });
      setFolders((current) =>
        current.map((folder) => (folder.id === updatedFolder.id ? updatedFolder : folder)),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to remove item.");
    }
  }

  function toggleSection(sectionId: LibrarySectionId) {
    setExpandedSections((current) => ({ ...current, [sectionId]: !current[sectionId] }));
  }

  const folderCreateForm = (
    <form className="folder-create" onSubmit={handleCreateFolder}>
      <label className="sr-only" htmlFor="new-folder-name">
        New folder name
      </label>
      <input
        className="input folder-name-input"
        id="new-folder-name"
        onChange={(event) => setNewFolderName(event.target.value)}
        placeholder="New folder"
        value={newFolderName}
      />
      <button className="secondary-button" disabled={saving} type="submit">
        <FolderPlus size={18} aria-hidden="true" />
        {saving ? "Adding" : "Add"}
      </button>
    </form>
  );

  return (
    <div className="profile-library">
      {error ? <p className="form-message error-message">{error}</p> : null}
      <LibrarySection
        action={folderCreateForm}
        emptyText="No saved works or pieces yet."
        expanded={expandedSections.saved}
        id="saved"
        items={savedItems}
        loading={loading}
        onRemove={handleRemove}
        onToggle={toggleSection}
        subtitle="Works and pieces you saved for later reading."
        title="Saved"
      />
      <LibrarySection
        emptyText="No annotations yet."
        expanded={expandedSections.annotations}
        id="annotations"
        items={annotationItems}
        loading={loading}
        onRemove={handleRemove}
        onToggle={toggleSection}
        subtitle="Highlighted passages with your comments."
        title="Annotations"
      />
      <LibrarySection
        emptyText="No liked pieces yet."
        expanded={expandedSections.liked}
        id="liked"
        items={library.liked}
        loading={loading}
        onToggle={toggleSection}
        subtitle="Pieces you marked as liked."
        title="Liked"
      />
    </div>
  );
}

function LibrarySection({
  action,
  emptyText,
  expanded,
  id,
  items,
  loading,
  onRemove,
  onToggle,
  subtitle,
  title,
}: {
  action?: ReactNode;
  emptyText: string;
  expanded: boolean;
  id: LibrarySectionId;
  items: FolderBackedItem[];
  loading: boolean;
  onRemove?: (folderId: string, itemId: string) => void;
  onToggle: (sectionId: LibrarySectionId) => void;
  subtitle: string;
  title: string;
}) {
  const visibleItems = expanded ? items : items.slice(0, 3);
  return (
    <section className="form-surface profile-library-section">
      <div className="form-heading">
        <div>
          <h2>{title}</h2>
          <p className="muted">
            {subtitle} {items.length ? `${items.length} total.` : ""}
          </p>
        </div>
        {action}
      </div>

      {loading ? <p className="muted">Loading {title.toLowerCase()}.</p> : null}
      {!loading && !items.length ? <p className="muted">{emptyText}</p> : null}
      {visibleItems.length ? (
        <div className="saved-item-list">
          {visibleItems.map((item) => (
            <div
              className={item.folderId && onRemove ? "saved-item" : "saved-item saved-item-readonly"}
              key={`${id}-${item.folderId ?? "account"}-${item.id}`}
            >
              <Link className="saved-item-link" href={`/work/${item.excerpt_id}`}>
                <span className="saved-item-title">{item.title}</span>
                <span className="muted">
                  {savedKindLabel(item.saved_kind)} · {item.form} ·{" "}
                  {item.word_count} words
                </span>
                {renderItemDetail(item)}
              </Link>
              <Link className="saved-item-author-link" href={`/authors/${authorId(item.author)}`}>
                {item.author}
              </Link>
              {item.folderId && onRemove ? (
                <button
                  aria-label={`Remove ${item.title}`}
                  className="icon-button"
                  onClick={() => void onRemove(item.folderId as string, item.id)}
                  type="button"
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {items.length > 3 ? (
        <button className="secondary-button quiet-button" onClick={() => onToggle(id)} type="button">
          {expanded ? "Show top 3" : "See all"}
        </button>
      ) : null}
    </section>
  );
}

function flattenFolderItems(
  folders: SavedFolder[],
  section: Exclude<LibrarySectionId, "liked">,
): FolderBackedItem[] {
  const items = folders.flatMap((folder) =>
    folder.items.map((item) => ({ ...item, folderId: folder.id })),
  );
  const filtered =
    section === "annotations"
      ? items.filter((item) => item.saved_kind === "selection")
      : items.filter((item) => item.saved_kind !== "selection");
  return filtered.sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

function renderItemDetail(item: FolderBackedItem) {
  if (item.saved_kind === "selection") {
    return (
      <span className="annotation-detail">
        <span>
          <strong>Text:</strong> “{item.selected_text ?? item.preview}”
        </span>
        <span>
          <strong>Comment:</strong> {item.note || "No comment added."}
        </span>
      </span>
    );
  }
  return <span>{item.preview}</span>;
}

function savedKindLabel(kind: string): string {
  if (kind === "work") {
    return "Work";
  }
  if (kind === "selection") {
    return "Annotation";
  }
  return "Piece";
}
