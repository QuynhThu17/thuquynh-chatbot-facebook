"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAccessToken } from "./auth-storage";

const PUBLIC_PATHS = new Set([
  "/",
  "/auth/login",
  "/auth/register",
  "/_not-found",
]);

export default function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [allowed, setAllowed] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    const isPublic = PUBLIC_PATHS.has(pathname || "/");

    if (!token && !isPublic) {
      setAllowed(false);
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/auth/login?next=${next}`);
    } else {
      setAllowed(true);
    }
  }, [pathname, router]);

  if (!allowed) return null;
  return children as any;
}