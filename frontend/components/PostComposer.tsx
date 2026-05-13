"use client";

import { ImagePlus, Send, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { createAccountPost, deleteAccountPost, fetchAccountPosts, fetchCurrentAccount } from "../lib/api";
import type { AccountUser, PostMediaItem, UserPost } from "../lib/types";

const formOptions = ["prose", "poetry", "essay", "drama"];
const maxMediaItems = 4;
const maxMediaBytes = 2_000_000;
const maxTotalMediaBytes = 4_000_000;

export function PostComposer() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [posts, setPosts] = useState<UserPost[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [form, setForm] = useState("prose");
  const [visibility, setVisibility] = useState("public");
  const [media, setMedia] = useState<PostMediaItem[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [deletingPostId, setDeletingPostId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchCurrentAccount(), fetchAccountPosts()])
      .then(([account, accountPosts]) => {
        if (mounted) {
          setUser(account);
          setPosts(accountPosts);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setStatus(caught instanceof Error ? caught.message : "Unable to load posts.");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus(null);
    if (!user) {
      setStatus("Sign in before posting your writing.");
      return;
    }
    setPublishing(true);
    try {
      const post = await createAccountPost({ title, body, form, visibility, media });
      setPosts((current) => [post, ...current]);
      setTitle("");
      setBody("");
      setForm("prose");
      setVisibility("public");
      setMedia([]);
      setStatus("Post published.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to publish post.");
    } finally {
      setPublishing(false);
    }
  }

  async function handleDeletePost(post: UserPost) {
    if (!window.confirm(`Delete "${post.title}"? This cannot be undone.`)) {
      return;
    }
    setDeletingPostId(post.id);
    setStatus(null);
    try {
      await deleteAccountPost(post.id);
      setPosts((current) => current.filter((candidate) => candidate.id !== post.id));
      setStatus("Post deleted.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to delete post.");
    } finally {
      setDeletingPostId(null);
    }
  }

  async function handleMediaChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) {
      return;
    }
    if (media.length + files.length > maxMediaItems) {
      setStatus(`Add up to ${maxMediaItems} media files per post.`);
      return;
    }

    const currentTotal = media.reduce((sum, item) => sum + dataUrlBytes(item.data_url), 0);
    let nextTotal = currentTotal;
    const nextItems: PostMediaItem[] = [];
    try {
      for (const file of files) {
        if (!file.type.startsWith("image/") && !file.type.startsWith("video/")) {
          setStatus("Choose image or video files.");
          return;
        }
        if (file.size > maxMediaBytes) {
          setStatus("Choose media files under 2 MB for this local prototype.");
          return;
        }
        nextTotal += file.size;
        if (nextTotal > maxTotalMediaBytes) {
          setStatus("Keep total post media under 4 MB for this local prototype.");
          return;
        }
        const dataUrl = await readFileAsDataUrl(file);
        nextItems.push({
          id: `media-${Date.now()}-${nextItems.length}-${slugifyFileName(file.name)}`,
          media_type: file.type.startsWith("video/") ? "video" : "image",
          data_url: dataUrl,
          alt_text: file.name,
          caption: "",
        });
      }
      setMedia((current) => [...current, ...nextItems]);
      setStatus(null);
    } catch {
      setStatus("Unable to read that media file.");
    }
  }

  function updateMediaCaption(mediaId: string, caption: string) {
    setMedia((current) =>
      current.map((item) => (item.id === mediaId ? { ...item, caption } : item)),
    );
  }

  function removeMedia(mediaId: string) {
    setMedia((current) => current.filter((item) => item.id !== mediaId));
  }

  return (
    <div className="post-workspace">
      <form className="form-surface post-composer" onSubmit={handleSubmit}>
        <div className="form-heading">
          <div>
            <h2>New post</h2>
            <p className="muted">Publish original work to your profile.</p>
          </div>
        </div>
        <label>
          Title
          <input
            className="input"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Title"
            value={title}
          />
        </label>
        <div className="field-grid two-column-fields">
          <label>
            Form
            <select className="input" onChange={(event) => setForm(event.target.value)} value={form}>
              {formOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            Visibility
            <select
              className="input"
              onChange={(event) => setVisibility(event.target.value)}
              value={visibility}
            >
              <option value="public">public</option>
              <option value="followers">followers</option>
              <option value="private">private</option>
            </select>
          </label>
        </div>
        <label>
          Piece
          <textarea
            className="textarea"
            onChange={(event) => setBody(event.target.value)}
            placeholder="Paste or write your piece here."
            value={body}
          />
        </label>
        <div className="post-media-field">
          <label>
            Media
            <span className="file-input-row">
              <input
                accept="image/*,video/*"
                multiple
                onChange={(event) => void handleMediaChange(event)}
                type="file"
              />
              <span className="muted">Images or short video clips, up to 4 files.</span>
            </span>
          </label>
          {media.length ? (
            <div className="post-media-grid">
              {media.map((item) => (
                <article className="post-media-card" key={item.id}>
                  <PostMediaPreview media={item} />
                  <label>
                    Caption
                    <input
                      className="input"
                      onChange={(event) => updateMediaCaption(item.id, event.target.value)}
                      placeholder="Optional caption"
                      value={item.caption ?? ""}
                    />
                  </label>
                  <button
                    className="secondary-button quiet-button"
                    onClick={() => removeMedia(item.id)}
                    type="button"
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    Remove
                  </button>
                </article>
              ))}
            </div>
          ) : null}
        </div>
        <button className="primary-button" disabled={publishing} type="submit">
          <Send size={18} aria-hidden="true" />
          {publishing ? "Publishing" : "Publish"}
        </button>
        {status ? <p className="form-message success-message">{status}</p> : null}
      </form>

      <section className="form-surface post-preview-list">
        <h2>Your posts</h2>
        {posts.length ? (
          <div className="profile-post-grid">
            {posts.map((post) => (
              <article className="profile-post-tile post-list-tile" key={post.id}>
                <Link className="post-tile-link" href={`/work/${post.id}`}>
                  <p className="eyebrow">{post.form}</p>
                  <h3>{post.title}</h3>
                  {post.media?.[0] ? <PostMediaPreview compact media={post.media[0]} /> : null}
                  <p>{post.body}</p>
                </Link>
                <div className="post-tile-actions">
                  <span className="muted">{post.visibility}</span>
                  <button
                    aria-label={`Delete ${post.title}`}
                    className="secondary-button quiet-button post-delete-button"
                    disabled={deletingPostId === post.id}
                    onClick={() => void handleDeletePost(post)}
                    title="Delete post"
                    type="button"
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">No posts yet.</p>
        )}
      </section>
    </div>
  );
}

function PostMediaPreview({
  compact = false,
  media,
}: {
  compact?: boolean;
  media: PostMediaItem;
}) {
  if (media.media_type === "image") {
    return (
      <Image
        alt={media.alt_text || media.caption || "Post image"}
        className={compact ? "post-media-preview compact-post-media" : "post-media-preview"}
        height={compact ? 180 : 360}
        src={media.data_url}
        unoptimized
        width={compact ? 260 : 640}
      />
    );
  }
  return (
    <video
      className={compact ? "post-media-preview compact-post-media" : "post-media-preview"}
      controls={!compact}
      muted={compact}
      playsInline
      src={media.data_url}
    />
  );
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Unable to read that file."));
    reader.readAsDataURL(file);
  });
}

function slugifyFileName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32);
}

function dataUrlBytes(dataUrl: string): number {
  return Math.ceil((dataUrl.length * 3) / 4);
}
