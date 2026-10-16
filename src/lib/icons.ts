export interface CategoryMeta {
  accent: string;
  summary: string;
  svg: string;
}

const USE_CASE_META: Record<string, CategoryMeta> = {
  "Enterprise Knowledge Search": {
    accent: "#0c7c6c",
    summary: "RAG pipelines, semantic search, and internal copilots over enterprise knowledge bases.",
    svg: `<circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M13.2 13.2 17.5 17.5M9 6.5v5M6.5 9h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  },
  "Customer Service Automation": {
    accent: "#d84a1b",
    summary: "Conversational AI agents, contact-center assist, and automated ticket resolution.",
    svg: `<path d="M4 11V9a6 6 0 0 1 12 0v2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><rect x="2.5" y="10.5" width="3" height="4.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="14.5" y="10.5" width="3" height="4.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M16 15v1a2 2 0 0 1-2 2h-3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  },
  "Real-time Analytics": {
    accent: "#2563eb",
    summary: "Streaming inference, operational decisioning, and low-latency telemetry intelligence.",
    svg: `<path d="M3 15.5 7.5 10l3.2 3.2L16.8 5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/><path d="M13.5 5h3.3v3.3" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 17.5h14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
  },
  "IT Operations Automation": {
    accent: "#7c3aed",
    summary: "AIOps, developer productivity copilots, incident triage, and autonomous runbooks.",
    svg: `<rect x="2.5" y="3.5" width="15" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m6 8 2.5 2L6 12M10 12h3.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  "Document Processing": {
    accent: "#0891b2",
    summary: "Multimodal OCR, contract & invoice extraction, clinical notes, and regulatory filings.",
    svg: `<path d="M5.5 2.8h6.3l3.7 3.7v10.7a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1V3.8a1 1 0 0 1 1-1Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M11.5 2.8v4h4M7.5 10.5h5M7.5 13.5h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  },
  "Marketing Personalization": {
    accent: "#db2777",
    summary: "Next-best-action engines, dynamic creative generation, and audience segmentation.",
    svg: `<circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="10" cy="10" r="3.8" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="10" cy="10" r="1.2" fill="currentColor"/>`,
  },
  "Risk Management": {
    accent: "#b45309",
    summary: "Credit underwriting, market exposure modeling, and operational risk forecasting.",
    svg: `<path d="M10 2.6 16.5 5v4.8c0 4.2-2.8 6.8-6.5 8-3.7-1.2-6.5-3.8-6.5-8V5L10 2.6Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M10 7v3.8M10 13.5h.01" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>`,
  },
  "Security and Compliance": {
    accent: "#0f766e",
    summary: "Threat detection, SOC copilot triage, policy governance, and audit automation.",
    svg: `<path d="M10 2.6 16.5 5v4.8c0 4.2-2.8 6.8-6.5 8-3.7-1.2-6.5-3.8-6.5-8V5L10 2.6Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m7.5 10.2 1.8 1.8 3.4-3.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  "Sales Automation": {
    accent: "#ea580c",
    summary: "Deal intelligence, RFP automation, lead scoring, and account copilot workflows.",
    svg: `<rect x="3" y="6" width="14" height="10.5" rx="1.8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M7.2 6V4.5a1 1 0 0 1 1-1h3.6a1 1 0 0 1 1 1V6M3 10.5h14" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  },
  "Data Lake / Data Warehouse Modernization": {
    accent: "#0284c7",
    summary: "Unified lakehouse foundations, vector-ready pipelines, and feature store platforms.",
    svg: `<ellipse cx="10" cy="5.2" rx="6.5" ry="2.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3.5 5.2v4.8c0 1.3 2.9 2.4 6.5 2.4s6.5-1.1 6.5-2.4V5.2M3.5 10v4.8c0 1.3 2.9 2.4 6.5 2.4s6.5-1.1 6.5-2.4V10" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  },
  "Application Refactoring": {
    accent: "#4f46e5",
    summary: "AI-assisted code modernization, legacy mainframe translation, and test generation.",
    svg: `<path d="m6.5 6.5-3.5 3.5 3.5 3.5M13.5 6.5 17 10l-3.5 3.5M11.2 4.8l-2.4 10.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  "Supply Chain Optimization": {
    accent: "#059669",
    summary: "Demand forecasting, inventory replenishment, and dynamic logistics routing.",
    svg: `<path d="M10 2.8 16.8 6.5v7L10 17.2 3.2 13.5v-7L10 2.8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M3.2 6.5 10 10.2l6.8-3.7M10 10.2v7" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  },
  "Predictive Maintenance": {
    accent: "#d97706",
    summary: "Sensor anomaly detection, visual quality inspection, and asset failure prediction.",
    svg: `<circle cx="10" cy="10" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 2.8v2.1M10 15.1v2.1M2.8 10h2.1M15.1 10h2.1M4.9 4.9l1.5 1.5M13.6 13.6l1.5 1.5M15.1 4.9l-1.5 1.5M6.4 13.6l-1.5 1.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  },
  "Fraud Detection": {
    accent: "#dc2626",
    summary: "Real-time payment scoring, anti-money-laundering graphs, and identity verification.",
    svg: `<path d="M6.5 5.2a5.5 5.5 0 0 1 7 0M4.8 8.2a7.5 7.5 0 0 1 10.4 0M7.2 11a3.2 3.2 0 0 1 5.6 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="14.2" r="1.5" fill="currentColor"/>`,
  },
  "System Migration": {
    accent: "#0369a1",
    summary: "AI-accelerated workload migration, GPU cluster onboarding, and platform consolidation.",
    svg: `<path d="M6.2 15.5a3.5 3.5 0 0 1-.5-7 4.8 4.8 0 0 1 9.2-.8 3.2 3.2 0 0 1 .6 6.3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><path d="m10 9.5 0 6.5m-2.4-4.2L10 9.4l2.4 2.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
};

const INDUSTRY_META: Record<string, CategoryMeta> = {
  "Software / SaaS": {
    accent: "#2563eb",
    summary: "Cloud software platforms, developer tools, AI-native SaaS, and digital products.",
    svg: `<rect x="2.5" y="3.5" width="15" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M2.5 7.2h15M7.5 11.2l-1.8 1.6 1.8 1.6M12.5 11.2l1.8 1.6-1.8 1.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  "Financial Services": {
    accent: "#0c7c6c",
    summary: "Banking, capital markets, insurance, payments, and wealth management institutions.",
    svg: `<path d="M3 7.5 10 3.2l7 4.3H3ZM4.8 7.5v7.2M8.2 7.5v7.2M11.8 7.5v7.2M15.2 7.5v7.2M3 16.5h14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  Healthcare: {
    accent: "#0891b2",
    summary: "Hospitals, life sciences, pharma R&D, medical devices, and clinical genomics.",
    svg: `<rect x="3" y="4" width="14" height="12.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M10 7.2v6M7 10.2h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`,
  },
  "Commercial and Professional Services": {
    accent: "#7c3aed",
    summary: "Legal, consulting, accounting, staffing, and B2B enterprise advisory firms.",
    svg: `<rect x="3" y="6" width="14" height="10.5" rx="1.8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M7.2 6V4.5a1 1 0 0 1 1-1h3.6a1 1 0 0 1 1 1V6M3 10.5h14" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  },
  Manufacturing: {
    accent: "#d97706",
    summary: "Industrial automation, electronics, chemicals, semiconductor fabs, and heavy machinery.",
    svg: `<path d="M3 16.8V8.5l4.5 2.5V8.5L12 11V6.2h5v10.6H3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  },
  Retail: {
    accent: "#d84a1b",
    summary: "E-commerce marketplaces, omnichannel merchants, grocery chains, and specialty retail.",
    svg: `<path d="M4.5 6.5h11l-1 10H5.5l-1-10Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M7.5 6.5V5a2.5 2.5 0 0 1 5 0v1.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  },
  "Media and Entertainment": {
    accent: "#db2777",
    summary: "Streaming platforms, gaming studios, publishing houses, sports, and digital media.",
    svg: `<rect x="2.8" y="4" width="14.4" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><polygon points="8.5,7.2 13.5,10 8.5,12.8" fill="currentColor"/>`,
  },
  "Public Sector": {
    accent: "#0369a1",
    summary: "National and municipal governments, civic services, defense, and public agencies.",
    svg: `<path d="M10 3v2.2M5 8.5a5 5 0 0 1 10 0H5ZM3.5 8.5h13M5 8.5v7.5M8.3 8.5v7.5M11.7 8.5v7.5M15 8.5v7.5M3 16.5h14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
  },
  Telecommunications: {
    accent: "#4f46e5",
    summary: "Mobile carriers, broadband networks, 5G operators, and communications infrastructure.",
    svg: `<circle cx="10" cy="9" r="1.6" fill="currentColor"/><path d="M6.8 6a4.5 4.5 0 0 0 0 6M13.2 6a4.5 4.5 0 0 1 0 6M4.5 3.8a7.8 7.8 0 0 0 0 10.4M15.5 3.8a7.8 7.8 0 0 1 0 10.4M10 10.8v6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  },
  Energy: {
    accent: "#059669",
    summary: "Power grids, renewable energy, oil & gas upstream/downstream, and utilities.",
    svg: `<polygon points="11.2,2.5 4.5,11 9.8,11 8.8,17.5 15.5,9 10.2,9" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  },
  Education: {
    accent: "#7c3aed",
    summary: "Universities, K-12 districts, research institutions, and EdTech learning platforms.",
    svg: `<path d="M2.5 8 10 4.2 17.5 8 10 11.8 2.5 8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M5.5 9.8v4.2c0 1.4 2 2.5 4.5 2.5s4.5-1.1 4.5-2.5V9.8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  },
  "Travel and Hospitality": {
    accent: "#0284c7",
    summary: "Airlines, hotel groups, online travel agencies, cruise lines, and mobility services.",
    svg: `<path d="M17.2 3.8 2.8 9.5l5.4 2.1 2.1 5.4 6.9-13.2Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  },
  Automotive: {
    accent: "#ea580c",
    summary: "Automakers, EV platforms, autonomous driving systems, and Tier-1 suppliers.",
    svg: `<path d="M4.8 11 6.4 6.2h7.2L15.2 11M3.2 11h13.6v4.2H3.2V11Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><circle cx="6.2" cy="15.2" r="1.6" fill="currentColor"/><circle cx="13.8" cy="15.2" r="1.6" fill="currentColor"/>`,
  },
  "Consumer Goods": {
    accent: "#db2777",
    summary: "CPG brands, food & beverage, cosmetics, apparel, and household products.",
    svg: `<path d="M6 3.5h8l2.5 4.2-7.5 9.3-7.5-9.3L6 3.5Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M2.5 7.7h15" fill="none" stroke="currentColor" stroke-width="1.6"/>`,
  },
  Logistics: {
    accent: "#059669",
    summary: "Freight carriers, parcel delivery, maritime shipping, warehousing, and 3PL networks.",
    svg: `<rect x="2.5" y="5.5" width="9.5" height="8.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 8h3.2l2.3 3v3H12V8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><circle cx="6.2" cy="15" r="1.6" fill="currentColor"/><circle cx="14.8" cy="15" r="1.6" fill="currentColor"/>`,
  },
  Nonprofit: {
    accent: "#e11d48",
    summary: "NGOs, humanitarian agencies, foundations, and mission-driven civic organizations.",
    svg: `<path d="M10 16.8s-6.5-4.1-6.5-8.6A3.6 3.6 0 0 1 10 5.8a3.6 3.6 0 0 1 6.5 2.4c0 4.5-6.5 8.6-6.5 8.6Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  },
  "Real Estate and Construction": {
    accent: "#b45309",
    summary: "Property developers, engineering & construction, REITs, and smart facilities.",
    svg: `<rect x="4" y="3.5" width="8.5" height="13.5" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="12.5" y="8.5" width="4.5" height="8.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M6.8 6.8h2.8M6.8 9.8h2.8M6.8 12.8h2.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
  },
  Agriculture: {
    accent: "#16a34a",
    summary: "Precision farming, agribusiness, crop science, and food supply chains.",
    svg: `<path d="M10 17V9m0 0C10 5.2 13 3.2 16.5 3.5 16.8 7 14.8 10 10 9Zm0 2c0-3.2-2.6-5-5.8-4.8-.2 3.2 1.6 5.6 5.8 4.8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
};

export function useCaseMeta(name: string): CategoryMeta {
  return (
    USE_CASE_META[name] ?? {
      accent: "#0c7c6c",
      summary: "Production AI implementation pattern documented across verified customer deployments.",
      svg: `<path d="M10 2.5 12.2 7.8 17.5 10l-5.3 2.2L10 17.5 7.8 12.2 2.5 10l5.3-2.2L10 2.5Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
    }
  );
}

export function industryMeta(name: string): CategoryMeta {
  return (
    INDUSTRY_META[name] ?? {
      accent: "#2563eb",
      summary: "Verified enterprise AI deployments and production references in this sector.",
      svg: `<rect x="3.5" y="3.5" width="13" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M7 7.5h6M7 10.5h6M7 13.5h4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
    }
  );
}
