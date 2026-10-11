import type { APIRoute } from "astro";
import { caseStudies } from "../../../lib/caseStudies";
import { href } from "../../../lib/paths";
import { groupByWeek } from "../../../lib/weeks";

// Public manifest of weekly shards: /data/weeks/index.json.
export const GET: APIRoute = () => {
  const weeks = groupByWeek(caseStudies).map((group) => ({
    week: group.week,
    label: group.label,
    count: group.records.length,
    url: href(`/data/weeks/${group.week}.json`),
  }));
  const body = { total: caseStudies.length, weeks };
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
};
