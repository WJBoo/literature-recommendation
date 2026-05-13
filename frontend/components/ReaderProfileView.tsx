"use client";

import { MessageCircle, UserCheck, UserPlus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchReaderProfile, followReader, unfollowReader } from "../lib/api";
import type { AccountActivityItem, AccountReaderProfile, PostMediaItem } from "../lib/types";

export function ReaderProfileView({ userId }: { userId: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<AccountReaderProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [updatingFollow, setUpdatingFollow] = useState(false);
  const reader = profile?.reader ?? null;

  useEffect(() => {
    let mounted = true;
    void fetchReaderProfile(userId)
      .then((loadedProfile) => {
        if (mounted) {
          setProfile(loadedProfile);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setStatus(caught instanceof Error ? caught.message : "Unable to load profile.");
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
  }, [userId]);

  async function handleFollowToggle() {
    if (!reader) {
      return;
    }
    setUpdatingFollow(true);
    setStatus(null);
    try {
      const directory = reader.followed_by_me
        ? await unfollowReader(reader.id)
        : await followReader(reader.id);
      const updatedReader = directory.find((candidate) => candidate.id === reader.id);
      const updatedProfile = await fetchReaderProfile(reader.id);
      setProfile({
        ...updatedProfile,
        reader: updatedReader ?? updatedProfile.reader,
      });
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update follow.");
    } finally {
      setUpdatingFollow(false);
    }
  }

  function handleMessage() {
    if (!reader) {
      return;
    }
    if (!reader.can_message) {
      setStatus(messageRestrictionText(reader));
      return;
    }
    router.push(`/messages?reader=${reader.id}`);
  }

  if (loading) {
    return (
      <section className="form-surface">
        <p className="muted">Loading reader profile.</p>
      </section>
    );
  }

  if (!reader) {
    return (
      <section className="form-surface">
        <p className="muted">{status || "Reader profile not found."}</p>
      </section>
    );
  }

  return (
    <section className="form-surface profile-showcase reader-profile-showcase">
      <div className="profile-identity">
        <ReaderProfileAvatar displayName={reader.display_name} src={reader.avatar_data_url} />
        <div className="profile-identity-copy">
          <p className="eyebrow">
            {formatProfileRole(reader.profile_role)} · {reader.account_visibility} profile
          </p>
          <h2>{reader.display_name}</h2>
          <p className="muted">{reader.bio || "Reading on Linguaphilia."}</p>
          <div className="profile-stats" aria-label="Profile stats">
            <span>
              <strong>{reader.post_count}</strong>
              posts
            </span>
            <span>
              <strong>{reader.followed_by_me ? "yes" : "no"}</strong>
              following
            </span>
            <span>
              <strong>{reader.follows_me ? "yes" : "no"}</strong>
              follows you
            </span>
          </div>
          <div className="reader-card-actions">
            <button
              className={reader.followed_by_me ? "secondary-button active-button" : "secondary-button"}
              disabled={updatingFollow}
              onClick={() => void handleFollowToggle()}
              type="button"
            >
              {reader.followed_by_me ? (
                <UserCheck size={16} aria-hidden="true" />
              ) : (
                <UserPlus size={16} aria-hidden="true" />
              )}
              {reader.followed_by_me ? "Following" : "Follow"}
            </button>
            <button
              className="primary-button"
              disabled={!reader.can_message}
              onClick={handleMessage}
              title={reader.can_message ? "Message" : messageRestrictionText(reader)}
              type="button"
            >
              <MessageCircle size={16} aria-hidden="true" />
              {reader.can_send_initial_message ? "Send one" : "Message"}
            </button>
          </div>
        </div>
      </div>
      {status ? <p className="form-message success-message">{status}</p> : null}
      {profile?.posts.length ? (
        <div className="profile-posts-header">
          <h3>Posts</h3>
          <div className="profile-post-grid">
            {profile.posts.slice(0, 6).map((post) => (
              <Link className="profile-post-tile" href={`/work/${post.id}`} key={post.id}>
                <p className="eyebrow">{post.form}</p>
                <h3>{post.title}</h3>
                {post.media?.[0] ? <PostTileMedia media={post.media[0]} /> : null}
                <p className="muted">{post.body}</p>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
      <div className="profile-activity-section">
        <div className="form-heading">
          <div>
            <h3>Activity</h3>
            <p className="muted">Read, liked, annotated, saved, and posted items visible to you.</p>
          </div>
        </div>
        {profile?.can_view_activity ? (
          profile.activity.length ? (
            <div className="profile-activity-list">
              {profile.activity.slice(0, 10).map((item) => (
                <ActivityItem item={item} key={item.id} />
              ))}
            </div>
          ) : (
            <p className="muted">No visible activity yet.</p>
          )
        ) : (
          <p className="muted">This reader shares activity with mutual follows.</p>
        )}
      </div>
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

function ReaderProfileAvatar({
  displayName,
  src,
}: {
  displayName: string;
  src: string | null;
}) {
  if (src) {
    return (
      <Image
        alt={`${displayName} profile`}
        className="profile-avatar"
        height={144}
        src={src}
        unoptimized
        width={144}
      />
    );
  }
  return (
    <div className="profile-avatar avatar-placeholder" aria-hidden="true">
      {displayName.slice(0, 1).toUpperCase()}
    </div>
  );
}

function ActivityItem({ item }: { item: AccountActivityItem }) {
  const href = activityHref(item);
  return (
    <article className="profile-activity-item">
      <p className="eyebrow">
        {formatActivityType(item.activity_type)} · {new Date(item.created_at).toLocaleDateString()}
      </p>
      <Link className="text-link" href={href}>
        {item.title}
      </Link>
      {item.author ? <p className="muted">{item.author}</p> : null}
      {item.selected_text ? (
        <p>
          <strong>Annotated text:</strong> {item.selected_text}
        </p>
      ) : null}
      {item.note ? (
        <p>
          <strong>Comment:</strong> {item.note}
        </p>
      ) : null}
      <p className="muted">{item.preview}</p>
    </article>
  );
}

function activityHref(item: AccountActivityItem): string {
  if (item.excerpt_id) {
    const suffix = item.activity_type === "annotated" ? `?annotation=${item.id}` : "";
    return `/work/${item.excerpt_id}${suffix}`;
  }
  if (item.post_id) {
    return `/work/${item.post_id}`;
  }
  return "#";
}

function formatProfileRole(role: AccountReaderProfile["reader"]["profile_role"]): string {
  if (role === "writer") {
    return "Writer";
  }
  if (role === "writer_reader") {
    return "Writer/reader";
  }
  return "Reader";
}

function formatActivityType(type: AccountActivityItem["activity_type"]): string {
  if (type === "posted") {
    return "Posted";
  }
  if (type === "saved") {
    return "Saved";
  }
  if (type === "liked") {
    return "Liked";
  }
  if (type === "annotated") {
    return "Annotated";
  }
  return "Read";
}

function messageRestrictionText(reader: AccountReaderProfile["reader"]): string {
  if (!reader.followed_by_me) {
    return "Follow this reader before sending a message.";
  }
  if (reader.message_limit_reached) {
    return "You have already sent one message. They need to follow you back before you can send another.";
  }
  return "You can message readers only after you follow each other.";
}
