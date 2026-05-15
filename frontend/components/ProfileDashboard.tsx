"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AccountPreferencesForm } from "./AccountPreferencesForm";
import {
  clearAccountSession,
  fetchAccountPosts,
  fetchCurrentAccount,
  fetchFollowedUserActivity,
  fetchFollowedAuthors,
} from "../lib/api";
import { ProfileSetup } from "./ProfileSetup";
import { SavedLibrary } from "./SavedLibrary";
import type { AccountActivityItem, AccountUser, FollowedAuthor, UserPost } from "../lib/types";

export function ProfileDashboard() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [posts, setPosts] = useState<UserPost[]>([]);
  const [followedAuthors, setFollowedAuthors] = useState<FollowedAuthor[]>([]);
  const [followedActivity, setFollowedActivity] = useState<AccountActivityItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [accountFormVersion, setAccountFormVersion] = useState(0);

  useEffect(() => {
    let mounted = true;

    async function loadProfile() {
      try {
        const account = await fetchCurrentAccount();
        if (!mounted) {
          return;
        }
        setUser(account);
        setSignedOut(false);
        setLoaded(true);

        if (!account) {
          setPosts([]);
          setFollowedAuthors([]);
          setFollowedActivity([]);
          return;
        }

        const [accountPosts, authors, activity] = await Promise.allSettled([
          fetchAccountPosts(),
          fetchFollowedAuthors(),
          fetchFollowedUserActivity(),
        ]);
        if (!mounted) {
          return;
        }
        if (accountPosts.status === "fulfilled") {
          setPosts(accountPosts.value);
        }
        if (authors.status === "fulfilled") {
          setFollowedAuthors(authors.value);
        }
        if (activity.status === "fulfilled") {
          setFollowedActivity(activity.value);
        }
      } catch {
        if (mounted) {
          setUser(null);
          setPosts([]);
          setFollowedAuthors([]);
          setFollowedActivity([]);
          setLoaded(true);
        }
      }
    }

    void loadProfile();
    return () => {
      mounted = false;
    };
  }, []);

  function signOut() {
    clearAccountSession();
    setUser(null);
    setPosts([]);
    setFollowedAuthors([]);
    setFollowedActivity([]);
    setSignedOut(true);
    setAccountFormVersion((version) => version + 1);
  }

  if (!loaded) {
    return (
      <div className="form-surface">
        <p className="muted">Loading profile.</p>
      </div>
    );
  }

  return (
    <div className="profile-stack">
      {user ? (
        <div className="form-surface profile-summary">
          <div>
            <h2>{user.display_name}</h2>
            <p className="muted">{user.email}</p>
          </div>
          <button className="secondary-button" onClick={signOut} type="button">
            <LogOut size={18} aria-hidden="true" />
            Sign out
          </button>
        </div>
      ) : null}
      {!user && signedOut ? (
        <section className="form-surface signed-out-panel">
          <h2>Signed out</h2>
          <p className="muted">
            You are signed out of Linguaphilia. Sign in or create an account below to save
            preferences, posts, follows, and messages.
          </p>
        </section>
      ) : null}
      {user ? <ProfileSetup onAccountChange={setUser} posts={posts} user={user} /> : null}
      {user ? <FollowedReaderActivity activity={followedActivity} /> : null}
      {user ? <FollowedAuthors authors={followedAuthors} /> : null}
      <AccountPreferencesForm
        compact={false}
        key={accountFormVersion}
        onAccountChange={(account) => {
          setUser(account);
          setSignedOut(false);
        }}
      />
      {user ? <SavedLibrary /> : null}
    </div>
  );
}

function FollowedReaderActivity({ activity }: { activity: AccountActivityItem[] }) {
  return (
    <section className="form-surface followed-authors-section">
      <div className="form-heading">
        <div>
          <h2>Followed Readers</h2>
          <p className="muted">Recent reading, likes, annotations, saves, and posts from people you follow.</p>
        </div>
        {activity.length > 3 ? (
          <Link className="quiet-button" href="/connect">
            See all writers
          </Link>
        ) : null}
      </div>
      {activity.length ? (
        <div className="profile-activity-list">
          {activity.slice(0, 3).map((item) => (
            <article className="profile-activity-item" key={item.id}>
              <p className="eyebrow">
                {item.user_display_name} · {formatActivityType(item.activity_type)}
              </p>
              <Link
                className="text-link"
                href={activityHref(item)}
              >
                {item.title}
              </Link>
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
          ))}
        </div>
      ) : (
        <p className="muted">Follow readers to see their visible activity here.</p>
      )}
    </section>
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

function FollowedAuthors({ authors }: { authors: FollowedAuthor[] }) {
  return (
    <section className="form-surface followed-authors-section">
      <div className="form-heading">
        <div>
          <h2>Following</h2>
          <p className="muted">Authors you follow will influence recommendations.</p>
        </div>
      </div>
      {authors.length ? (
        <div className="followed-author-list">
          {authors.map((author) => (
            <Link className="followed-author-pill" href={`/authors/${author.id}`} key={author.id}>
              {author.name}
            </Link>
          ))}
        </div>
      ) : (
        <p className="muted">No followed authors yet.</p>
      )}
    </section>
  );
}
