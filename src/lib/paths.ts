// Every internal link goes through `href` so the site works both at the root
// (local dev) and under the GitHub Pages project sub-path (e.g. /usecase/).
const base = import.meta.env.BASE_URL.replace(/\/$/, "");

export function href(path = "/"): string {
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function caseHref(slug: string): string {
  return href(`/cases/${slug}/`);
}
