"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { persistQueryClient } from "@tanstack/query-persist-client-core";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 60 * 60 * 1000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        retry: (failureCount, error: unknown) => {
          const status = (() => {
            if (typeof error === "object" && error !== null) {
              const obj = error as { status?: number; response?: { status?: number } };
              return obj.status ?? obj.response?.status;
            }
            return undefined;
          })();
          if (status === 401) return false;
          return failureCount < 2;
        },
      },
    },
  }));

  useEffect(() => {
    if (typeof window === "undefined") return;
    const persister = createSyncStoragePersister({ storage: window.localStorage });
    persistQueryClient({ queryClient: client, persister, maxAge: 24 * 60 * 60 * 1000 });
  }, [client]);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
