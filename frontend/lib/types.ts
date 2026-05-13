export type Work = {
  id: string;
  title: string;
  author: string;
  form: string;
  reason: string;
  excerpt: string;
  tags: string[];
  work_title?: string | null;
  section_title?: string | null;
  excerpt_label?: string | null;
};

export type PoemOfTheDay = {
  date: string;
  work: Work;
};

export type MusicTrack = {
  id: string;
  title: string;
  composer: string;
  performer: string;
  duration: string;
  tone_tags: string[];
  audio_url: string;
  source_url: string;
  license: string;
  reason: string;
};

export type ListeningRecommendation = {
  item_id: string;
  title: string;
  author: string;
  tone: string;
  tone_label: string;
  summary: string;
  tracks: MusicTrack[];
};


export type MusicCatalog = {
  tones: Record<string, string>;
  composers: string[];
  tracks: MusicTrack[];
};

export type ContinueReadingItem = {
  id: string;
  work_id: string;
  title: string;
  author: string;
  form: string;
  work_title?: string | null;
  section_title?: string | null;
  excerpt_label?: string | null;
  saved_at: string;
};



export type MusicPreferences = {
  tones: string[];
  composers: string[];
  updated_at?: string | null;
};

export type MusicPlaylistTrack = MusicTrack & {
  added_at: string;
};

export type MusicPlaylist = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  tracks: MusicPlaylistTrack[];
};

export type ReaderItem = {
  id: string;
  work_id: string;
  title: string;
  author: string;
  form: string;
  text: string;
  chunk_type: string;
  word_count: number;
  subjects: string[];
  work_title?: string | null;
  section_title?: string | null;
  section_excerpt_index?: number | null;
  section_excerpt_count?: number | null;
  excerpt_label?: string | null;
  media?: PostMediaItem[];
  first_item?: ReaderNavigationItem | null;
  previous_item?: ReaderNavigationItem | null;
  next_item?: ReaderNavigationItem | null;
};

export type PostMediaItem = {
  id: string;
  media_type: "image" | "video";
  data_url: string;
  alt_text: string | null;
  caption: string | null;
};

export type ReaderNavigationItem = {
  id: string;
  title: string;
  author: string;
  form: string;
  work_title?: string | null;
};

export type RecommendationSection = {
  title: string;
  subtitle: string;
  works: Work[];
};

export type PreferenceProfile = {
  genres: string[];
  forms: string[];
  themes: string[];
  moods: string[];
  authors: string[];
  books: string[];
};

export type AccountUser = {
  id: string;
  email: string;
  display_name: string;
  preferences: PreferenceProfile;
  bio: string | null;
  avatar_data_url: string | null;
  account_visibility: "public" | "private";
  created_at: string;
  updated_at: string;
};

export type AccountDirectoryUser = {
  id: string;
  display_name: string;
  bio: string | null;
  avatar_data_url: string | null;
  account_visibility: "public" | "private";
  profile_role: "reader" | "writer" | "writer_reader";
  followed_by_me: boolean;
  follows_me: boolean;
  can_message: boolean;
  can_send_initial_message: boolean;
  message_limit_reached: boolean;
  post_count: number;
};

export type AccountAuthResponse = {
  token: string;
  user: AccountUser;
};

export type AccountFeedbackEventType = "like" | "dislike" | "skip";

export type AccountExcerptState = {
  excerpt_id: string;
  saved: boolean;
  saved_folder_ids: string[];
  saved_item_ids: string[];
  feedback: AccountFeedbackEventType | null;
};

export type SavedItemKind = "work" | "excerpt" | "selection";
export type SavedHighlightColor = "yellow" | "green" | "blue" | "pink" | "lavender";
export type AnnotationVisibility = "private" | "public";

export type SavedExcerpt = {
  id: string;
  excerpt_id: string;
  saved_kind: SavedItemKind;
  title: string;
  author: string;
  form: string;
  preview: string;
  word_count: number;
  selected_text: string | null;
  selection_start: number | null;
  selection_end: number | null;
  highlight_color: SavedHighlightColor | null;
  annotation_visibility: AnnotationVisibility | null;
  note: string | null;
  created_at: string;
};

export type SavedFolder = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  items: SavedExcerpt[];
};

export type AccountLibrary = {
  saved: SavedExcerpt[];
  annotations: SavedExcerpt[];
  liked: SavedExcerpt[];
};

export type AccountActivityType = "posted" | "saved" | "liked" | "annotated" | "read";

export type AccountActivityItem = {
  id: string;
  activity_type: AccountActivityType;
  user_id: string;
  user_display_name: string;
  title: string;
  author: string | null;
  excerpt_id: string | null;
  post_id: string | null;
  preview: string;
  selected_text: string | null;
  note: string | null;
  created_at: string;
};

export type AccountReaderProfile = {
  reader: AccountDirectoryUser;
  posts: UserPost[];
  activity: AccountActivityItem[];
  can_view_activity: boolean;
};

export type AccountSocialUser = {
  id: string;
  display_name: string;
  avatar_data_url: string | null;
  profile_role: "reader" | "writer" | "writer_reader";
};

export type AccountPublicAnnotation = {
  id: string;
  excerpt_id: string;
  user: AccountSocialUser;
  selected_text: string;
  selection_start: number | null;
  selection_end: number | null;
  highlight_color: SavedHighlightColor;
  note: string | null;
  created_at: string;
};

export type AccountExcerptSocial = {
  excerpt_id: string;
  like_count: number;
  save_count: number;
  annotation_count: number;
  liked_by: AccountSocialUser[];
  saved_by: AccountSocialUser[];
  annotations: AccountPublicAnnotation[];
};

export type FollowedAuthor = {
  id: string;
  name: string;
  followed_at: string;
};

export type AuthorWork = {
  work_id: string;
  title: string;
  form: string;
  excerpt_count: number;
  first_excerpt_id: string;
  subjects: string[];
};

export type AuthorExcerpt = {
  id: string;
  title: string;
  work_title: string | null;
  form: string;
  preview: string;
  word_count: number;
  subjects: string[];
};

export type AuthorProfile = {
  id: string;
  name: string;
  forms: string[];
  subjects: string[];
  work_count: number;
  excerpt_count: number;
  works: AuthorWork[];
  sample_excerpts: AuthorExcerpt[];
  followed: boolean;
};

export type AuthorSearchResult = {
  id: string;
  name: string;
  forms: string[];
  work_count: number;
  excerpt_count: number;
};

export type SearchResults = {
  authors: AuthorSearchResult[];
  works: Work[];
};

export type UserPost = {
  id: string;
  author_user_id: string;
  author_display_name: string;
  title: string;
  body: string;
  form: string;
  visibility: "public" | "followers" | "private";
  word_count: number;
  media: PostMediaItem[];
  created_at: string;
  updated_at: string;
};

export type MessageParticipant = {
  id: string;
  display_name: string;
  email: string;
  avatar_data_url: string | null;
};

export type Message = {
  id: string;
  thread_id: string;
  sender_user_id: string;
  sender_display_name: string;
  body: string;
  created_at: string;
};

export type MessageThread = {
  id: string;
  subject: string | null;
  participants: MessageParticipant[];
  messages: Message[];
  created_at: string;
  updated_at: string;
};

export type InteractionEventType =
  | "open"
  | "read_start"
  | "read_progress"
  | "read_complete"
  | "like"
  | "dislike"
  | "save"
  | "annotate"
  | "skip"
  | "search";

export type InteractionPayload = {
  eventType: InteractionEventType;
  workId?: string;
  excerptId?: string;
  value?: number;
  metadata?: Record<string, string | number | boolean | null>;
};
