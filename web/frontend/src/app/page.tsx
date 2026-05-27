"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const t = typeof window !== "undefined" && window.localStorage.getItem("se_coach_token");
    router.replace(t ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
