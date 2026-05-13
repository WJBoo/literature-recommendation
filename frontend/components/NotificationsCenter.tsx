"use client";

import { Bell, MessageCircle, NotebookPen, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  fetchCurrentAccount,
  fetchFollowedUserActivity,
  fetchMessageThreads,
} from "../lib/api";
import type { AccountActivityItem, AccountUser, MessageThread } from "../lib/types";

type NotificationItem = {
  id: string;
  href: string;
  kind: string;
  title: string;
  body: string;
  timestamp: string;
};

export function NotificationsCenter() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [activity, setActivity] = useState<AccountActivityItem[]>([]);
  const [threads, setThreads] = useState<MessageThread[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchCurrentAccount()
      .then(async (account) => {
        if (!mounted) {
          return;
        }
        setUser(account);
        if (!account) {
          setActivity([]);
          setThreads([]);
          return;
        }
        const [readerActivity, messageThreads] = await Promise.all([
          fetchFollowedUserActivity(),
          fetchMessageThreads(),
        ]);
        if (mounted) {
          setActivity(readerActivity);
          setThreads(messageThreads);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setStatus(caught instanceof Error ? caught.message : "Unable to load notifications.");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoaded(true);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const notifications = useMemo(
    () => buildNotifications(activity, threads, user?.id),
    [activity, threads, user?.id],
  );

  if (!loaded) {
    return (
      <section className="form-surface notifications-center">
        <p className="muted">Loading notifications.</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="form-surface notifications-center">
        <div className="empty-notifications">
          <Bell size={26} aria-hidden="true" />
          <h2>Sign in to tune your updates.</h2>
          <p className="muted">
            Notifications collect messages, friend annotations, posts, likes, and saves once
            you have an account.
          </p>
          <Link className="primary-button" href="/profile">
            <UserRound size={18} aria-hidden="true" />
            Go to profile
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="form-surface notifications-center">
      <div className="form-heading">
        <div>
          <h2>Notifications</h2>
          <p className="muted">Messages and visible activity from people you follow.</p>
        </div>
        <span className="notification-count">{notifications.length}</span>
      </div>
      {status ? <p className="form-message error-message">{status}</p> : null}
      {notifications.length ? (
        <div className="notification-list">
          {notifications.map((item) => (
            <Link className="notification-item" href={item.href} key={item.id}>
              {item.kind === "Message" ? (
                <MessageCircle size={18} aria-hidden="true" />
              ) : (
                <NotebookPen size={18} aria-hidden="true" />
              )}
              <span>
                <strong>{item.title}</strong>
                <span className="muted">{item.body}</span>
              </span>
              <time className="notification-time" dateTime={item.timestamp}>
                {new Date(item.timestamp).toLocaleDateString()}
              </time>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty-notifications">
          <Bell size={26} aria-hidden="true" />
          <h2>No notifications yet.</h2>
          <p className="muted">Follow writers and readers to see activity here.</p>
        </div>
      )}
    </section>
  );
}

function buildNotifications(
  activity: AccountActivityItem[],
  threads: MessageThread[],
  currentUserId?: string,
): NotificationItem[] {
  const messageItems = threads
    .map((thread) => {
      const latest = thread.messages[thread.messages.length - 1];
      if (!latest || latest.sender_user_id === currentUserId) {
        return null;
      }
      return {
        id: `message-${latest.id}`,
        href: `/messages?reader=${latest.sender_user_id}`,
        kind: "Message",
        title: `Message from ${latest.sender_display_name}`,
        body: latest.body,
        timestamp: latest.created_at,
      };
    })
    .filter((item): item is NotificationItem => Boolean(item));

  const activityItems = activity.map((item) => ({
    id: `activity-${item.id}`,
    href: activityHref(item),
    kind: formatActivityType(item.activity_type),
    title: `${item.user_display_name} ${formatActivityVerb(item.activity_type)}`,
    body: item.note || item.selected_text || item.title,
    timestamp: item.created_at,
  }));

  return [...messageItems, ...activityItems].sort(
    (left, right) => Date.parse(right.timestamp) - Date.parse(left.timestamp),
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
  return "/connect";
}

function formatActivityType(type: AccountActivityItem["activity_type"]): string {
  if (type === "posted") {
    return "Post";
  }
  if (type === "annotated") {
    return "Annotation";
  }
  if (type === "liked") {
    return "Like";
  }
  if (type === "saved") {
    return "Save";
  }
  return "Read";
}

function formatActivityVerb(type: AccountActivityItem["activity_type"]): string {
  if (type === "posted") {
    return "posted";
  }
  if (type === "annotated") {
    return "annotated";
  }
  if (type === "liked") {
    return "liked";
  }
  if (type === "saved") {
    return "saved";
  }
  return "read";
}
