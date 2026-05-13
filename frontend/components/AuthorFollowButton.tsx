"use client";

import { UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchAuthorProfile, followAuthor, getAccountToken, unfollowAuthor } from "../lib/api";

type AuthorFollowButtonProps = {
  authorId: string;
  initialFollowed: boolean;
};

export function AuthorFollowButton({ authorId, initialFollowed }: AuthorFollowButtonProps) {
  const [followed, setFollowed] = useState(initialFollowed);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccountToken()) {
      return;
    }
    let mounted = true;
    void fetchAuthorProfile(authorId)
      .then((profile) => {
        if (mounted) {
          setFollowed(profile.followed);
        }
      })
      .catch(() => {
        // The public profile still renders if account-specific follow state is unavailable.
      });
    return () => {
      mounted = false;
    };
  }, [authorId]);

  async function toggleFollow() {
    if (!getAccountToken()) {
      setStatus("Sign in to follow authors.");
      return;
    }
    setPending(true);
    setStatus(null);
    try {
      if (followed) {
        await unfollowAuthor(authorId);
        setFollowed(false);
      } else {
        await followAuthor(authorId);
        setFollowed(true);
      }
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update follow.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="author-follow-control">
      <button
        aria-pressed={followed}
        className={followed ? "secondary-button active-button" : "primary-button"}
        disabled={pending}
        onClick={() => void toggleFollow()}
        type="button"
      >
        <UserPlus size={18} aria-hidden="true" />
        {pending ? "Updating" : followed ? "Following" : "Follow"}
      </button>
      {status ? <p className="muted">{status}</p> : null}
    </div>
  );
}
