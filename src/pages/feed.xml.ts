import type { APIRoute } from "astro";
import { caseStudies } from "../lib/caseStudies";
import { isParseableDate } from "../lib/analytics";
import { caseHref } from "../lib/paths";

const escapeXml = (value: string) =>
  value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");

export const GET: APIRoute = ({ site }) => {
  const base = site ?? new URL("https://usecase.genisisiq.com");
  const records = caseStudies
    .filter((record) => !record.is_sample)
    .sort((left, right) => (right.collected_at ?? "").localeCompare(left.collected_at ?? ""))
    .slice(0, 100);
  const lastBuildDate = records.find((record) => isParseableDate(record.collected_at ?? ""))?.collected_at;
  const items = records.map((record) => {
    const link = new URL(caseHref(record.slug), base).toString();
    const date = record.collected_at && isParseableDate(record.collected_at)
      ? new Date(record.collected_at).toUTCString()
      : record.published_date && isParseableDate(record.published_date)
        ? new Date(record.published_date).toUTCString()
        : "";
    return `<item>
      <title>${escapeXml(`${record.customer_name} — ${record.use_case_category[0] ?? record.vendor}`)}</title>
      <link>${escapeXml(link)}</link>
      <guid isPermaLink="true">${escapeXml(link)}</guid>
      ${date ? `<pubDate>${date}</pubDate>` : ""}
      <description>${escapeXml(record.business_problem)}</description>
      <category>${escapeXml(record.vendor)}</category>
    </item>`;
  }).join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Use Case Intelligence — latest use cases</title>
    <link>${escapeXml(base.toString())}</link>
    <description>Newly collected real-world AI customer use cases with evidence, provenance, and comparable scoring.</description>
    ${lastBuildDate ? `<lastBuildDate>${new Date(lastBuildDate).toUTCString()}</lastBuildDate>` : ""}
    ${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
};
