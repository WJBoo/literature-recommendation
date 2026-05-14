"use client";

import { Bell, LogIn, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  fetchCurrentAccount,
  getAccountToken,
  getStoredAccountUser,
} from "../lib/api";
import type { AccountUser } from "../lib/types";

export function AccountTopNav() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    let mounted = true;

    function refreshFromStorage() {
      if (!mounted) {
        return;
      }
      setUser(getStoredAccountUser());
      setHasToken(Boolean(getAccountToken()));
    }

    refreshFromStorage();
    if (getAccountToken()) {
      void fetchCurrentAccount()
        .then((account) => {
          if (mounted) {
            setUser(account);
            setHasToken(Boolean(getAccountToken()));
          }
        })
        .catch(() => {
          if (mounted) {
            refreshFromStorage();
          }
        });
    }

    window.addEventListener("storage", refreshFromStorage);
    window.addEventListener("literature-account-session", refreshFromStorage);
    return () => {
      mounted = false;
      window.removeEventListener("storage", refreshFromStorage);
      window.removeEventListener("literature-account-session", refreshFromStorage);
    };
  }, []);

  if (!hasToken) {
    return (
      <Link className="primary-button account-signin-button" href="/profile">
        <LogIn size={18} aria-hidden="true" />
        Sign In
      </Link>
    );
  }

  return (
    <div className="account-topnav">
      <Link className="secondary-button account-profile-button" href="/profile">
        <UserRound size={18} aria-hidden="true" />
        <span>{user?.display_name ?? "Profile"}</span>
      </Link>
      <Link className="secondary-button account-notifications-button" href="/notifications">
        <Bell size={18} aria-hidden="true" />
        Notifications
      </Link>
    </div>
  );
}
