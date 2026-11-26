"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authApi, tokens } from "@/lib/api";

export function useCurrentUser(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
    enabled: enabled && typeof window !== "undefined" && !!tokens.access,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useLogout() {
  const router = useRouter();
  const qc = useQueryClient();
  return async () => {
    try {
      await authApi.logout();
    } catch {
      /* tokens are discarded locally either way */
    }
    tokens.clear();
    qc.clear();
    router.replace("/login");
  };
}
