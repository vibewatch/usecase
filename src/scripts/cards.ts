// Client-side card rendering shared by the explore page. Cards are cloned from
// the server-rendered <CaseCard> template so markup stays in one place.

export interface CardData {
  url: string;
  vendor: string;
  vendorMark: string;
  vendorColor: string;
  customer: string;
  industry: string;
  region: string;
  useCases: string[];
  products: string;
  problem: string;
  metric: string;
  published: string;
  maturity: number;
  sample: boolean;
}

/** Pagefind result metadata (set on each case page) -> card fields. */
export function cardFromMeta(url: string, meta: Record<string, string>): CardData {
  return {
    url,
    vendor: meta.vendor ?? "",
    vendorMark: meta.mark ?? "",
    vendorColor: meta.color ?? "#64748b",
    customer: meta.title ?? "",
    industry: meta.industry ?? "",
    region: meta.region ?? "",
    useCases: (meta.usecases ?? "").split("|").filter(Boolean),
    products: meta.products ?? "",
    problem: meta.problem ?? "",
    metric: meta.metric ?? "",
    published: meta.published ?? "",
    maturity: Number(meta.maturity ?? 0),
    sample: meta.sample === "1",
  };
}

function slot(root: Element, name: string): HTMLElement {
  return root.querySelector<HTMLElement>(`[data-slot="${name}"]`)!;
}

export function buildCard(template: HTMLTemplateElement, card: CardData): HTMLAnchorElement | null {
  const prototype = template.content.firstElementChild;
  if (!prototype) return null;
  const node = prototype.cloneNode(true) as HTMLAnchorElement;
  node.href = card.url;
  const mark = slot(node, "mark");
  mark.textContent = card.vendorMark;
  mark.style.setProperty("--vendor", card.vendorColor);
  slot(node, "vendor").textContent = card.vendor;
  slot(node, "sample").hidden = !card.sample;
  slot(node, "published").textContent = card.published;
  slot(node, "customer").textContent = card.customer;
  slot(node, "industry").textContent = card.industry;
  slot(node, "region").textContent = card.region;
  slot(node, "problem").textContent = card.problem;
  const metric = slot(node, "metric");
  metric.textContent = card.metric;
  metric.hidden = !card.metric;
  slot(node, "usecases").replaceChildren(
    ...card.useCases.slice(0, 2).map((useCase) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = useCase;
      return tag;
    }),
  );
  slot(node, "products").textContent = card.products;
  const maturity = slot(node, "maturity");
  maturity.title = `Maturity ${card.maturity}/6`;
  maturity.setAttribute("aria-label", `Maturity ${card.maturity} of 6`);
  maturity.querySelectorAll(".maturity__dot").forEach((dot, index) => {
    dot.classList.toggle("is-on", index < card.maturity);
  });
  return node;
}
