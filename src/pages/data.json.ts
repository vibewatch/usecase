import type { APIRoute } from "astro";
import { caseStudies } from "../lib/caseStudies";

export const GET: APIRoute = () =>
  new Response(JSON.stringify(caseStudies, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": 'attachment; filename="use-case-intelligence.json"',
      "Cache-Control": "public, max-age=3600",
    },
  });
