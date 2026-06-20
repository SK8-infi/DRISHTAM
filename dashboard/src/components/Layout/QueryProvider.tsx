"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 5 * 60_000,       // 5 min — data is static per session
          gcTime: 10 * 60_000,         // 10 min — keep unused queries longer
          retry: 1,
          refetchOnWindowFocus: false,  // No refetch on tab switch
          refetchOnReconnect: false,    // No refetch on reconnect
        },
      },
    })
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
