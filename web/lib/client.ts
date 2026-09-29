"use client";

import { useSyncExternalStore } from "react";

// Browser-only values for statically pre-built pages: the build has no window, time zone or
// storage, so these return a neutral value during the build/hydration and the real one after.
const noop = () => () => {};

export const useHydrated = () => useSyncExternalStore(noop, () => true, () => false);

export const useSearch = () => useSyncExternalStore(noop, () => window.location.search, () => "");

export function readStorage(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }   // blocked / private mode
}

export function writeStorage(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}
