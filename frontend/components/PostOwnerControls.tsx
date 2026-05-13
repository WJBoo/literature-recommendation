"use client";

import { Pencil, Save, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  deleteAccountPost,
  fetchAccountPosts,
  updateAccountPost,
} from "../lib/api";
import type { UserPost } from "../lib/types";

const formOptions = ["prose", "poetry", "essay", "drama"];
const visibilityOptions = ["public", "followers", "private"];

export function PostOwnerControls({ postId }: { postId: string }) {
  const router = useRouter();
  const [post, setPost] = useState<UserPost | null>(null);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [form, setForm] = useState("prose");
  const [visibility, setVisibility] = useState("public");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchAccountPosts()
      .then((posts) => {
        const matchingPost = posts.find((candidate) => candidate.id === postId) ?? null;
        if (mounted && matchingPost) {
          setPost(matchingPost);
          setTitle(matchingPost.title);
          setBody(matchingPost.body);
          setForm(matchingPost.form);
          setVisibility(matchingPost.visibility);
        }
      })
      .catch(() => {
        if (mounted) {
          setPost(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, [postId]);

  if (!post) {
    return null;
  }

  async function handleDelete() {
    if (!post || !window.confirm(`Delete "${post.title}"? This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      await deleteAccountPost(post.id);
      router.push("/post");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to delete post.");
      setBusy(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!post) {
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      const updated = await updateAccountPost(post.id, {
        title,
        body,
        form,
        visibility,
        media: post.media ?? [],
      });
      setPost(updated);
      setTitle(updated.title);
      setBody(updated.body);
      setForm(updated.form);
      setVisibility(updated.visibility);
      setEditing(false);
      setStatus("Post updated.");
      router.refresh();
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update post.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="post-owner-panel">
      <div className="post-owner-heading">
        <div>
          <p className="eyebrow">Your post</p>
          <p className="muted">Edit this piece or remove it from your profile.</p>
        </div>
        <div className="post-owner-actions">
          <button
            className="secondary-button"
            disabled={busy}
            onClick={() => setEditing((current) => !current)}
            type="button"
          >
            {editing ? <X size={16} aria-hidden="true" /> : <Pencil size={16} aria-hidden="true" />}
            {editing ? "Cancel" : "Edit"}
          </button>
          <button
            className="secondary-button quiet-button post-delete-button"
            disabled={busy}
            onClick={() => void handleDelete()}
            type="button"
          >
            <Trash2 size={16} aria-hidden="true" />
            Delete
          </button>
        </div>
      </div>
      {editing ? (
        <form className="post-owner-edit-form" onSubmit={handleSave}>
          <label>
            Title
            <input
              className="input"
              onChange={(event) => setTitle(event.target.value)}
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
                {visibilityOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Piece
            <textarea
              className="textarea post-owner-textarea"
              onChange={(event) => setBody(event.target.value)}
              value={body}
            />
          </label>
          <button className="primary-button" disabled={busy} type="submit">
            <Save size={16} aria-hidden="true" />
            {busy ? "Saving" : "Save changes"}
          </button>
        </form>
      ) : null}
      {status ? <p className="form-message success-message">{status}</p> : null}
    </section>
  );
}
