import { Suspense } from "react";
import { SearchBox } from "./SearchBox";

export function TopBar() {
  return (
    <Suspense fallback={<div className="topbar" aria-hidden="true" />}>
      <SearchBox />
    </Suspense>
  );
}
