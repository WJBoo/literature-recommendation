"use client";

import { ChevronsDownUp, ExternalLink, Headphones, ListPlus, Music2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { addTrackToMusicPlaylist, fetchMusicPlaylists, getAccountToken } from "../lib/api";
import type { ListeningRecommendation, MusicPlaylist, MusicTrack } from "../lib/types";

export const LISTENING_RECOMMENDATION_EVENT = "linguaphilia:listening-recommendation";

type ListeningAction = "suggest" | "switch";

type ListeningRecommendationEvent = CustomEvent<{
  action?: ListeningAction;
  recommendation: ListeningRecommendation;
  track?: MusicTrack;
}>;

export function publishListeningRecommendation(
  recommendation: ListeningRecommendation,
  track?: MusicTrack,
  action: ListeningAction = "suggest",
): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(
    new CustomEvent(LISTENING_RECOMMENDATION_EVENT, {
      detail: { action, recommendation, track },
    }),
  );
}

export function GlobalListeningPlayer() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const shouldPlayAfterSwitch = useRef(false);
  const [currentTrack, setCurrentTrack] = useState<MusicTrack | null>(null);
  const [suggestedTrack, setSuggestedTrack] = useState<MusicTrack | null>(null);
  const [recommendation, setRecommendation] = useState<ListeningRecommendation | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [playlists, setPlaylists] = useState<MusicPlaylist[]>([]);
  const [playlistMenuOpen, setPlaylistMenuOpen] = useState(false);
  const [loadingPlaylists, setLoadingPlaylists] = useState(false);
  const [playlistStatus, setPlaylistStatus] = useState<string | null>(null);

  useEffect(() => {
    function handleRecommendation(event: Event) {
      const { action = "suggest", recommendation: nextRecommendation, track } =
        (event as ListeningRecommendationEvent).detail;
      const recommendedTrack = track ?? nextRecommendation.tracks[0] ?? null;
      if (!recommendedTrack) {
        return;
      }

      setRecommendation(nextRecommendation);
      setSuggestedTrack(recommendedTrack);
      if (action === "switch") {
        shouldPlayAfterSwitch.current = true;
        setCurrentTrack(recommendedTrack);
        return;
      }

      setCurrentTrack((existingTrack) => existingTrack ?? recommendedTrack);
    }

    window.addEventListener(LISTENING_RECOMMENDATION_EVENT, handleRecommendation);
    return () => window.removeEventListener(LISTENING_RECOMMENDATION_EVENT, handleRecommendation);
  }, []);

  useEffect(() => {
    if (!currentTrack || !shouldPlayAfterSwitch.current) {
      return;
    }
    shouldPlayAfterSwitch.current = false;
    const audio = audioRef.current;
    if (!audio) {
      return;
    }
    audio.load();
    void audio.play().catch(() => {
      setIsPlaying(false);
    });
  }, [currentTrack]);


  if (!currentTrack) {
    return null;
  }

  const activeTrack = currentTrack;
  const hasNewSuggestion = Boolean(
    suggestedTrack && suggestedTrack.id !== activeTrack.id,
  );

  return (
    <aside className={`global-listening-player ${expanded ? "" : "compact-listening-player"}`}>
      <div className="global-listening-header">
        <button
          aria-label={expanded ? "Collapse listening player" : "Expand listening player"}
          className="global-listening-title"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          <Headphones size={17} aria-hidden="true" />
          <span>{isPlaying ? "Listening" : "Musical pairing"}</span>
          <ChevronsDownUp size={14} aria-hidden="true" />
        </button>
        {hasNewSuggestion ? (
          <button
            className="listening-switch-button"
            onClick={() => switchToTrack(suggestedTrack)}
            type="button"
          >
            Switch to recommendation
          </button>
        ) : null}
      </div>

      <audio
        className={expanded ? "global-audio-control" : "global-hidden-audio"}
        controls
        onEnded={playNextRecommendedTrack}
        onPause={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
        preload="metadata"
        ref={audioRef}
        src={activeTrack.audio_url}
      />

      {expanded ? (
        <div className="global-listening-body">
          <div className="global-listening-track">
            <Music2 size={19} aria-hidden="true" />
            <div>
              <h3>{activeTrack.title}</h3>
              <p>
                {activeTrack.composer} · {activeTrack.performer}
              </p>
            </div>
          </div>
          {recommendation ? (
            <p className="global-listening-reason">
              Recommended here for a {recommendation.tone_label} passage.
            </p>
          ) : null}
          <div className="global-listening-actions">
            <button
              aria-expanded={playlistMenuOpen}
              className="secondary-button global-playlist-button"
              onClick={() => void togglePlaylistMenu()}
              type="button"
            >
              <ListPlus size={15} aria-hidden="true" />
              Add to playlist
            </button>
            {playlistStatus ? <span className="global-playlist-status">{playlistStatus}</span> : null}
            {playlistMenuOpen ? (
              <div className="global-playlist-menu" role="group" aria-label={`Choose playlist for ${activeTrack.title}`}>
                {loadingPlaylists ? <p className="muted">Loading playlists...</p> : null}
                {!loadingPlaylists && playlists.length ? (
                  <div className="global-playlist-options">
                    {playlists.map((playlist) => (
                      <button
                        className="secondary-button"
                        key={playlist.id}
                        onClick={() => void addCurrentTrackToPlaylist(playlist.id)}
                        type="button"
                      >
                        {playlist.name}
                      </button>
                    ))}
                  </div>
                ) : null}
                {!loadingPlaylists && !playlists.length ? (
                  <p className="muted">Create a playlist in Music first.</p>
                ) : null}
              </div>
            ) : null}
          </div>
          {hasNewSuggestion && suggestedTrack ? (
            <div className="global-listening-suggestion">
              <span>
                Suggested now: <strong>{suggestedTrack.title}</strong>
              </span>
              <button onClick={() => switchToTrack(suggestedTrack)} type="button">
                Switch
              </button>
            </div>
          ) : null}
          <div className="listening-attribution">
            <span>{activeTrack.license}</span>
            <a href={activeTrack.source_url} rel="noreferrer" target="_blank">
              Source <ExternalLink size={13} aria-hidden="true" />
            </a>
          </div>
        </div>
      ) : null}
    </aside>
  );

  async function togglePlaylistMenu(): Promise<void> {
    const nextOpen = !playlistMenuOpen;
    setPlaylistStatus(null);
    if (!nextOpen) {
      setPlaylistMenuOpen(false);
      return;
    }
    if (!getAccountToken()) {
      setPlaylistMenuOpen(false);
      setPlaylistStatus("Sign in to add music to playlists.");
      return;
    }
    setPlaylistMenuOpen(true);
    await refreshPlaylists();
  }

  async function refreshPlaylists(): Promise<void> {
    setLoadingPlaylists(true);
    try {
      const items = await fetchMusicPlaylists();
      setPlaylists(items);
    } catch (error) {
      setPlaylistStatus(error instanceof Error ? error.message : "Unable to load playlists.");
    } finally {
      setLoadingPlaylists(false);
    }
  }

  async function addCurrentTrackToPlaylist(playlistId: string): Promise<void> {
    try {
      const playlist = await addTrackToMusicPlaylist(playlistId, normalizeMusicTrack(activeTrack));
      setPlaylists((current) => replaceMusicPlaylist(current, playlist));
      setPlaylistMenuOpen(false);
      setPlaylistStatus(`Added to ${playlist.name}.`);
    } catch (error) {
      setPlaylistStatus(error instanceof Error ? error.message : "Unable to add this track.");
    }
  }

  function switchToTrack(track: MusicTrack | null): void {
    if (!track) {
      return;
    }
    shouldPlayAfterSwitch.current = true;
    setCurrentTrack(track);
  }

  function playNextRecommendedTrack(): void {
    const queue = recommendation?.tracks ?? [];
    if (suggestedTrack && suggestedTrack.id !== activeTrack.id) {
      switchToTrack(suggestedTrack);
      return;
    }
    if (!queue.length) {
      setIsPlaying(false);
      return;
    }
    const currentIndex = queue.findIndex((track) => track.id === activeTrack.id);
    const nextTrack = queue[currentIndex >= 0 ? (currentIndex + 1) % queue.length : 0];
    switchToTrack(nextTrack);
  }
}


function normalizeMusicTrack(track: MusicTrack): MusicTrack {
  return {
    id: track.id,
    title: track.title,
    composer: track.composer,
    performer: track.performer,
    duration: track.duration,
    tone_tags: track.tone_tags,
    audio_url: track.audio_url,
    source_url: track.source_url,
    license: track.license,
    reason: track.reason,
  };
}

function replaceMusicPlaylist(playlists: MusicPlaylist[], playlist: MusicPlaylist): MusicPlaylist[] {
  const next = playlists.map((item) => (item.id === playlist.id ? playlist : item));
  return next.some((item) => item.id === playlist.id) ? next : [playlist, ...next];
}
