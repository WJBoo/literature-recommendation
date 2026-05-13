"use client";

import { ListMusic, ListPlus, Music2, Play, Plus, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  addTrackToMusicPlaylist,
  createMusicPlaylist,
  deleteMusicPlaylist,
  fetchAccountMusicPreferences,
  fetchMusicCatalog,
  fetchMusicPlaylists,
  removeTrackFromMusicPlaylist,
  updateAccountMusicPreferences,
} from "../lib/api";
import type {
  ListeningRecommendation,
  MusicCatalog,
  MusicPlaylist,
  MusicPreferences,
  MusicTrack,
} from "../lib/types";
import { publishListeningRecommendation } from "./GlobalListeningPlayer";

const musicPreferenceStorageKey = "linguaphilia_music_preferences";
const emptyMusicPreferences: MusicPreferences = { tones: [], composers: [] };

export function MusicPreferencesPanel() {
  const [preferences, setPreferences] = useState<MusicPreferences>(() => readStoredMusicPreferences());
  const [preferencesReady, setPreferencesReady] = useState(false);
  const [catalog, setCatalog] = useState<MusicCatalog | null>(null);
  const [playlists, setPlaylists] = useState<MusicPlaylist[]>([]);
  const [activeTrackPickerId, setActiveTrackPickerId] = useState<string | null>(null);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchAccountMusicPreferences()
      .then((accountPreferences) => {
        if (mounted && accountPreferences) {
          setPreferences({
            tones: accountPreferences.tones,
            composers: accountPreferences.composers,
            updated_at: accountPreferences.updated_at,
          });
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (mounted) {
          setPreferencesReady(true);
        }
      });
    void fetchMusicPlaylists()
      .then((items) => {
        if (mounted) {
          setPlaylists(items);
        }
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    void fetchMusicCatalog(preferences)
      .then((payload) => {
        if (mounted) {
          setCatalog(payload);
        }
      })
      .catch(() => {
        if (mounted) {
          setCatalog(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, [preferences]);

  useEffect(() => {
    if (!preferencesReady) {
      return;
    }
    window.localStorage.setItem(musicPreferenceStorageKey, JSON.stringify(preferences));
    void updateAccountMusicPreferences(preferences).catch(() => {
      setStatus("Music preferences are saved on this browser.");
    });
  }, [preferences, preferencesReady]);

  const recommendedTracks = useMemo(() => catalog?.tracks ?? [], [catalog]);

  return (
    <section className="music-page" aria-labelledby="music-heading">
      <div className="page-heading">
        <p className="eyebrow">Music</p>
        <h1 id="music-heading">Musical listening preferences</h1>
        <p className="muted">
          Choose tones and composers you like. Reader pages will still recommend from the current passage, but this page lets you start music from your own listening mood.
        </p>
      </div>

      <div className="music-preference-grid">
        <fieldset className="preference-panel">
          <legend>Tones</legend>
          <div className="preference-chip-grid">
            {Object.entries(catalog?.tones ?? fallbackTones).map(([tone, label]) => (
              <button
                className={`preference-chip ${preferences.tones.includes(tone) ? "active-preference-chip" : ""}`}
                key={tone}
                onClick={() => toggleTone(tone)}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="preference-panel">
          <legend>Composers</legend>
          <div className="preference-chip-grid">
            {(catalog?.composers ?? []).map((composer) => (
              <button
                className={`preference-chip ${preferences.composers.includes(composer) ? "active-preference-chip" : ""}`}
                key={composer}
                onClick={() => toggleComposer(composer)}
                type="button"
              >
                {composer}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="music-actions-row">
        <button className="secondary-button" onClick={clearPreferences} type="button">
          Clear preferences
        </button>
        {status ? <p className="muted">{status}</p> : null}
      </div>

      <section className="section" aria-labelledby="music-recommendations-heading">
        <div className="row-header">
          <div>
            <h2 id="music-recommendations-heading">Recommended listening</h2>
          </div>
        </div>
        <div className="music-track-grid">
          {recommendedTracks.map((track) => (
            <article className="music-track-card" key={track.id}>
              <div className="music-track-heading">
                <Music2 size={20} aria-hidden="true" />
                <div>
                  <h3>{track.title}</h3>
                  <p>{track.composer} · {track.duration}</p>
                </div>
              </div>
              <p className="muted">{track.performer}</p>
              <div className="tag-list">
                {track.tone_tags.slice(0, 3).map((tone) => (
                  <span className="tag" key={tone}>{toneLabel(tone)}</span>
                ))}
              </div>
              <div className="music-track-actions">
                <button
                  className="primary-button"
                  onClick={() => startTrack(track)}
                  type="button"
                >
                  <Play size={16} aria-hidden="true" />
                  Play
                </button>
                <button
                  aria-expanded={activeTrackPickerId === track.id}
                  className="secondary-button"
                  disabled={!playlists.length}
                  onClick={() => {
                    setActiveTrackPickerId((current) => (current === track.id ? null : track.id));
                  }}
                  type="button"
                >
                  <ListPlus size={16} aria-hidden="true" />
                  Add to playlist
                </button>
                {activeTrackPickerId === track.id && playlists.length ? (
                  <div className="playlist-picker" role="group" aria-label={`Choose playlist for ${track.title}`}>
                    <p className="playlist-picker-label">Choose playlist</p>
                    <div className="playlist-picker-options">
                      {playlists.map((playlist) => (
                        <button
                          className="secondary-button"
                          key={playlist.id}
                          onClick={() => void addTrackToPlaylist(playlist.id, track)}
                          type="button"
                        >
                          {playlist.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="music-playlists-heading">
        <div className="row-header">
          <div>
            <h2 id="music-playlists-heading">Your playlists</h2>
          </div>
        </div>
        <form className="playlist-create-form" onSubmit={handleCreatePlaylist}>
          <input
            aria-label="Playlist name"
            className="input"
            onChange={(event) => setNewPlaylistName(event.target.value)}
            placeholder="Playlist name"
            value={newPlaylistName}
          />
          <button className="primary-button" type="submit">
            <Plus size={16} aria-hidden="true" />
            Create
          </button>
        </form>

        {playlists.length ? (
          <div className="music-playlist-grid">
            {playlists.map((playlist) => (
              <article className="music-playlist-card" key={playlist.id}>
                <div className="music-playlist-header">
                  <div>
                    <h3>{playlist.name}</h3>
                    <p className="muted">{playlist.tracks.length} tracks</p>
                  </div>
                  <div className="music-playlist-actions">
                    <button
                      className="secondary-button"
                      disabled={!playlist.tracks.length}
                      onClick={() => startPlaylist(playlist)}
                      type="button"
                    >
                      <ListMusic size={16} aria-hidden="true" />
                      Play
                    </button>
                    <button
                      aria-label={`Delete ${playlist.name}`}
                      className="secondary-button quiet-button"
                      onClick={() => void handleDeletePlaylist(playlist.id)}
                      type="button"
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                </div>
                {playlist.tracks.length ? (
                  <div className="playlist-track-list">
                    {playlist.tracks.map((track) => (
                      <div className="playlist-track-row" key={track.id}>
                        <button onClick={() => startTrack(track, playlist.tracks)} type="button">
                          <span>{track.title}</span>
                          <small>{track.composer}</small>
                        </button>
                        <button
                          aria-label={`Remove ${track.title}`}
                          className="quiet-icon-button"
                          onClick={() => void removeTrackFromPlaylist(playlist.id, track.id)}
                          type="button"
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted">Add tracks from recommended listening.</p>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state-panel">
            <h3>No playlists yet</h3>
            <p className="muted">Create one, then add tracks from recommended listening.</p>
          </div>
        )}
      </section>
    </section>
  );

  function toggleTone(tone: string): void {
    setPreferences((current) => ({
      ...current,
      tones: toggleValue(current.tones, tone),
    }));
  }

  function toggleComposer(composer: string): void {
    setPreferences((current) => ({
      ...current,
      composers: toggleValue(current.composers, composer),
    }));
  }

  function clearPreferences(): void {
    setPreferences(emptyMusicPreferences);
    setStatus("Music preferences cleared.");
  }

  function startTrack(track: MusicTrack, queue: MusicTrack[] = recommendedTracks): void {
    const recommendation: ListeningRecommendation = {
      item_id: "music-preferences",
      title: "Music preferences",
      author: "Linguaphilia",
      tone: track.tone_tags[0] ?? "contemplative",
      tone_label: toneLabel(track.tone_tags[0] ?? "contemplative"),
      summary: "Selected from your music preferences.",
      tracks: queue.length ? queue : [track],
    };
    publishListeningRecommendation(recommendation, track, "switch");
    setStatus(`Playing ${track.title}.`);
  }

  function startPlaylist(playlist: MusicPlaylist): void {
    const firstTrack = playlist.tracks[0];
    if (!firstTrack) {
      return;
    }
    const recommendation: ListeningRecommendation = {
      item_id: `playlist-${playlist.id}`,
      title: playlist.name,
      author: "Linguaphilia",
      tone: firstTrack.tone_tags[0] ?? "contemplative",
      tone_label: toneLabel(firstTrack.tone_tags[0] ?? "contemplative"),
      summary: "Selected from your playlist.",
      tracks: playlist.tracks,
    };
    publishListeningRecommendation(recommendation, firstTrack, "switch");
    setStatus(`Playing ${playlist.name}.`);
  }

  function toneLabel(tone: string): string {
    return catalog?.tones[tone] ?? fallbackTones[tone] ?? tone;
  }

  async function handleCreatePlaylist(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const name = newPlaylistName.trim();
    if (!name) {
      setStatus("Name the playlist first.");
      return;
    }
    try {
      const playlist = await createMusicPlaylist({ name });
      setPlaylists((current) => [playlist, ...current.filter((item) => item.id !== playlist.id)]);
      setNewPlaylistName("");
      setStatus(`${playlist.name} created.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to create playlist.");
    }
  }

  async function handleDeletePlaylist(playlistId: string): Promise<void> {
    try {
      await deleteMusicPlaylist(playlistId);
      setPlaylists((current) => current.filter((playlist) => playlist.id !== playlistId));
      setStatus("Playlist deleted.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to delete playlist.");
    }
  }

  async function addTrackToPlaylist(playlistId: string, track: MusicTrack): Promise<void> {
    try {
      const playlist = await addTrackToMusicPlaylist(playlistId, track);
      setPlaylists((current) => replacePlaylist(current, playlist));
      setActiveTrackPickerId(null);
      setStatus(`${track.title} added to ${playlist.name}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to add track.");
    }
  }

  async function removeTrackFromPlaylist(playlistId: string, trackId: string): Promise<void> {
    try {
      const playlist = await removeTrackFromMusicPlaylist(playlistId, trackId);
      setPlaylists((current) => replacePlaylist(current, playlist));
      setStatus("Track removed.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to remove track.");
    }
  }
}

function readStoredMusicPreferences(): MusicPreferences {
  if (typeof window === "undefined") {
    return emptyMusicPreferences;
  }
  const stored = window.localStorage.getItem(musicPreferenceStorageKey);
  if (!stored) {
    return emptyMusicPreferences;
  }
  try {
    const parsed = JSON.parse(stored) as MusicPreferences;
    return {
      tones: Array.isArray(parsed.tones) ? parsed.tones : [],
      composers: Array.isArray(parsed.composers) ? parsed.composers : [],
      updated_at: typeof parsed.updated_at === "string" ? parsed.updated_at : null,
    };
  } catch {
    return emptyMusicPreferences;
  }
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((candidate) => candidate !== value)
    : [...values, value];
}

function replacePlaylist(playlists: MusicPlaylist[], playlist: MusicPlaylist): MusicPlaylist[] {
  const next = playlists.map((item) => (item.id === playlist.id ? playlist : item));
  return next.some((item) => item.id === playlist.id) ? next : [playlist, ...next];
}

const fallbackTones: Record<string, string> = {
  adventurous: "adventurous and kinetic",
  contemplative: "contemplative and reflective",
  dramatic: "dramatic and theatrical",
  epic: "epic and ceremonial",
  gothic: "shadowed and suspenseful",
  melancholy: "melancholy and inward",
  pastoral: "pastoral and bright",
  playful: "playful and quick-witted",
  romantic: "romantic and intimate",
  serene: "serene and nocturnal",
};
