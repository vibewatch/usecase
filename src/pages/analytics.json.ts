import type { APIRoute } from "astro";
import { generatedAnalytics } from "../lib/generatedAnalytics";

export const GET: APIRoute = () =>
  new Response(JSON.stringify(generatedAnalytics), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
