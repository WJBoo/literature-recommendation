import type {
  AccountActivityItem,
  AccountAuthResponse,
  AccountDirectoryUser,
  AccountExcerptSocial,
  AccountExcerptState,
  AccountFeedbackEventType,
  AccountLibrary,
  AccountReaderProfile,
  AccountUser,
  AuthorProfile,
  ContinueReadingItem,
  FollowedAuthor,
  InteractionPayload,
  MessageThread,
  ListeningRecommendation,
  MusicCatalog,
  MusicPlaylist,
  MusicPreferences,
  MusicTrack,
  PoemOfTheDay,
  PostMediaItem,
  PreferenceProfile,
  ReaderItem,
  SavedHighlightColor,
  SavedItemKind,
  AnnotationVisibility,
  SavedFolder,
  SearchResults,
  UserPost,
  Work,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const RECOMMENDATION_TIMEOUT_MS = 8000;

export const emptyPreferenceProfile: PreferenceProfile = {
  genres: [],
  forms: [],
  themes: [],
  moods: [],
  authors: [],
  books: [],
};

export async function fetchRecommendations(
  preferences?: PreferenceProfile,
  options?: { maxWordCount?: number | null; limit?: number },
): Promise<Work[]> {
  const token = getAccountToken();
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/recommendations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      genres: preferences?.genres.length ? preferences.genres : ["romance", "poetry"],
      themes: preferences?.themes.length ? preferences.themes : ["love", "time"],
      moods: preferences?.moods ?? [],
      forms: preferences?.forms.length ? preferences.forms : ["poetry"],
      authors: preferences?.authors ?? [],
      books: preferences?.books ?? [],
      max_word_count: options?.maxWordCount,
      limit: options?.limit ?? 12,
    }),
  }, RECOMMENDATION_TIMEOUT_MS);

  if (!response.ok) {
    throw new Error("Unable to fetch recommendations.");
  }

  const payload = await response.json();
  return payload.items.map((item: Work) => ({
    ...item,
    tags: item.tags?.length ? item.tags : [item.form],
  }));
}

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export async function fetchPoemOfTheDay(): Promise<PoemOfTheDay> {
  const response = await fetch(`${API_BASE_URL}/api/poem-of-the-day`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load poem of the day."));
  }

  return response.json();
}

export async function fetchListeningRecommendation(itemId: string): Promise<ListeningRecommendation> {
  const response = await fetch(`${API_BASE_URL}/api/reader-items/${itemId}/listening`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load listening recommendation."));
  }

  return response.json();
}


export async function fetchMusicCatalog(options?: {
  tones?: string[];
  composers?: string[];
}): Promise<MusicCatalog> {
  const params = new URLSearchParams();
  for (const tone of options?.tones ?? []) {
    params.append("tones", tone);
  }
  for (const composer of options?.composers ?? []) {
    params.append("composers", composer);
  }
  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/music/catalog${query ? `?${query}` : ""}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load music catalog."));
  }

  return response.json();
}


export async function fetchAccountReadingProgress(): Promise<ContinueReadingItem | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/reading-progress`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function updateAccountReadingProgress(
  item: Omit<ContinueReadingItem, "saved_at">,
): Promise<ContinueReadingItem | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/reading-progress`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(item),
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function fetchAccountMusicPreferences(): Promise<MusicPreferences | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/music/preferences`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function updateAccountMusicPreferences(
  preferences: Pick<MusicPreferences, "tones" | "composers">,
): Promise<MusicPreferences | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/music/preferences`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(preferences),
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function fetchMusicPlaylists(): Promise<MusicPlaylist[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/music/playlists`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load music playlists."));
  }

  return response.json();
}

export async function createMusicPlaylist(payload: {
  name: string;
  description?: string;
}): Promise<MusicPlaylist> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/music/playlists`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to create playlist."));
  }

  return response.json();
}

export async function deleteMusicPlaylist(playlistId: string): Promise<void> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/music/playlists/${playlistId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to delete playlist."));
  }
}

export async function addTrackToMusicPlaylist(
  playlistId: string,
  track: MusicTrack,
): Promise<MusicPlaylist> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/music/playlists/${playlistId}/tracks`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(track),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to add track to playlist."));
  }

  return response.json();
}

export async function removeTrackFromMusicPlaylist(
  playlistId: string,
  trackId: string,
): Promise<MusicPlaylist> {
  const token = requireAccountToken();
  const response = await fetch(
    `${API_BASE_URL}/api/accounts/music/playlists/${playlistId}/tracks/${trackId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to remove track from playlist."));
  }

  return response.json();
}


export async function fetchReaderItem(id: string): Promise<ReaderItem> {
  const response = await fetch(`${API_BASE_URL}/api/reader-items/${id}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Unable to fetch reader item.");
  }

  return response.json();
}

export async function fetchAuthorProfile(id: string): Promise<AuthorProfile> {
  const token = getAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/authors/${id}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load author profile."));
  }

  return response.json();
}

export async function searchCatalog(query: string): Promise<SearchResults> {
  const response = await fetch(
    `${API_BASE_URL}/api/search?query=${encodeURIComponent(query)}&limit=12`,
    { cache: "no-store" },
  );

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to search."));
  }

  const payload = (await response.json()) as SearchResults;
  return {
    authors: payload.authors,
    works: payload.works.map((item) => ({ ...item, tags: [item.form] })),
  };
}

export async function logInteraction(payload: InteractionPayload): Promise<void> {
  const token = getAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/interactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      event_type: payload.eventType,
      anonymous_user_id: getAnonymousUserId(),
      session_id: getSessionId(),
      work_id: payload.workId,
      excerpt_id: payload.excerptId,
      value: payload.value,
      metadata: payload.metadata ?? {},
    }),
    keepalive: true,
  });

  if (!response.ok) {
    throw new Error("Unable to log interaction.");
  }
}

export async function fetchSavedFolders(): Promise<SavedFolder[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/saved-folders`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load saved folders."));
  }

  return response.json();
}

export async function fetchAccountLibrary(): Promise<AccountLibrary> {
  const token = getAccountToken();
  if (!token) {
    return { saved: [], annotations: [], liked: [] };
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/library`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load profile library."));
  }

  return response.json();
}

export async function fetchFollowedAuthors(): Promise<FollowedAuthor[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-authors`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load followed authors."));
  }

  return response.json();
}

export async function followAuthor(authorId: string): Promise<FollowedAuthor> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-authors/${authorId}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to follow author."));
  }

  return response.json();
}

export async function unfollowAuthor(authorId: string): Promise<FollowedAuthor[]> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-authors/${authorId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to unfollow author."));
  }

  return response.json();
}

export async function updateAccountProfile(payload: {
  displayName?: string;
  bio?: string;
  avatarDataUrl?: string | null;
  accountVisibility?: "public" | "private";
}): Promise<AccountUser> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/profile`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      display_name: payload.displayName,
      bio: payload.bio,
      avatar_data_url: payload.avatarDataUrl,
      account_visibility: payload.accountVisibility,
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to update profile."));
  }

  const user = (await response.json()) as AccountUser;
  saveAccountUser(user);
  return user;
}

export async function fetchAccountPosts(): Promise<UserPost[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/posts`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load posts."));
  }

  return response.json();
}

export async function createAccountPost(payload: {
  title: string;
  body: string;
  form: string;
  visibility: string;
  media?: PostMediaItem[];
}): Promise<UserPost> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/posts`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to publish post."));
  }

  return response.json();
}

export async function updateAccountPost(
  postId: string,
  payload: {
    title: string;
    body: string;
    form: string;
    visibility: string;
    media?: PostMediaItem[];
  },
): Promise<UserPost> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/posts/${postId}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to update post."));
  }

  return response.json();
}

export async function deleteAccountPost(postId: string): Promise<void> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/posts/${postId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to delete post."));
  }
}

export async function fetchMessageThreads(): Promise<MessageThread[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/messages`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load messages."));
  }

  return response.json();
}

export async function fetchAccountDirectory(): Promise<AccountDirectoryUser[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/directory`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load readers."));
  }

  return response.json();
}

export async function fetchReaderProfile(userId: string): Promise<AccountReaderProfile> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/directory/${userId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load reader profile."));
  }

  return response.json();
}

export async function fetchFollowedUserActivity(): Promise<AccountActivityItem[]> {
  const token = getAccountToken();
  if (!token) {
    return [];
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-users/activity`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load followed reader activity."));
  }

  return response.json();
}

export async function followReader(userId: string): Promise<AccountDirectoryUser[]> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-users/${userId}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to follow reader."));
  }

  return response.json();
}

export async function unfollowReader(userId: string): Promise<AccountDirectoryUser[]> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/followed-users/${userId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to unfollow reader."));
  }

  return response.json();
}

export async function sendAccountMessage(payload: {
  body: string;
  recipientEmail?: string;
  recipientUserId?: string;
  subject?: string;
  threadId?: string;
}): Promise<MessageThread> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      body: payload.body,
      recipient_email: payload.recipientEmail,
      recipient_user_id: payload.recipientUserId,
      subject: payload.subject,
      thread_id: payload.threadId,
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to send message."));
  }

  return response.json();
}

export async function fetchAccountExcerptState(
  excerptId: string,
): Promise<AccountExcerptState | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/excerpts/${excerptId}/state`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to load excerpt state."));
  }

  return response.json();
}

export async function fetchAccountExcerptSocial(
  excerptId: string,
): Promise<AccountExcerptSocial | null> {
  const token = getAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/excerpts/${excerptId}/social`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function createSavedFolder(payload: {
  name: string;
  description?: string;
}): Promise<SavedFolder> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/saved-folders`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to create folder."));
  }

  return response.json();
}

export async function saveExcerptToFolder(payload: {
  folderId: string;
  excerptId: string;
  saveScope?: SavedItemKind;
  selectedText?: string;
  selectionStart?: number;
  selectionEnd?: number;
  highlightColor?: SavedHighlightColor;
  annotationVisibility?: AnnotationVisibility;
  note?: string;
}): Promise<SavedFolder> {
  const token = requireAccountToken();
  const response = await fetch(
    `${API_BASE_URL}/api/accounts/saved-folders/${payload.folderId}/items`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        excerpt_id: payload.excerptId,
        save_scope: payload.saveScope ?? "excerpt",
        selected_text: payload.selectedText,
        selection_start: payload.selectionStart,
        selection_end: payload.selectionEnd,
        highlight_color: payload.highlightColor,
        annotation_visibility: payload.annotationVisibility,
        note: payload.note,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to save excerpt."));
  }

  return response.json();
}

export async function removeSavedExcerptEverywhere(excerptId: string): Promise<AccountExcerptState> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/excerpts/${excerptId}/saved`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to remove saved item."));
  }

  return response.json();
}

export async function removeSavedExcerpt(payload: {
  folderId: string;
  excerptId: string;
}): Promise<SavedFolder> {
  const token = requireAccountToken();
  const response = await fetch(
    `${API_BASE_URL}/api/accounts/saved-folders/${payload.folderId}/items/${payload.excerptId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to remove excerpt."));
  }

  return response.json();
}

export async function recordAccountFeedback(payload: {
  eventType: AccountFeedbackEventType;
  excerptId: string;
}): Promise<void> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/feedback`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event_type: payload.eventType,
      excerpt_id: payload.excerptId,
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to save feedback."));
  }
}

export async function clearAccountFeedback(excerptId: string): Promise<AccountExcerptState> {
  const token = requireAccountToken();
  const response = await fetch(`${API_BASE_URL}/api/accounts/feedback/${excerptId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to clear feedback."));
  }

  return response.json();
}

export async function registerAccount(payload: {
  email: string;
  password: string;
  displayName: string;
  preferences: PreferenceProfile;
}): Promise<AccountAuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/accounts/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
      display_name: payload.displayName,
      preferences: payload.preferences,
    }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to create account."));
  }

  const account = (await response.json()) as AccountAuthResponse;
  saveAccountSession(account);
  return account;
}

export async function loginAccount(payload: {
  email: string;
  password: string;
}): Promise<AccountAuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/accounts/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to sign in."));
  }

  const account = (await response.json()) as AccountAuthResponse;
  saveAccountSession(account);
  return account;
}

export async function fetchCurrentAccount(): Promise<AccountUser | null> {
  const token = getAccountToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!response.ok) {
    clearAccountSession();
    return null;
  }

  const user = (await response.json()) as AccountUser;
  saveAccountUser(user);
  return user;
}

export async function updateAccountPreferences(
  preferences: PreferenceProfile,
): Promise<AccountUser> {
  const token = getAccountToken();
  if (!token) {
    throw new Error("Create an account or sign in before saving preferences.");
  }

  const response = await fetch(`${API_BASE_URL}/api/accounts/preferences`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ preferences }),
  });

  if (!response.ok) {
    throw new Error(await readApiError(response, "Unable to save preferences."));
  }

  const user = (await response.json()) as AccountUser;
  saveAccountUser(user);
  return user;
}

export function getStoredAccountUser(): AccountUser | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem("literature_account_user");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AccountUser;
  } catch {
    return null;
  }
}

export function getStoredPreferenceProfile(): PreferenceProfile | null {
  return getStoredAccountUser()?.preferences ?? null;
}

export function clearAccountSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem("literature_account_token");
  window.localStorage.removeItem("literature_account_user");
}

function getAnonymousUserId(): string {
  return getOrCreateBrowserId("literature_anonymous_user_id", "anon");
}

export function getAccountToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("literature_account_token");
}

function requireAccountToken(): string {
  const token = getAccountToken();
  if (!token) {
    throw new Error("Sign in before saving this to your profile.");
  }
  return token;
}

function saveAccountSession(account: AccountAuthResponse): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem("literature_account_token", account.token);
  saveAccountUser(account.user);
}

function saveAccountUser(user: AccountUser): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem("literature_account_user", JSON.stringify(user));
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : fallback;
  } catch {
    return fallback;
  }
}

function getSessionId(): string {
  return getOrCreateBrowserId("literature_session_id", "session");
}

function getOrCreateBrowserId(key: string, prefix: string): string {
  if (typeof window === "undefined") {
    return `${prefix}-server`;
  }

  const existing = window.localStorage.getItem(key);
  if (existing) {
    return existing;
  }

  const value = `${prefix}-${crypto.randomUUID()}`;
  window.localStorage.setItem(key, value);
  return value;
}
