// Vendor identity marks, categories, and SVG brand logos.
export interface VendorIdentity {
  color: string;
  mark: string;
  category: string;
  svg: string;
}

const VENDOR_STYLES: Record<string, VendorIdentity> = {
  Microsoft: {
    color: "#0078d4",
    mark: "MS",
    category: "Cloud & Hyperscaler",
    svg: `<rect x="3" y="3" width="8.2" height="8.2" rx="1" fill="#F25022"/><rect x="12.8" y="3" width="8.2" height="8.2" rx="1" fill="#7FBA00"/><rect x="3" y="12.8" width="8.2" height="8.2" rx="1" fill="#00A4EF"/><rect x="12.8" y="12.8" width="8.2" height="8.2" rx="1" fill="#FFB900"/>`,
  },
  "Google Cloud": {
    color: "#4285f4",
    mark: "GC",
    category: "Cloud & Hyperscaler",
    svg: `<path d="M15.2 7.2a5.5 5.5 0 0 0-9.9 2.1A4.2 4.2 0 0 0 6.2 17.5h11a3.8 3.8 0 0 0 .6-7.5 5.4 5.4 0 0 0-2.6-2.8Z" fill="none"/><path d="M12 5.2c1.8 0 3.4.8 4.4 2.2l2.1-2.1A8.3 8.3 0 0 0 4.2 9.4l2.7.7A5.5 5.5 0 0 1 12 5.2Z" fill="#EA4335"/><path d="M19.8 11.2a5.8 5.8 0 0 0-1.3-3.8l-2.1 2.1c.6.6.9 1.4.9 2.3 0 1.6-1.3 2.9-2.9 2.9H11v2.8h3.4a5.7 5.7 0 0 0 5.4-6.3Z" fill="#4285F4"/><path d="M6.6 14.7A2.9 2.9 0 0 1 6.9 9.4l-2.7-.7a5.7 5.7 0 0 0 2.4 8.8h4.4v-2.8H6.6Z" fill="#FBBC05"/><path d="M11 14.7h3.8v2.8H9.2a5.7 5.7 0 0 1-2.6-.6l2-2.2h2.4Z" fill="#34A853"/>`,
  },
  AWS: {
    color: "#ff9900",
    mark: "AWS",
    category: "Cloud & Hyperscaler",
    svg: `<path d="M4.2 14.8c4.2 2.9 11.2 3.1 15.3.4" fill="none" stroke="#FF9900" stroke-width="2.1" stroke-linecap="round"/><path d="M17.8 13.7l2.5 1.1-.8 2.6" fill="none" stroke="#FF9900" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/><text x="12" y="11.5" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.4" font-weight="800" letter-spacing="-0.3" fill="#232F3E">aws</text>`,
  },
  IBM: {
    color: "#0f62fe",
    mark: "IBM",
    category: "Enterprise & Cloud",
    svg: `<g fill="#0F62FE"><rect x="2.5" y="6.2" width="19" height="1.25" rx=".4"/><rect x="2.5" y="8.4" width="19" height="1.25" rx=".4"/><rect x="3.3" y="10.6" width="17.4" height="1.25" rx=".4"/><rect x="3.3" y="12.8" width="17.4" height="1.25" rx=".4"/><rect x="2.5" y="15" width="19" height="1.25" rx=".4"/><rect x="2.5" y="17.2" width="19" height="1.25" rx=".4"/></g><text x="12" y="15.4" text-anchor="middle" font-family="ui-monospace, monospace" font-size="9.5" font-weight="900" fill="#ffffff" stroke="#0F62FE" stroke-width=".5">IBM</text>`,
  },
  OpenAI: {
    color: "#10a37f",
    mark: "OA",
    category: "Foundation Models & AI",
    svg: `<g fill="none" stroke="#10A37F" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.2"/><path d="M12 3.3a4.3 4.3 0 0 1 4.1 3v5.2"/><path d="M19.5 7.7a4.3 4.3 0 0 1-.5 5l-4.5 2.6"/><path d="M19.5 16.3a4.3 4.3 0 0 1-4.6 2l-4.5-2.6"/><path d="M12 20.7a4.3 4.3 0 0 1-4.1-3v-5.2"/><path d="M4.5 16.3a4.3 4.3 0 0 1 .5-5l4.5-2.6"/><path d="M4.5 7.7a4.3 4.3 0 0 1 4.6-2l4.5 2.6"/></g>`,
  },
  Databricks: {
    color: "#ff3621",
    mark: "DB",
    category: "Data & AI Platform",
    svg: `<path d="M12 3.2 20.2 7.8 12 12.4 3.8 7.8 12 3.2Z" fill="#FF3621"/><path d="M20.2 11.7 12 16.3 3.8 11.7" fill="none" stroke="#FF3621" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><path d="M20.2 15.6 12 20.2 3.8 15.6" fill="none" stroke="#FF3621" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  NVIDIA: {
    color: "#76b900",
    mark: "NV",
    category: "AI Compute & Silicon",
    svg: `<path d="M3.5 12c2.2-4.2 6.2-6.2 10.6-5.2 3.2.7 5.5 2.9 6.4 5.2-1.8 3.6-5.6 5.6-9.8 5-3.1-.4-5.6-2.3-7.2-5Z" fill="none" stroke="#76B900" stroke-width="2.1" stroke-linejoin="round"/><circle cx="12.5" cy="12" r="2.7" fill="#76B900"/><path d="M9.5 12c.8-1.8 2.7-2.6 4.6-2" fill="none" stroke="#1a1a1a" stroke-width="1.2" stroke-linecap="round"/>`,
  },
  "Baidu AI Cloud": {
    color: "#2932e1",
    mark: "BD",
    category: "China Cloud & AI",
    svg: `<g fill="#2932E1"><ellipse cx="7.1" cy="7.8" rx="1.6" ry="2.2" transform="rotate(-18 7.1 7.8)"/><ellipse cx="10.2" cy="5.8" rx="1.5" ry="2.2" transform="rotate(-5 10.2 5.8)"/><ellipse cx="13.8" cy="5.8" rx="1.5" ry="2.2" transform="rotate(5 13.8 5.8)"/><ellipse cx="16.9" cy="7.8" rx="1.6" ry="2.2" transform="rotate(18 16.9 7.8)"/><path d="M7.4 13.5c0-2.3 2.1-4.1 4.6-4.1s4.6 1.8 4.6 4.1c0 2.6-1.8 4.9-4.6 4.9s-4.6-2.3-4.6-4.9Z"/></g><path d="M9.8 14.8h4.4" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>`,
  },
  "Alibaba Cloud": {
    color: "#ff6a00",
    mark: "AC",
    category: "China Cloud & AI",
    svg: `<path d="M8.8 6.5H6.2a2.8 2.8 0 0 0-2.8 2.8v5.4a2.8 2.8 0 0 0 2.8 2.8h2.6M15.2 6.5h2.6a2.8 2.8 0 0 1 2.8 2.8v5.4a2.8 2.8 0 0 1-2.8 2.8h-2.6" fill="none" stroke="#FF6A00" stroke-width="2.3" stroke-linecap="round"/><rect x="8.8" y="10.9" width="6.4" height="2.2" rx="1.1" fill="#FF6A00"/>`,
  },
  MongoDB: {
    color: "#00684a",
    mark: "MDB",
    category: "Data & AI Platform",
    svg: `<path d="M12 2.8C8.3 6.6 6.8 10.4 7.2 14.3c.3 2.8 2.2 4.8 4.8 5.7 2.6-.9 4.5-2.9 4.8-5.7.4-3.9-1.1-7.7-4.8-11.5Z" fill="#00ED64" stroke="#00684A" stroke-width="1.2"/><path d="M12 4.2v17" stroke="#00684A" stroke-width="1.5" stroke-linecap="round"/>`,
  },
  ServiceNow: {
    color: "#1f8476",
    mark: "SN",
    category: "Enterprise Software",
    svg: `<circle cx="12" cy="12" r="8" fill="none" stroke="#293E40" stroke-width="2.6"/><path d="M7.2 17.8a8 8 0 0 1 9.6 0" fill="none" stroke="#62D84E" stroke-width="2.8" stroke-linecap="round"/><circle cx="12" cy="11.5" r="2.8" fill="#62D84E"/>`,
  },
  Snowflake: {
    color: "#29b5e8",
    mark: "SNW",
    category: "Data & AI Platform",
    svg: `<g stroke="#29B5E8" stroke-width="2" stroke-linecap="round" fill="none"><path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9"/><path d="M10 5l2 2 2-2M10 19l2-2 2 2"/></g><circle cx="12" cy="12" r="2" fill="#29B5E8"/>`,
  },
  Salesforce: {
    color: "#00a1e0",
    mark: "SF",
    category: "Enterprise Software",
    svg: `<path d="M7.2 17.8a3.8 3.8 0 0 1-.7-7.5 4.6 4.6 0 0 1 8.4-1.8 3.9 3.9 0 0 1 4.7 3.8 3.9 3.9 0 0 1-3.9 5.5H7.2Z" fill="#00A1E0"/><text x="12" y="14.6" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.2" font-weight="800" fill="#ffffff">sf</text>`,
  },
  Accenture: {
    color: "#a100ff",
    mark: "ACN",
    category: "Global Consulting",
    svg: `<path d="M6.5 5.2 17.8 12 6.5 18.8" fill="none" stroke="#A100FF" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  Capgemini: {
    color: "#0070ad",
    mark: "CAP",
    category: "Global Consulting",
    svg: `<path d="M12 3.5c-4.2 3-7 6.8-5.5 11.2 1 2.8 3.8 3.8 5.5 2.2 1.7 1.6 4.5.6 5.5-2.2 1.5-4.4-1.3-8.2-5.5-11.2Z" fill="#0070AD"/><circle cx="12" cy="17.8" r="2.4" fill="#12ABDB"/>`,
  },
  "Huawei Cloud": {
    color: "#cf0a2c",
    mark: "HW",
    category: "China Cloud & AI",
    svg: `<g fill="#CF0A2C"><ellipse cx="12" cy="7.2" rx="1.4" ry="3.8"/><ellipse cx="8.6" cy="8.4" rx="1.4" ry="3.8" transform="rotate(-32 8.6 8.4)"/><ellipse cx="15.4" cy="8.4" rx="1.4" ry="3.8" transform="rotate(32 15.4 8.4)"/><ellipse cx="6.2" cy="11.4" rx="1.3" ry="3.6" transform="rotate(-64 6.2 11.4)"/><ellipse cx="17.8" cy="11.4" rx="1.3" ry="3.6" transform="rotate(64 17.8 11.4)"/></g><path d="M6 16.5h12" stroke="#CF0A2C" stroke-width="2" stroke-linecap="round"/>`,
  },
  "Tencent Cloud": {
    color: "#0052d9",
    mark: "TC",
    category: "China Cloud & AI",
    svg: `<path d="M7.4 17.5a4 4 0 0 1-.8-7.9 5.2 5.2 0 0 1 9.8-1.4 3.8 3.8 0 0 1 1.2 7.4H7.4Z" fill="#0052D9"/><path d="M9.5 14.2 12 10.2l2.5 4h-5Z" fill="#00A4FF"/>`,
  },
  Oracle: {
    color: "#c74634",
    mark: "OR",
    category: "Cloud & Hyperscaler",
    svg: `<rect x="3.2" y="7.2" width="17.6" height="9.6" rx="4.8" fill="none" stroke="#C74634" stroke-width="2.8"/>`,
  },
  Anthropic: {
    color: "#d97757",
    mark: "AN",
    category: "Foundation Models & AI",
    svg: `<path d="M8.8 18.2 12.6 5.8h2.3l3.8 12.4h-2.3l-.8-2.8H11.9l-.8 2.8H8.8Zm3.7-4.8h2.5l-1.25-4.3-1.25 4.3ZM5.3 18.2 9.1 5.8h2.1L7.4 18.2H5.3Z" fill="#D97757"/>`,
  },
  EY: {
    color: "#2e2e38",
    mark: "EY",
    category: "Global Consulting",
    svg: `<polygon points="4,8.2 20,4.2 20,7.4 4,9.8" fill="#FFE600"/><text x="11.8" y="19" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="9.2" font-weight="900" fill="#2E2E38">EY</text>`,
  },
  PwC: {
    color: "#d04a02",
    mark: "PwC",
    category: "Global Consulting",
    svg: `<rect x="11.5" y="4" width="5" height="5" fill="#EB8C00"/><rect x="14.5" y="6.5" width="5.5" height="4.5" fill="#D04A02"/><rect x="9.5" y="6" width="4" height="5" fill="#E0301E"/><text x="11.5" y="18.8" text-anchor="middle" font-family="Georgia, serif" font-size="8.2" font-weight="700" fill="#2D2D2D">pwc</text>`,
  },
  Bain: {
    color: "#cc0000",
    mark: "BAIN",
    category: "Global Consulting",
    svg: `<circle cx="12" cy="12" r="8.2" fill="none" stroke="#CC0000" stroke-width="2.2"/><polygon points="15.8,8.2 13.2,14.8 11.4,12.6 9.2,10.8" fill="#CC0000"/>`,
  },
  Confluent: {
    color: "#0433ff",
    mark: "CF",
    category: "Data & AI Platform",
    svg: `<circle cx="12" cy="12" r="8.2" fill="none" stroke="#0433FF" stroke-width="2"/><path d="M6 12c2-3.5 4.5-3.5 6 0s4 3.5 6 0" fill="none" stroke="#00B4FF" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="12" r="2.1" fill="#0433FF"/>`,
  },
  TCS: {
    color: "#0066b3",
    mark: "TCS",
    category: "Global Consulting",
    svg: `<rect x="2.8" y="5.5" width="18.4" height="13" rx="3" fill="#0066B3"/><circle cx="18.2" cy="8.2" r="1.6" fill="#E40046"/><text x="11.2" y="15" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="8.2" font-weight="800" fill="#ffffff">tcs</text>`,
  },
  LangChain: {
    color: "#1c3c3c",
    mark: "LC",
    category: "Foundation Models & AI",
    svg: `<path d="M9.5 14.5 7.2 16.8a3.2 3.2 0 1 1-4.5-4.5l2.8-2.8a3.2 3.2 0 0 1 4.5 0M14.5 9.5l2.3-2.3a3.2 3.2 0 1 1 4.5 4.5l-2.8 2.8a3.2 3.2 0 0 1-4.5 0" fill="none" stroke="#1C3C3C" stroke-width="2.2" stroke-linecap="round"/><path d="M9.2 14.8 14.8 9.2" stroke="#2F9E8F" stroke-width="2.2" stroke-linecap="round"/>`,
  },
  Mistral: {
    color: "#fa520f",
    mark: "MI",
    category: "Foundation Models & AI",
    svg: `<rect x="4" y="5" width="3.2" height="3.2" fill="#FFD800"/><rect x="16.8" y="5" width="3.2" height="3.2" fill="#FFD800"/><rect x="4" y="8.2" width="6.4" height="3.2" fill="#FFAF00"/><rect x="13.6" y="8.2" width="6.4" height="3.2" fill="#FFAF00"/><rect x="4" y="11.4" width="16" height="3.2" fill="#FF8205"/><rect x="4" y="14.6" width="3.2" height="4.4" fill="#FA520F"/><rect x="10.4" y="14.6" width="3.2" height="3.2" fill="#FA520F"/><rect x="16.8" y="14.6" width="3.2" height="4.4" fill="#FA520F"/>`,
  },
  DXC: {
    color: "#5f249f",
    mark: "DXC",
    category: "Global Consulting",
    svg: `<polygon points="3.5,6.5 11.2,12 3.5,17.5" fill="#5F249F"/><polygon points="20.5,6.5 12.8,12 20.5,17.5" fill="#111827"/>`,
  },
  BCG: {
    color: "#00a859",
    mark: "BCG",
    category: "Global Consulting",
    svg: `<rect x="2.8" y="5.5" width="18.4" height="13" rx="2.5" fill="#008446"/><text x="12" y="14.8" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.8" font-weight="800" letter-spacing="0.4" fill="#ffffff">BCG</text>`,
  },
  Cohere: {
    color: "#39594d",
    mark: "CO",
    category: "Foundation Models & AI",
    svg: `<circle cx="8.2" cy="9.2" r="4.2" fill="#39594D"/><circle cx="15.8" cy="9.2" r="3.2" fill="#D18EE2"/><rect x="5" y="14" width="14" height="5" rx="2.5" fill="#FF7759"/>`,
  },
  Intel: {
    color: "#0068b5",
    mark: "INTC",
    category: "AI Compute & Silicon",
    svg: `<rect x="2.8" y="6" width="18.4" height="12" rx="2.5" fill="#0068B5"/><circle cx="6.2" cy="8.8" r="1" fill="#00C7FD"/><text x="12.5" y="15" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.2" font-weight="800" fill="#ffffff">intel</text>`,
  },
  SLB: {
    color: "#0114dc",
    mark: "SLB",
    category: "Enterprise & Industry",
    svg: `<rect x="2.8" y="5.8" width="18.4" height="12.4" rx="2.5" fill="#0114DC"/><text x="12" y="14.8" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="8" font-weight="800" fill="#ffffff">slb</text>`,
  },
  Cognizant: {
    color: "#0033a0",
    mark: "CTSH",
    category: "Global Consulting",
    svg: `<polygon points="4,12 11.5,5.5 14.5,8.5 9.5,12 14.5,15.5 11.5,18.5" fill="#0033A0"/><polygon points="20,12 13.5,6.5 11,9 15,12 11,15 13.5,17.5" fill="#26EFE9"/>`,
  },
  Atos: {
    color: "#0066a1",
    mark: "ATOS",
    category: "Global Consulting",
    svg: `<rect x="2.5" y="5.8" width="19" height="12.4" rx="2.5" fill="#0066A1"/><text x="12" y="14.6" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.4" font-weight="800" fill="#ffffff">Atos</text>`,
  },
  BytePlus: {
    color: "#325ab4",
    mark: "BP",
    category: "China Cloud & AI",
    svg: `<rect x="4.2" y="7.5" width="2.8" height="9.5" rx="1.2" fill="#325AB4"/><rect x="8.6" y="4.5" width="2.8" height="14.5" rx="1.2" fill="#3C8CFF"/><rect x="13" y="8.5" width="2.8" height="10.5" rx="1.2" fill="#00C8D2"/><rect x="17.4" y="5.5" width="2.8" height="11.5" rx="1.2" fill="#78E6D0"/>`,
  },
  Adobe: {
    color: "#fa0f00",
    mark: "ADB",
    category: "Enterprise Software",
    svg: `<rect x="3" y="3" width="18" height="18" rx="3" fill="#FA0F00"/><path d="M10.2 6h-4v12l4-12Zm3.6 0h4v12l-4-12ZM12 10.6l2.6 7.4h-2.1l-.6-2H10l2-5.4Z" fill="#ffffff"/>`,
  },
  Infosys: {
    color: "#007cc3",
    mark: "INFY",
    category: "Global Consulting",
    svg: `<rect x="2.5" y="5.8" width="19" height="12.4" rx="2.5" fill="#007CC3"/><text x="12" y="14.4" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.2" font-weight="800" fill="#ffffff">Infosys</text>`,
  },
  KPMG: {
    color: "#00338d",
    mark: "KPMG",
    category: "Global Consulting",
    svg: `<g fill="none" stroke="#00338D" stroke-width="1.3"><rect x="3.2" y="5.5" width="3.8" height="5.5" transform="skewX(-12)"/><rect x="7.8" y="5.5" width="3.8" height="5.5" transform="skewX(-12)"/><rect x="12.4" y="5.5" width="3.8" height="5.5" transform="skewX(-12)"/><rect x="17" y="5.5" width="3.8" height="5.5" transform="skewX(-12)"/></g><text x="12" y="18.2" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.8" font-weight="900" fill="#00338D">KPMG</text>`,
  },
  SAP: {
    color: "#0070f2",
    mark: "SAP",
    category: "Enterprise Software",
    svg: `<polygon points="2.5,6 21.5,6 15.5,18 2.5,18" fill="#008FD3"/><text x="10.2" y="14.5" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.8" font-weight="900" fill="#ffffff">SAP</text>`,
  },
  Wipro: {
    color: "#341f65",
    mark: "WIP",
    category: "Global Consulting",
    svg: `<circle cx="12" cy="12" r="8" fill="none" stroke="#E31837" stroke-width="1.6" stroke-dasharray="2.2 2.2"/><circle cx="12" cy="12" r="5.5" fill="none" stroke="#00A88F" stroke-width="1.6" stroke-dasharray="2 2"/><text x="12" y="14.2" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="5.6" font-weight="800" fill="#341F65">wipro</text>`,
  },
  Deloitte: {
    color: "#86bc25",
    mark: "DEL",
    category: "Global Consulting",
    svg: `<text x="9.5" y="16.8" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="13.5" font-weight="900" fill="#111827">D</text><circle cx="17.2" cy="15.2" r="2.4" fill="#86BC25"/>`,
  },
  Eviden: {
    color: "#ff5500",
    mark: "EVI",
    category: "Global Consulting",
    svg: `<rect x="3" y="5.5" width="18" height="13" rx="2.5" fill="#002D3C"/><path d="M6.5 9.5h6M6.5 12h4.5M6.5 14.5h6" stroke="#FF5500" stroke-width="2" stroke-linecap="round"/><circle cx="16.5" cy="12" r="2.2" fill="#FF5500"/>`,
  },
  "Deutsche Telekom": {
    color: "#e20074",
    mark: "DT",
    category: "Enterprise & Industry",
    svg: `<rect x="3" y="3" width="18" height="18" rx="3" fill="#E20074"/><path d="M7.5 7h9v2.5h-1.4V8.4h-2.1v7.2h1.6V17H9.4v-1.4H11V8.4H8.9v1.1H7.5V7Z" fill="#ffffff"/><rect x="7.5" y="11.5" width="1.8" height="1.8" fill="#ffffff"/><rect x="14.7" y="11.5" width="1.8" height="1.8" fill="#ffffff"/>`,
  },
  Mastercard: {
    color: "#eb001b",
    mark: "MA",
    category: "Enterprise & Industry",
    svg: `<circle cx="9.2" cy="12" r="5.6" fill="#EB001B"/><circle cx="14.8" cy="12" r="5.6" fill="#F79E1B" fill-opacity="0.88"/>`,
  },
  Medtronic: {
    color: "#0085ca",
    mark: "MDT",
    category: "Enterprise & Industry",
    svg: `<rect x="3" y="5.5" width="18" height="13" rx="2.5" fill="#001E46"/><text x="12" y="14.6" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.8" font-weight="800" fill="#0085CA">MDT</text>`,
  },
  Halliburton: {
    color: "#cc0000",
    mark: "HAL",
    category: "Enterprise & Industry",
    svg: `<rect x="3" y="5.5" width="18" height="13" rx="2.5" fill="#CC0000"/><text x="12" y="14.8" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.2" font-weight="800" fill="#ffffff">HAL</text>`,
  },
  "Rockwell Automation": {
    color: "#cd163f",
    mark: "ROK",
    category: "Enterprise & Industry",
    svg: `<polygon points="7,4 17,4 20,12 17,20 7,20 4,12" fill="#CD163F"/><text x="12" y="14.5" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="6.8" font-weight="800" fill="#ffffff">RA</text>`,
  },
  Sprinklr: {
    color: "#0875e1",
    mark: "CXM",
    category: "Enterprise Software",
    svg: `<g stroke-width="2.2" stroke-linecap="round"><path d="M12 4.5v5" stroke="#0875E1"/><path d="M12 14.5v5" stroke="#7ED321"/><path d="M5.5 8.2l4.3 2.5" stroke="#F5A623"/><path d="M14.2 13.3l4.3 2.5" stroke="#D0021B"/><path d="M18.5 8.2l-4.3 2.5" stroke="#9B51E0"/><path d="M9.8 13.3l-4.3 2.5" stroke="#00B8D9"/></g>`,
  },
  "Telefónica": {
    color: "#0066ff",
    mark: "TEF",
    category: "Enterprise & Industry",
    svg: `<g fill="#0066FF"><circle cx="7" cy="7.2" r="2.1"/><circle cx="12" cy="7.2" r="2.1"/><circle cx="17" cy="7.2" r="2.1"/><circle cx="12" cy="12.2" r="2.1"/><circle cx="12" cy="17.2" r="2.1"/></g>`,
  },
  Windward: {
    color: "#0284c7",
    mark: "WNW",
    category: "Enterprise Software",
    svg: `<path d="M4.5 8.5 8.2 16l3.8-6 3.8 6 3.7-7.5" fill="none" stroke="#0284C7" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
  "7AI": {
    color: "#6366f1",
    mark: "7AI",
    category: "Enterprise Software",
    svg: `<rect x="3" y="4" width="18" height="16" rx="3.5" fill="#4F46E5"/><text x="12" y="14.8" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="7.6" font-weight="800" fill="#ffffff">7AI</text>`,
  },
  "In-house": {
    color: "#0f766e",
    mark: "IN",
    category: "Internal Engineering",
    svg: `<rect x="3.5" y="4.5" width="17" height="15" rx="3" fill="#0F766E"/><path d="M9.2 9.5 6.5 12l2.7 2.5M14.8 9.5l2.7 2.5-2.7 2.5M12.8 8.8l-1.6 6.4" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  },
};

function escapeXml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] ?? ch);
}

export function vendorStyle(vendor: string): VendorIdentity {
  const known = VENDOR_STYLES[vendor];
  if (known) return known;
  const initials = vendor
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 3)
    .toUpperCase() || "?";
  const safe = escapeXml(initials);
  return {
    color: "#475569",
    mark: initials,
    category: "Enterprise & Industry",
    svg: `<rect x="2.5" y="4.5" width="19" height="15" rx="3" fill="#475569"/><text x="12" y="14.6" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="${safe.length > 2 ? "6.6" : "7.8"}" font-weight="800" fill="#ffffff">${safe}</text>`,
  };
}

export function vendorLogoSvg(vendor: string, fallbackMark?: string): string {
  const info = vendorStyle(vendor);
  if (VENDOR_STYLES[vendor]) {
    return `<svg class="vendor-logo-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${info.svg}</svg>`;
  }
  const label = escapeXml((fallbackMark || info.mark || "?").slice(0, 3).toUpperCase());
  return `<svg class="vendor-logo-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="2.5" y="4.5" width="19" height="15" rx="3" fill="${info.color}"/><text x="12" y="14.6" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="${label.length > 2 ? "6.6" : "7.8"}" font-weight="800" fill="#ffffff">${label}</text></svg>`;
}

