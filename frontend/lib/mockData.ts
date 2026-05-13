import type { RecommendationSection, Work } from "./types";

export const featuredWorks: Work[] = [
  {
    id: "gutenberg-1342",
    title: "Pride and Prejudice",
    author: "Jane Austen",
    form: "Novel",
    reason: "Matches **romance**, **satire**, and **social observation**",
    excerpt: "A quick-minded passage about first impressions and private judgment.",
    tags: ["Romance", "Satire", "Manners"],
  },
  {
    id: "gutenberg-1041",
    title: "The Sonnets",
    author: "William Shakespeare",
    form: "Poetry",
    reason: "For your interest in **love**, **time**, and **lyric form**",
    excerpt: "A compact argument with beauty, memory, and devotion.",
    tags: ["Poetry", "Love", "Time"],
  },
  {
    id: "gutenberg-2701",
    title: "Moby-Dick",
    author: "Herman Melville",
    form: "Novel",
    reason: "Tuned to **philosophical** and **oceanic** language",
    excerpt: "A meditation on obsession, fate, and pursuit.",
    tags: ["Epic", "Sea", "Philosophy"],
  },
  {
    id: "gutenberg-84",
    title: "Frankenstein",
    author: "Mary Wollstonecraft Shelley",
    form: "Novel",
    reason: "Picked for **gothic mood** and **moral pressure**",
    excerpt: "An anxious passage about creation, responsibility, and dread.",
    tags: ["Gothic", "Science", "Ambition"],
  },
];

export const recommendationSections: RecommendationSection[] = [
  {
    title: "For You",
    subtitle: "",
    works: featuredWorks,
  },
  {
    title: "Romance",
    subtitle: "",
    works: featuredWorks.filter((work) => work.tags.includes("Romance") || work.tags.includes("Love")),
  },
  {
    title: "Epic Poetry",
    subtitle: "",
    works: featuredWorks.filter((work) => work.tags.includes("Epic") || work.form === "Poetry"),
  },
];

export function getWork(id: string): Work {
  return featuredWorks.find((work) => work.id === id) ?? featuredWorks[0];
}
