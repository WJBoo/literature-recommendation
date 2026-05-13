"use client";

import { ChevronDown, Headphones, Music2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { fetchListeningRecommendation } from "../lib/api";
import { publishListeningRecommendation } from "./GlobalListeningPlayer";
import type { ListeningRecommendation, MusicTrack } from "../lib/types";

export function ListeningPanel({ excerptId }: { excerptId: string }) {
  const [recommendation, setRecommendation] = useState<ListeningRecommendation | null>(null);
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    void fetchListeningRecommendation(excerptId)
      .then((payload) => {
        if (mounted) {
          const recommendedTrack = payload.tracks[0] ?? null;
          setRecommendation(payload);
          setActiveTrackId(recommendedTrack?.id ?? null);
          publishListeningRecommendation(payload, recommendedTrack ?? undefined);
        }
      })
      .catch(() => {
        if (mounted) {
          setRecommendation(null);
          setActiveTrackId(null);
          setOpen(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [excerptId]);

  const activeTrack = useMemo(() => {
    if (!recommendation?.tracks.length) {
      return null;
    }
    return recommendation.tracks.find((track) => track.id === activeTrackId) ?? recommendation.tracks[0];
  }, [activeTrackId, recommendation]);

  if (!recommendation || !activeTrack) {
    return null;
  }

  return (
    <section className="reader-listening-compact" aria-label="Musical pairing">
      <button
        aria-expanded={open}
        className={open ? "secondary-button reader-pairing-button active-button" : "secondary-button reader-pairing-button"}
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <Headphones size={18} aria-hidden="true" />
        Pairing
        <span className="reader-pairing-track">{activeTrack.title}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>

      {open ? (
        <div className="reader-pairing-popover" role="dialog" aria-label="Musical pairing recommendation">
          <div className="reader-pairing-summary">
            <span className="listening-tone compact-listening-tone">
              <Headphones size={14} aria-hidden="true" />
              {recommendation.tone_label}
            </span>
            <p>{recommendation.summary}</p>
          </div>

          <div className="reader-pairing-current">
            <Music2 size={18} aria-hidden="true" />
            <div>
              <h3>{activeTrack.title}</h3>
              <p>
                {activeTrack.composer} · {activeTrack.performer}
              </p>
            </div>
          </div>
          <button
            className="primary-button reader-pairing-switch"
            onClick={() => publishListeningRecommendation(recommendation, activeTrack, "switch")}
            type="button"
          >
            Switch player to this track
          </button>

          <div className="reader-pairing-options" aria-label="Recommended musical pairings">
            {recommendation.tracks.map((track) => (
              <TrackButton
                active={track.id === activeTrack.id}
                key={track.id}
                onSelect={() => {
                  setActiveTrackId(track.id);
                  publishListeningRecommendation(recommendation, track);
                }}
                track={track}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TrackButton({
  active,
  onSelect,
  track,
}: {
  active: boolean;
  onSelect: () => void;
  track: MusicTrack;
}) {
  return (
    <button
      className={`reader-pairing-track-button ${active ? "active-listening-track" : ""}`}
      onClick={onSelect}
      type="button"
    >
      <span>{track.title}</span>
      <small>
        {track.composer} · {track.duration}
      </small>
    </button>
  );
}
