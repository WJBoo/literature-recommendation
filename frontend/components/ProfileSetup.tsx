"use client";

import { ImagePlus, Save, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { updateAccountProfile } from "../lib/api";
import type { AccountUser, PostMediaItem, UserPost } from "../lib/types";

type ProfileSetupProps = {
  posts: UserPost[];
  user: AccountUser;
  onAccountChange: (user: AccountUser) => void;
};

const maxAvatarBytes = 400_000;

export function ProfileSetup({ posts, user, onAccountChange }: ProfileSetupProps) {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [bio, setBio] = useState(user.bio ?? "");
  const [avatarDataUrl, setAvatarDataUrl] = useState<string | null>(user.avatar_data_url);
  const [accountVisibility, setAccountVisibility] = useState<"public" | "private">(user.account_visibility);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function handleAvatarChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    if (!file.type.startsWith("image/")) {
      setStatus("Choose an image file for your profile photo.");
      return;
    }
    if (file.size > maxAvatarBytes) {
      setStatus("Choose an image under 400 KB for now.");
      return;
    }
    const dataUrl = await readFileAsDataUrl(file);
    setAvatarDataUrl(dataUrl);
    setStatus(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      const updated = await updateAccountProfile({
        displayName,
        bio,
        avatarDataUrl,
        accountVisibility,
      });
      onAccountChange(updated);
      setStatus("Profile updated.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="form-surface profile-showcase">
      <div className="profile-identity">
        <Avatar displayName={user.display_name} src={avatarDataUrl} />
        <div className="profile-identity-copy">
          <p className="eyebrow">Reader profile</p>
          <h2>{user.display_name}</h2>
          <p className="muted">{user.bio || "Add a short self-description for other readers."}</p>
          <div className="profile-stats" aria-label="Profile stats">
            <span>
              <strong>{posts.length}</strong>
              posts
            </span>
            <span>
              <strong>{user.preferences.genres.length}</strong>
              genres
            </span>
            <span>
              <strong>{user.preferences.authors.length}</strong>
              authors
            </span>
            <span>
              <strong>{user.account_visibility}</strong>
              account
            </span>
          </div>
        </div>
      </div>

      <form className="profile-edit-form" onSubmit={handleSubmit}>
        <label>
          Display name
          <input
            className="input"
            onChange={(event) => setDisplayName(event.target.value)}
            value={displayName}
          />
        </label>
        <label>
          Profile photo
          <span className="file-input-row">
            <input accept="image/*" onChange={handleAvatarChange} type="file" />
            <button
              className="secondary-button"
              onClick={() => setAvatarDataUrl(null)}
              type="button"
            >
              <X size={16} aria-hidden="true" />
              Clear
            </button>
          </span>
        </label>
        <label className="profile-bio-field">
          Self-description
          <textarea
            className="textarea compact-textarea"
            onChange={(event) => setBio(event.target.value)}
            placeholder="What do you read, write, notice, return to?"
            value={bio}
          />
        </label>
        <label>
          Account visibility
          <select
            className="input"
            onChange={(event) => setAccountVisibility(event.target.value === "private" ? "private" : "public")}
            value={accountVisibility}
          >
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        </label>
        <button className="primary-button profile-save-button" disabled={saving} type="submit">
          <Save size={18} aria-hidden="true" />
          {saving ? "Saving" : "Save Profile"}
        </button>
      </form>
      {status ? <p className="form-message success-message">{status}</p> : null}

      <div className="profile-posts-header">
        <div>
          <h3>Posts</h3>
          <p className="muted">Original pieces posted from this account.</p>
        </div>
      </div>
      {posts.length ? (
        <div className="profile-post-grid">
          {posts.map((post) => (
            <Link className="profile-post-tile" href={`/work/${post.id}`} key={post.id}>
              <p className="eyebrow">{post.form}</p>
              <h4>{post.title}</h4>
              {post.media?.[0] ? <PostTileMedia media={post.media[0]} /> : null}
              <p>{post.body}</p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="muted">No posts yet. Use the Post tab to publish your first piece.</p>
      )}
    </section>
  );
}

function PostTileMedia({ media }: { media: PostMediaItem }) {
  if (media.media_type === "image") {
    return (
      <Image
        alt={media.alt_text || media.caption || "Post image"}
        className="post-media-preview compact-post-media"
        height={160}
        src={media.data_url}
        unoptimized
        width={260}
      />
    );
  }
  return (
    <video
      className="post-media-preview compact-post-media"
      muted
      playsInline
      src={media.data_url}
    />
  );
}

function Avatar({ displayName, src }: { displayName: string; src: string | null }) {
  if (src) {
    return (
      <Image
        alt={`${displayName} profile`}
        className="profile-avatar"
        height={150}
        src={src}
        unoptimized
        width={150}
      />
    );
  }
  return (
    <div className="profile-avatar avatar-placeholder" aria-hidden="true">
      <ImagePlus size={34} />
    </div>
  );
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Unable to read that image."));
    reader.readAsDataURL(file);
  });
}
