"use client";

import { Lock, MessageCircle, Send, UserCheck, UserPlus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  fetchAccountDirectory,
  fetchCurrentAccount,
  fetchMessageThreads,
  followReader,
  sendAccountMessage,
  unfollowReader,
} from "../lib/api";
import type { AccountDirectoryUser, AccountUser, MessageThread } from "../lib/types";

export function MessagesPanel() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [threads, setThreads] = useState<MessageThread[]>([]);
  const [readers, setReaders] = useState<AccountDirectoryUser[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [draftRecipientId, setDraftRecipientId] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [sending, setSending] = useState(false);
  const [updatingFollowId, setUpdatingFollowId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const threadDetailRef = useRef<HTMLElement | null>(null);
  const replyRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([fetchCurrentAccount(), fetchMessageThreads(), fetchAccountDirectory()])
      .then(([account, messageThreads, directory]) => {
        if (!mounted) {
          return;
        }
        setUser(account);
        setThreads(messageThreads);
        setReaders(directory);
        const requestedReaderId = new URLSearchParams(window.location.search).get("reader");
        const requestedReader = directory.find((reader) => reader.id === requestedReaderId);
        const requestedThread = requestedReader
          ? messageThreads.find((thread) =>
              thread.participants.some((participant) => participant.id === requestedReader.id),
            )
          : null;
        if (requestedReader && requestedThread) {
          setSelectedThreadId(requestedThread.id);
          if (!requestedReader.can_message) {
            setStatus(messageRestrictionText(requestedReader));
          }
        } else if (requestedReader?.can_message) {
          setDraftRecipientId(requestedReader.id);
          setSelectedThreadId(null);
        } else {
          setSelectedThreadId(messageThreads[0]?.id ?? null);
          if (requestedReader) {
            setStatus(messageRestrictionText(requestedReader));
          }
        }
      })
      .catch((caught) => {
        if (mounted) {
          setStatus(caught instanceof Error ? caught.message : "Unable to load messages.");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) ?? null,
    [selectedThreadId, threads],
  );
  const draftReader = useMemo(
    () => readers.find((reader) => reader.id === draftRecipientId) ?? null,
    [draftRecipientId, readers],
  );
  const selectedReader = useMemo(() => {
    if (!selectedThread) {
      return null;
    }
    const recipient = selectedThread.participants.find((participant) => participant.id !== user?.id);
    return readers.find((reader) => reader.id === recipient?.id) ?? null;
  }, [readers, selectedThread, user?.id]);
  const selectedThreadHasMyMessage = Boolean(
    selectedThread?.messages.some((message) => message.sender_user_id === user?.id),
  );
  const canSendSelectedMessage = Boolean(
    selectedThread
      ? selectedReader
        ? selectedReader.can_message &&
          (!selectedReader.can_send_initial_message || !selectedThreadHasMyMessage)
        : true
      : draftReader?.can_message,
  );

  async function handleFollowToggle(reader: AccountDirectoryUser) {
    setUpdatingFollowId(reader.id);
    setStatus(null);
    try {
      const updatedDirectory = reader.followed_by_me
        ? await unfollowReader(reader.id)
        : await followReader(reader.id);
      setReaders(updatedDirectory);
      const updated = updatedDirectory.find((candidate) => candidate.id === reader.id);
      setStatus(updated?.can_message ? messageAllowedText(updated) : null);
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to update follow.");
    } finally {
      setUpdatingFollowId(null);
    }
  }

  function startChat(reader: AccountDirectoryUser) {
    const existingThread = threads.find((thread) =>
      thread.participants.some((participant) => participant.id === reader.id),
    );
    if (existingThread) {
      setSelectedThreadId(existingThread.id);
      setDraftRecipientId(null);
      setStatus(reader.can_message ? null : messageRestrictionText(reader));
      focusReply();
      return;
    }
    if (!reader.can_message) {
      setStatus(messageRestrictionText(reader));
      return;
    }
    setSelectedThreadId(null);
    setDraftRecipientId(reader.id);
    setStatus(null);
    focusReply();
  }

  function canSubmitReply() {
    return Boolean(replyBody.trim()) && (selectedThread || draftReader) && canSendSelectedMessage;
  }

  async function handleReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = replyBody.trim();
    if (!body) {
      return;
    }
    if (!user) {
      setStatus("Sign in before messaging other readers.");
      return;
    }
    if (!selectedThread && !draftReader) {
      setStatus("Choose a reader to message.");
      return;
    }
    if (!canSendSelectedMessage) {
      setStatus(
        selectedReader
          ? messageRestrictionText(selectedReader)
          : "You can message readers only after you follow each other.",
      );
      return;
    }
    setSending(true);
    setStatus(null);
    try {
      const thread = await sendAccountMessage({
        threadId: selectedThread?.id,
        recipientUserId: selectedThread ? undefined : draftReader?.id,
        body,
      });
      setThreads((current) => upsertThread(current, thread));
      setSelectedThreadId(thread.id);
      setDraftRecipientId(null);
      setReplyBody("");
      const updatedDirectory = await fetchAccountDirectory();
      setReaders(updatedDirectory);
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Unable to send message.");
    } finally {
      setSending(false);
    }
  }

  function selectThread(threadId: string) {
    setSelectedThreadId(threadId);
    setDraftRecipientId(null);
    focusReply();
  }

  function focusReply() {
    window.setTimeout(() => {
      threadDetailRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      replyRef.current?.focus();
    }, 0);
  }

  return (
    <div className="messages-layout">
      <section className="form-surface reader-directory">
        <div className="form-heading">
          <div>
            <h2>Readers</h2>
            <p className="muted">Follow readers and open message threads.</p>
          </div>
        </div>
        {!user ? <p className="muted">Sign in from Profile before connecting with readers.</p> : null}
        <div className="reader-card-grid">
          {readers.map((reader) => (
            <article className="reader-card" key={reader.id}>
              <Link className="reader-card-profile" href={`/readers/${reader.id}`}>
                <ReaderAvatar reader={reader} />
                <span>
                  <strong>{reader.display_name}</strong>
                  <span className="muted">
                    {reader.account_visibility === "private" ? "Private" : "Public"} ·{" "}
                    {formatProfileRole(reader.profile_role)} ·{" "}
                    {reader.post_count} posts
                  </span>
                </span>
              </Link>
              <p className="reader-card-bio">{reader.bio || "Reading on Linguaphilia."}</p>
              <div className="reader-card-actions">
                <button
                  className={reader.followed_by_me ? "secondary-button active-button" : "secondary-button"}
                  disabled={updatingFollowId === reader.id}
                  onClick={() => void handleFollowToggle(reader)}
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
                  disabled={!reader.can_message && !existingThreadForReader(threads, reader.id)}
                  onClick={() => startChat(reader)}
                  title={
                    reader.can_message
                      ? messageAllowedText(reader)
                      : messageRestrictionText(reader)
                  }
                  type="button"
                >
                  {reader.can_message ? (
                    <MessageCircle size={16} aria-hidden="true" />
                  ) : (
                    <Lock size={16} aria-hidden="true" />
                  )}
                  {reader.can_send_initial_message ? "Send one" : "Message"}
                </button>
              </div>
            </article>
          ))}
          {user && !readers.length ? <p className="muted">No other readers yet.</p> : null}
        </div>
      </section>

      <section className="form-surface inbox-surface" ref={threadDetailRef}>
        <div className="form-heading">
          <div>
            <h2>Messages</h2>
            <p className="muted">{threads.length} chats</p>
          </div>
        </div>
        <div className="inbox-grid">
          <div className="thread-list">
            {draftReader ? (
              <button className="thread-list-item active-thread" type="button">
                <span>{draftReader.display_name}</span>
                <span className="muted">New conversation</span>
              </button>
            ) : null}
            {threads.map((thread) => (
              <button
                className={
                  selectedThread?.id === thread.id ? "thread-list-item active-thread" : "thread-list-item"
                }
                key={thread.id}
                onClick={() => selectThread(thread.id)}
                type="button"
              >
                <span>{participantNames(thread, user?.id) || thread.subject || "Conversation"}</span>
                <span className="muted">{lastMessagePreview(thread)}</span>
              </button>
            ))}
            {!threads.length && !draftReader ? <p className="muted">No conversations yet.</p> : null}
          </div>
          <div className="thread-detail">
            {selectedThread || draftReader ? (
              <>
                <h3>
                  {selectedThread ? participantNames(selectedThread, user?.id) : draftReader?.display_name}
                </h3>
                <div className="message-list">
                  {selectedThread?.messages.map((message) => (
                    <article
                      className={
                        message.sender_user_id === user?.id
                          ? "message-bubble own-message"
                          : "message-bubble"
                      }
                      key={message.id}
                    >
                      <strong>{message.sender_display_name}</strong>
                      <p>{message.body}</p>
                    </article>
                  ))}
                  {!selectedThread ? <p className="muted">Start the conversation below.</p> : null}
                </div>
                <form className="message-form" onSubmit={handleReply}>
                  <label className="sr-only" htmlFor="reply-body">
                    Message
                  </label>
                  <textarea
                    className="textarea compact-textarea"
                    disabled={!canSendSelectedMessage}
                    id="reply-body"
                    onChange={(event) => setReplyBody(event.target.value)}
                    placeholder={
                      canSendSelectedMessage
                        ? "Message"
                        : "They need to follow you back before more messages."
                    }
                    ref={replyRef}
                    value={replyBody}
                  />
                  <button className="secondary-button" disabled={sending || !canSubmitReply()} type="submit">
                    <Send size={16} aria-hidden="true" />
                    {sending ? "Sending" : "Send"}
                  </button>
                </form>
              </>
            ) : (
              <p className="muted">Choose a reader to start or continue a message thread.</p>
            )}
          </div>
        </div>
        {status ? <p className="form-message success-message">{status}</p> : null}
      </section>
    </div>
  );
}

function ReaderAvatar({ reader }: { reader: AccountDirectoryUser }) {
  if (reader.avatar_data_url) {
    return (
      <Image
        alt={`${reader.display_name} profile`}
        className="reader-card-avatar"
        height={52}
        src={reader.avatar_data_url}
        unoptimized
        width={52}
      />
    );
  }
  return (
    <span className="reader-card-avatar reader-card-avatar-placeholder" aria-hidden="true">
      {reader.display_name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function upsertThread(threads: MessageThread[], updatedThread: MessageThread): MessageThread[] {
  const withoutUpdated = threads.filter((thread) => thread.id !== updatedThread.id);
  return [updatedThread, ...withoutUpdated];
}

function participantNames(thread: MessageThread, currentUserId?: string): string {
  const names = thread.participants
    .filter((participant) => participant.id !== currentUserId)
    .map((participant) => participant.display_name);
  return names.join(", ");
}

function existingThreadForReader(threads: MessageThread[], readerId: string): MessageThread | null {
  return (
    threads.find((thread) =>
      thread.participants.some((participant) => participant.id === readerId),
    ) ?? null
  );
}

function formatProfileRole(role: AccountDirectoryUser["profile_role"]): string {
  if (role === "writer") {
    return "Writer";
  }
  if (role === "writer_reader") {
    return "Writer/reader";
  }
  return "Reader";
}

function messageAllowedText(reader: AccountDirectoryUser): string {
  if (reader.can_send_initial_message) {
    return "You can send one message because you follow this reader.";
  }
  return "Message";
}

function messageRestrictionText(reader: AccountDirectoryUser): string {
  if (!reader.followed_by_me) {
    return "Follow this reader before sending a message.";
  }
  if (reader.message_limit_reached) {
    return "You have already sent one message. They need to follow you back before you can send another.";
  }
  return "You can message readers only after you follow each other.";
}

function lastMessagePreview(thread: MessageThread): string {
  const lastMessage = thread.messages[thread.messages.length - 1];
  if (!lastMessage) {
    return thread.subject || "Conversation";
  }
  return lastMessage.body.length > 56 ? `${lastMessage.body.slice(0, 53)}...` : lastMessage.body;
}
