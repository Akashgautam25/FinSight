"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { reportClientError } from "@/lib/errors";

/** Contains a rendering error to one part of the page and shows `fallback` instead. */
export class SafeBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error("Rendering error contained:", error);
    reportClientError(error, "safe-boundary", info.componentStack ?? undefined);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
