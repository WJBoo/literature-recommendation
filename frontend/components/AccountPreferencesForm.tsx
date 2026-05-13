"use client";

import { LogIn, Save, UserPlus } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  emptyPreferenceProfile,
  fetchCurrentAccount,
  loginAccount,
  registerAccount,
  updateAccountPreferences,
} from "../lib/api";
import type { AccountUser, PreferenceProfile } from "../lib/types";

const genreChoices = ["romance", "epic poetry", "gothic", "satire", "adventure", "philosophy"];
const formChoices = ["poetry", "prose", "drama"];
const themeChoices = ["love", "time", "beauty", "memory", "fate", "justice", "sea", "family"];
const moodChoices = ["contemplative", "melancholic", "dramatic", "playful", "mysterious"];

type AccountPreferencesFormProps = {
  compact?: boolean;
  onAccountChange?: (user: AccountUser) => void;
};

export function AccountPreferencesForm({ compact = false, onAccountChange }: AccountPreferencesFormProps) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [user, setUser] = useState<AccountUser | null>(null);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [preferences, setPreferences] = useState<PreferenceProfile>(emptyPreferenceProfile);
  const [authorsText, setAuthorsText] = useState("");
  const [booksText, setBooksText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    void fetchCurrentAccount().then((account) => {
      if (!mounted || !account) {
        return;
      }
      setUser(account);
      setEmail(account.email);
      setDisplayName(account.display_name);
      setPreferences(account.preferences);
      setAuthorsText(account.preferences.authors.join(", "));
      setBooksText(account.preferences.books.join(", "));
    });

    return () => {
      mounted = false;
    };
  }, []);

  const profileWithText = useMemo(
    () => ({
      ...preferences,
      authors: splitList(authorsText),
      books: splitList(booksText),
    }),
    [authorsText, booksText, preferences],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setStatus(null);

    try {
      if (user) {
        const updated = await updateAccountPreferences(profileWithText);
        setUser(updated);
        onAccountChange?.(updated);
        setStatus("Preferences saved.");
        return;
      }

      const account =
        mode === "register"
          ? await registerAccount({
              email,
              password,
              displayName,
              preferences: profileWithText,
            })
          : await loginAccount({ email, password });

      setUser(account.user);
      setEmail(account.user.email);
      setDisplayName(account.user.display_name);
      setPreferences(account.user.preferences);
      setAuthorsText(account.user.preferences.authors.join(", "));
      setBooksText(account.user.preferences.books.join(", "));
      onAccountChange?.(account.user);
      setStatus(mode === "register" ? "Account created." : "Signed in.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  function togglePreference(group: keyof PreferenceProfile, value: string) {
    setPreferences((current) => {
      const values = current[group];
      const hasValue = values.includes(value);
      return {
        ...current,
        [group]: hasValue ? values.filter((item) => item !== value) : [...values, value],
      };
    });
  }

  return (
    <form className="form-surface account-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <div>
          <h2>{user ? "Saved Preferences" : "Account"}</h2>
          <p className="muted">
            {user
              ? `${user.display_name} · ${user.email}`
              : "Create a reader profile or sign in to restore one."}
          </p>
        </div>
        {!user ? (
          <div className="segmented-control" aria-label="Account mode">
            <button
              className={mode === "register" ? "segment active-segment" : "segment"}
              onClick={() => setMode("register")}
              type="button"
            >
              <UserPlus size={16} aria-hidden="true" />
              Join
            </button>
            <button
              className={mode === "login" ? "segment active-segment" : "segment"}
              onClick={() => setMode("login")}
              type="button"
            >
              <LogIn size={16} aria-hidden="true" />
              Sign in
            </button>
          </div>
        ) : null}
      </div>

      {!user ? (
        <div className="field-grid">
          {mode === "register" ? (
            <label>
              Display name
              <input
                className="input"
                onChange={(event) => setDisplayName(event.target.value)}
                required
                value={displayName}
              />
            </label>
          ) : null}
          <label>
            Email
            <input
              className="input"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label>
            Password
            <input
              className="input"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
        </div>
      ) : null}

      {mode === "register" || user ? (
        <>
          <PreferenceGroup
            label="Genres"
            choices={genreChoices}
            selected={preferences.genres}
            onToggle={(value) => togglePreference("genres", value)}
          />
          <PreferenceGroup
            label="Forms"
            choices={formChoices}
            selected={preferences.forms}
            onToggle={(value) => togglePreference("forms", value)}
          />
          {!compact ? (
            <>
              <PreferenceGroup
                label="Themes"
                choices={themeChoices}
                selected={preferences.themes}
                onToggle={(value) => togglePreference("themes", value)}
              />
              <PreferenceGroup
                label="Moods"
                choices={moodChoices}
                selected={preferences.moods}
                onToggle={(value) => togglePreference("moods", value)}
              />
            </>
          ) : null}
          <label>
            Authors
            <textarea
              className="textarea compact-textarea"
              onChange={(event) => setAuthorsText(event.target.value)}
              placeholder="Jane Austen, William Shakespeare, Mary Shelley"
              value={authorsText}
            />
          </label>
          <label>
            Books
            <textarea
              className="textarea compact-textarea"
              onChange={(event) => setBooksText(event.target.value)}
              placeholder="Pride and Prejudice, Frankenstein"
              value={booksText}
            />
          </label>
        </>
      ) : null}

      {error ? <p className="form-message error-message">{error}</p> : null}
      {status ? <p className="form-message success-message">{status}</p> : null}

      <button className="primary-button" disabled={saving} type="submit">
        <Save size={18} aria-hidden="true" />
        {saving ? "Saving" : user ? "Save Preferences" : mode === "register" ? "Create Account" : "Sign In"}
      </button>
    </form>
  );
}

function PreferenceGroup({
  label,
  choices,
  selected,
  onToggle,
}: {
  label: string;
  choices: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="preference-fieldset">
      <legend>{label}</legend>
      <div className="preference-grid">
        {choices.map((choice) => (
          <button
            className={selected.includes(choice) ? "choice selected-choice" : "choice"}
            key={choice}
            onClick={() => onToggle(choice)}
            type="button"
          >
            {choice}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
