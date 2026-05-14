"use client";

import {
  Bookmark,
  Heart,
  MessageSquare,
  SkipForward,
  ThumbsDown,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useState, type ReactNode } from "react";
import {
  clearAccountFeedback,
  fetchAccountExcerptSocial,
  fetchAccountExcerptState,
  fetchSavedFolders,
  getAccountToken,
  logInteraction,
  recordAccountFeedback,
  removeSavedExcerptEverywhere,
  saveExcerptToFolder,
} from "../lib/api";
import { fetchRecommendedAlternative } from "../lib/recommendationNavigation";
import type {
  AccountFeedbackEventType,
  AccountExcerptSocial,
  AnnotationVisibility,
  InteractionEventType,
  SavedHighlightColor,
  SavedFolder,
  SavedItemKind,
} from "../lib/types";

type InteractionButtonsProps = {
  excerptId: string;
  workId: string;
  workTitle: string;
  author?: string | null;
  hasSiblingExcerpts?: boolean;
  children?: ReactNode;
};

type ActionState = "idle" | "liked" | "saved" | "disliked" | "passed";
type FeedbackState = AccountFeedbackEventType | null;
type ReaderSelection = { text: string; start: number; end: number };
type ActivePanel = "save" | "annotate" | "social" | null;

const actions: Array<{
  eventType: InteractionEventType;
  label: string;
  nextState: ActionState;
  Icon: LucideIcon;
}> = [
  { eventType: "like", label: "Like", nextState: "liked", Icon: Heart },
  { eventType: "save", label: "Save", nextState: "saved", Icon: Bookmark },
  { eventType: "annotate", label: "Annotate", nextState: "idle", Icon: MessageSquare },
  { eventType: "dislike", label: "Dislike", nextState: "disliked", Icon: ThumbsDown },
  { eventType: "skip", label: "Skip to new book", nextState: "passed", Icon: SkipForward },
];

const highlightColors: Array<{ value: SavedHighlightColor; label: string }> = [
  { value: "yellow", label: "Yellow" },
  { value: "green", label: "Green" },
  { value: "blue", label: "Blue" },
  { value: "pink", label: "Pink" },
  { value: "lavender", label: "Lavender" },
];

export function InteractionButtons({
  author,
  children,
  excerptId,
  hasSiblingExcerpts = false,
  workId,
  workTitle,
}: InteractionButtonsProps) {
  const router = useRouter();
  const [feedbackState, setFeedbackState] = useState<FeedbackState>(null);
  const [isSaved, setIsSaved] = useState(false);
  const [pendingEvent, setPendingEvent] = useState<InteractionEventType | null>(null);
  const [folders, setFolders] = useState<SavedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState("read-later");
  const [status, setStatus] = useState<string | null>(null);
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [highlightColor, setHighlightColor] = useState<SavedHighlightColor>("yellow");
  const [annotationVisibility, setAnnotationVisibility] = useState<AnnotationVisibility>("public");
  const [highlightComment, setHighlightComment] = useState("");
  const [draftSelection, setDraftSelection] = useState<ReaderSelection | null>(null);
  const [socialContext, setSocialContext] = useState<AccountExcerptSocial | null>(null);

  useEffect(() => {
    void logInteraction({
      eventType: "read_start",
      workId,
      excerptId,
      metadata: { surface: "reader", workTitle },
    }).catch(() => {
      // Interaction logging should never block reading.
    });
  }, [excerptId, workId, workTitle]);

  useEffect(() => {
    let mounted = true;
    void Promise.all([
      fetchSavedFolders(),
      fetchAccountExcerptState(excerptId),
      fetchAccountExcerptSocial(excerptId),
    ])
      .then(([items, accountState, social]) => {
        if (!mounted) {
          return;
        }
        const savedFolderIds = accountState?.saved_folder_ids ?? [];
        setFolders(items);
        setSelectedFolderId(savedFolderIds[0] ?? items[0]?.id ?? "read-later");
        setIsSaved(folderListContainsSavableItem(items, excerptId, workId));
        setFeedbackState(accountState?.feedback ?? null);
        setSocialContext(social);
        setActivePanel(null);
      })
      .catch(() => {
        if (mounted) {
          setFolders([]);
          setIsSaved(false);
          setFeedbackState(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, [excerptId, workId]);

  async function refreshSocialContext() {
    const social = await fetchAccountExcerptSocial(excerptId);
    setSocialContext(social);
  }

  useEffect(() => {
    if (activePanel !== "annotate") {
      return;
    }

    function captureSelection() {
      const selection = getReaderSelection();
      if (selection) {
        setDraftSelection(selection);
      }
    }

    document.addEventListener("selectionchange", captureSelection);
    captureSelection();
    return () => {
      document.removeEventListener("selectionchange", captureSelection);
    };
  }, [activePanel]);

  async function handleAction(eventType: InteractionEventType) {
    if (eventType === "save") {
      await handleSaveClick();
      return;
    }
    if (eventType === "annotate") {
      await handleAnnotateClick();
      return;
    }

    setPendingEvent(eventType);
    setStatus(null);
    try {
      await logInteraction({
        eventType,
        workId,
        excerptId,
        metadata: { surface: "reader", workTitle },
      });
      if (eventType === "skip") {
        if (getAccountToken()) {
          await recordAccountFeedback({ eventType: "skip", excerptId });
        }
        setFeedbackState("skip");
        const target = await fetchRecommendedAlternative({
          currentExcerptId: excerptId,
          currentWorkId: workId,
          currentWorkTitle: workTitle,
          currentAuthor: author,
        });
        if (target) {
          router.push(`/work/${target.id}`);
          return;
        }
        setStatus("No different recommended book is available yet.");
      } else if (eventType === "like" || eventType === "dislike") {
        const targetFeedback = eventType as AccountFeedbackEventType;
        if (feedbackState === targetFeedback) {
          if (getAccountToken()) {
            const updatedState = await clearAccountFeedback(excerptId);
            setFeedbackState(updatedState.feedback);
            await refreshSocialContext();
          } else {
            setFeedbackState(null);
            setStatus("Sign in to save feedback for recommendations.");
          }
          return;
        }

        if (getAccountToken()) {
          await recordAccountFeedback({
            eventType: targetFeedback,
            excerptId,
          });
          setFeedbackState(targetFeedback);
          await refreshSocialContext();
        } else {
          setFeedbackState(targetFeedback);
          setStatus("Sign in to use this feedback for recommendations.");
        }
      }
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to save that action.");
    } finally {
      setPendingEvent(null);
    }
  }

  async function handleSaveClick() {
    setStatus(null);
    if (!getAccountToken()) {
      setActivePanel(null);
      setStatus("Sign in to save to your library.");
      return;
    }

    if (!isSaved && !hasSiblingExcerpts) {
      await handleSaveChoice("excerpt");
      return;
    }

    if (!isSaved) {
      setActivePanel((current) => (current === "save" ? null : "save"));
      return;
    }

    const confirmed = window.confirm(
      "Remove saved entries for this item from your library?",
    );
    if (!confirmed) {
      return;
    }

    setPendingEvent("save");
    try {
      await removeSavedExcerptEverywhere(excerptId);
      setIsSaved(false);
      setFolders((currentFolders) =>
        removeSavedItemsForCurrentReader(currentFolders, excerptId, workId, false),
      );
      setActivePanel(null);
      setDraftSelection(null);
      setHighlightComment("");
      setStatus("Removed from your library.");
      await refreshSocialContext();
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to remove that saved item.");
    } finally {
      setPendingEvent(null);
    }
  }

  async function handleAnnotateClick() {
    setStatus(null);
    if (!getAccountToken()) {
      setActivePanel(null);
      setStatus("Sign in to annotate passages.");
      return;
    }

    const selection = getReaderSelection();
    if (selection) {
      setDraftSelection(selection);
    }
    setActivePanel((current) => (current === "annotate" ? null : "annotate"));
  }

  async function handleSaveChoice(saveScope: Exclude<SavedItemKind, "selection">) {
    setPendingEvent("save");
    setStatus(null);
    try {
      await logInteraction({
        eventType: "save",
        workId,
        excerptId,
        metadata: { surface: "reader", workTitle, saveScope },
      });

      const targetFolderId = selectedFolderId || folders[0]?.id || "read-later";
      const updatedFolder = await saveExcerptToFolder({
        folderId: targetFolderId,
        excerptId,
        saveScope,
      });
      setFolders((currentFolders) => replaceFolder(currentFolders, updatedFolder));
      setSelectedFolderId(updatedFolder.id);
      setIsSaved(true);
      setActivePanel(null);
      setStatus(saveStatus(saveScope));
      await refreshSocialContext();
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to save that item.");
    } finally {
      setPendingEvent(null);
    }
  }

  async function handleAnnotationSave() {
    setPendingEvent("annotate");
    setStatus(null);
    try {
      const selection = getReaderSelection() ?? draftSelection;
      const selectedText = selection?.text;
      if (!selectedText) {
        setStatus("Highlight text in the passage first.");
        return;
      }

      await logInteraction({
        eventType: "annotate",
        workId,
        excerptId,
        metadata: { surface: "reader", workTitle, saveScope: "selection" },
      });

      const targetFolderId =
        folders.find((folder) => folder.id === "annotations")?.id ??
        selectedFolderId ??
        folders[0]?.id ??
        "read-later";
      const updatedFolder = await saveExcerptToFolder({
        folderId: targetFolderId,
        excerptId,
        saveScope: "selection",
        selectedText,
        selectionStart: selection?.start,
        selectionEnd: selection?.end,
        highlightColor,
        annotationVisibility,
        note: cleanHighlightComment(highlightComment),
      });
      setFolders((currentFolders) => replaceFolder(currentFolders, updatedFolder));
      setActivePanel(null);
      setDraftSelection(null);
      setHighlightComment("");
      notifySavedHighlightsChanged(excerptId);
      setStatus("Annotation saved.");
      await refreshSocialContext();
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to save that annotation.");
    } finally {
      setPendingEvent(null);
    }
  }

  return (
    <div className="reader-actions" aria-label="Reader actions">
      {actions.map(({ eventType, label, nextState, Icon }) => {
        const isActive = actionIsActive(eventType, nextState, feedbackState, isSaved);
        if (eventType === "save") {
          return (
            <div className="reader-action-cluster" key={eventType}>
              <button
                className={isActive ? "secondary-button active-button" : "secondary-button"}
                disabled={pendingEvent !== null}
                aria-pressed={isActive}
                onClick={() => void handleAction(eventType)}
                type="button"
              >
                <Icon size={18} aria-hidden="true" />
                {pendingEvent === eventType ? pendingLabel(eventType) : label}
              </button>
              {activePanel === "save" && hasSiblingExcerpts ? (
                <div className="save-options-popover" aria-label="Save options" role="group">
                  {folders.length ? (
                    <select
                      aria-label="Saved folder"
                      className="folder-select"
                      onChange={(event) => setSelectedFolderId(event.target.value)}
                      value={selectedFolderId}
                    >
                      {folders.map((folder) => (
                        <option key={folder.id} value={folder.id}>
                          {folder.name}
                        </option>
                      ))}
                    </select>
                  ) : null}
                  <div className="save-option-buttons">
                    <button
                      className="secondary-button"
                      disabled={pendingEvent !== null}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => void handleSaveChoice("work")}
                      type="button"
                    >
                      Whole work
                    </button>
                    <button
                      className="secondary-button"
                      disabled={pendingEvent !== null}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => void handleSaveChoice("excerpt")}
                      type="button"
                    >
                      Current piece
                    </button>
                    <button
                      className="secondary-button quiet-button"
                      disabled={pendingEvent !== null}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setActivePanel(null);
                      }}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          );
        }
        return (
          <Fragment key={eventType}>
            <div className="reader-action-cluster">
              <button
                className={isActive ? "secondary-button active-button" : "secondary-button"}
                disabled={pendingEvent !== null}
                aria-pressed={isActive}
                onClick={() => void handleAction(eventType)}
                type="button"
              >
                <Icon size={18} aria-hidden="true" />
                {pendingEvent === eventType ? pendingLabel(eventType) : label}
              </button>
            </div>
            {eventType === "annotate" ? children : null}
          </Fragment>
        );
      })}
      <button
        className={activePanel === "social" ? "secondary-button active-button" : "secondary-button"}
        onClick={() => setActivePanel((current) => (current === "social" ? null : "social"))}
        type="button"
      >
        <UsersRound size={18} aria-hidden="true" />
        Who else
        {socialContext ? ` (${socialContext.like_count}/${socialContext.save_count})` : ""}
      </button>
      {activePanel === "annotate" ? (
        <div className="save-options-panel" aria-label="Annotation options" role="group">
          <div className="highlight-color-picker" aria-label="Highlight color">
            {highlightColors.map((color) => (
              <button
                aria-label={`${color.label} highlight`}
                aria-pressed={highlightColor === color.value}
                className={
                  highlightColor === color.value
                    ? `highlight-swatch highlight-${color.value} selected`
                    : `highlight-swatch highlight-${color.value}`
                }
                key={color.value}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => setHighlightColor(color.value)}
                title={`${color.label} highlight`}
                type="button"
              />
            ))}
          </div>
          <label className="sr-only" htmlFor={`highlight-comment-${excerptId}`}>
            Annotation comment
          </label>
          <textarea
            className="highlight-comment-input"
            id={`highlight-comment-${excerptId}`}
            onChange={(event) => setHighlightComment(event.target.value)}
            placeholder="Comment on highlighted text"
            rows={2}
            value={highlightComment}
          />
          <label className="annotation-visibility-field">
            Visibility
            <select
              className="folder-select"
              onChange={(event) =>
                setAnnotationVisibility(event.target.value === "private" ? "private" : "public")
              }
              value={annotationVisibility}
            >
              <option value="public">Public to friends</option>
              <option value="private">Private</option>
            </select>
          </label>
          <button
            className="secondary-button"
            disabled={pendingEvent !== null}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => void handleAnnotationSave()}
            type="button"
          >
            Save annotation
          </button>
          <button
            className="secondary-button quiet-button"
            disabled={pendingEvent !== null}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              setActivePanel(null);
              setDraftSelection(null);
              setHighlightComment("");
            }}
            type="button"
          >
            Cancel
          </button>
        </div>
      ) : null}
      {activePanel === "social" ? (
        <div className="save-options-panel social-context-panel" aria-label="Social context">
          <SocialContextList title="Liked by" users={socialContext?.liked_by ?? []} />
          <SocialContextList title="Saved/shared by" users={socialContext?.saved_by ?? []} />
        </div>
      ) : null}
      {status ? <p className="reader-action-status muted">{status}</p> : null}
    </div>
  );
}

function SocialContextList({
  title,
  users,
}: {
  title: string;
  users: NonNullable<AccountExcerptSocial["liked_by"]>;
}) {
  return (
    <div className="social-context-list">
      <strong>
        {title} ({users.length})
      </strong>
      {users.length ? (
        <p className="muted">{users.map((user) => user.display_name).join(", ")}</p>
      ) : (
        <p className="muted">No visible readers yet.</p>
      )}
    </div>
  );
}

function pendingLabel(eventType: InteractionEventType): string {
  if (eventType === "skip") {
    return "Finding";
  }
  return eventType === "annotate" ? "Annotating" : "Saving";
}

function actionIsActive(
  eventType: InteractionEventType,
  nextState: ActionState,
  feedbackState: FeedbackState,
  isSaved: boolean,
): boolean {
  if (eventType === "save") {
    return isSaved;
  }
  if (nextState === "liked") {
    return feedbackState === "like";
  }
  if (nextState === "disliked") {
    return feedbackState === "dislike";
  }
  if (nextState === "passed") {
    return feedbackState === "skip";
  }
  return false;
}

function folderListContainsSavableItem(
  folders: SavedFolder[],
  excerptId: string,
  workId: string,
): boolean {
  return folders.some((folder) =>
    folder.items.some(
      (item) =>
        item.saved_kind !== "selection" &&
        (item.id === excerptId ||
          item.excerpt_id === excerptId ||
          item.id === `${workId}-whole-work`),
    ),
  );
}

function replaceFolder(folders: SavedFolder[], updatedFolder: SavedFolder): SavedFolder[] {
  if (!folders.some((folder) => folder.id === updatedFolder.id)) {
    return [updatedFolder, ...folders];
  }
  return folders.map((folder) => (folder.id === updatedFolder.id ? updatedFolder : folder));
}

function removeSavedItemsForCurrentReader(
  folders: SavedFolder[],
  excerptId: string,
  workId: string,
  includeAnnotations: boolean,
): SavedFolder[] {
  return folders.map((folder) => ({
    ...folder,
    items: folder.items.filter(
      (item) =>
        (!includeAnnotations && item.saved_kind === "selection") ||
        (item.id !== excerptId &&
          item.excerpt_id !== excerptId &&
          item.id !== `${workId}-whole-work`),
    ),
  }));
}

function getReaderSelection(): ReaderSelection | null {
  const selection = window.getSelection();
  const readerBody = document.querySelector(".reader-body");
  if (!selection || !readerBody || selection.rangeCount === 0) {
    return null;
  }

  const range = selection.getRangeAt(0);
  if (
    !readerBody.contains(range.commonAncestorContainer) &&
    range.commonAncestorContainer !== readerBody
  ) {
    return null;
  }

  const rawText = range.toString();
  const leadingWhitespace = rawText.length - rawText.trimStart().length;
  const trailingWhitespace = rawText.length - rawText.trimEnd().length;
  const selectedText = rawText.trim().replace(/\s+/g, " ");
  if (!selectedText) {
    return null;
  }

  const prefixRange = range.cloneRange();
  prefixRange.selectNodeContents(readerBody);
  prefixRange.setEnd(range.startContainer, range.startOffset);
  const start = prefixRange.toString().length + leadingWhitespace;
  const end = start + rawText.length - leadingWhitespace - trailingWhitespace;
  return { text: selectedText, start, end };
}

function cleanHighlightComment(comment: string): string | undefined {
  const cleaned = comment.trim();
  return cleaned.length ? cleaned : undefined;
}

function saveStatus(saveScope: SavedItemKind): string {
  if (saveScope === "work") {
    return "Saved the whole work to your library.";
  }
  return "Saved the current piece to your library.";
}

function notifySavedHighlightsChanged(excerptId: string): void {
  window.dispatchEvent(
    new CustomEvent("saved-highlights-changed", {
      detail: { excerptId },
    }),
  );
}
