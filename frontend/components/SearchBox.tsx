"use client";

import { Bell, Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export function SearchBox({ mode }: { mode?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("query") ?? "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      const modeParam = mode && mode !== "all" ? `&mode=${encodeURIComponent(mode)}` : "";
      router.push(`/search?query=${encodeURIComponent(trimmed)}${modeParam}`);
    }
  }

  return (
    <form className="topbar" onSubmit={handleSubmit}>
      <label className="sr-only" htmlFor="catalog-search">
        Search works, authors, themes
      </label>
      <div className="search-control">
        <Search size={18} aria-hidden="true" />
        <input
          className="search"
          id="catalog-search"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search works, authors, themes"
          value={query}
        />
      </div>
      <button className="secondary-button" type="submit">
        <Search size={18} aria-hidden="true" />
        Search
      </button>
      <Link className="secondary-button" href="/notifications">
        <Bell size={18} aria-hidden="true" />
        Notifications
      </Link>
    </form>
  );
}
