import type { APIRoute, GetStaticPaths } from "astro";
import { caseStudies } from "../../../lib/caseStudies";
import { groupByWeek, toCardRecord } from "../../../lib/weeks";

// One static JSON shard per collection week: /data/weeks/<week>.json.
// The dashboard ships the newest weeks inline and fetches older shards on demand.
export const getStaticPaths = (() =>
  groupByWeek(caseStudies).map((group) => ({ params: { week: group.week } }))) satisfies GetStaticPaths;

export const GET: APIRoute = ({ params }) => {
  const group = groupByWeek(caseStudies).find((entry) => entry.week === params.week);
  const body = {
    week: params.week,
    label: group?.label ?? "",
    count: group?.records.length ?? 0,
    records: (group?.records ?? []).map(toCardRecord),
  };
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
};
