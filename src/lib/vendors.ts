// Official vendor brand logos (fetched from official vendor websites / brand kits in public/logos/vendors/)
import { href } from "./paths";

export interface VendorIdentity {
  color: string;
  mark: string;
  category: string;
  domain: string;
  logo: string;
}

const VENDOR_STYLES: Record<string, VendorIdentity> = {
  Microsoft: {
    color: "#0078d4",
    mark: "MS",
    category: "Cloud & Hyperscaler",
    domain: "microsoft.com",
    logo: "microsoft.svg",
  },
  "Google Cloud": {
    color: "#4285f4",
    mark: "GC",
    category: "Cloud & Hyperscaler",
    domain: "cloud.google.com",
    logo: "google-cloud.svg",
  },
  AWS: {
    color: "#ff9900",
    mark: "AWS",
    category: "Cloud & Hyperscaler",
    domain: "aws.amazon.com",
    logo: "aws.svg",
  },
  IBM: {
    color: "#0f62fe",
    mark: "IBM",
    category: "Enterprise & Cloud",
    domain: "ibm.com",
    logo: "ibm.svg",
  },
  OpenAI: {
    color: "#10a37f",
    mark: "OA",
    category: "Foundation Models & AI",
    domain: "openai.com",
    logo: "openai.svg",
  },
  Databricks: {
    color: "#ff3621",
    mark: "DB",
    category: "Data & AI Platform",
    domain: "databricks.com",
    logo: "databricks.svg",
  },
  NVIDIA: {
    color: "#76b900",
    mark: "NV",
    category: "AI Compute & Silicon",
    domain: "nvidia.com",
    logo: "nvidia.svg",
  },
  "Baidu AI Cloud": {
    color: "#2932e1",
    mark: "BD",
    category: "China Cloud & AI",
    domain: "cloud.baidu.com",
    logo: "baidu-ai-cloud.svg",
  },
  "Alibaba Cloud": {
    color: "#ff6a00",
    mark: "AC",
    category: "China Cloud & AI",
    domain: "alibabacloud.com",
    logo: "alibaba-cloud.svg",
  },
  MongoDB: {
    color: "#00684a",
    mark: "MDB",
    category: "Data & AI Platform",
    domain: "mongodb.com",
    logo: "mongodb.svg",
  },
  ServiceNow: {
    color: "#1f8476",
    mark: "SN",
    category: "Enterprise Software",
    domain: "servicenow.com",
    logo: "servicenow.png",
  },
  Snowflake: {
    color: "#29b5e8",
    mark: "SNW",
    category: "Data & AI Platform",
    domain: "snowflake.com",
    logo: "snowflake.svg",
  },
  Salesforce: {
    color: "#00a1e0",
    mark: "SF",
    category: "Enterprise Software",
    domain: "salesforce.com",
    logo: "salesforce.svg",
  },
  Accenture: {
    color: "#a100ff",
    mark: "ACN",
    category: "Global Consulting",
    domain: "accenture.com",
    logo: "accenture.svg",
  },
  Capgemini: {
    color: "#0070ad",
    mark: "CAP",
    category: "Global Consulting",
    domain: "capgemini.com",
    logo: "capgemini.svg",
  },
  "Huawei Cloud": {
    color: "#cf0a2c",
    mark: "HW",
    category: "China Cloud & AI",
    domain: "huaweicloud.com",
    logo: "huawei-cloud.svg",
  },
  "Tencent Cloud": {
    color: "#0052d9",
    mark: "TC",
    category: "China Cloud & AI",
    domain: "tencentcloud.com",
    logo: "tencent-cloud.png",
  },
  Oracle: {
    color: "#c74634",
    mark: "OR",
    category: "Cloud & Hyperscaler",
    domain: "oracle.com",
    logo: "oracle.png",
  },
  Anthropic: {
    color: "#d97757",
    mark: "AN",
    category: "Foundation Models & AI",
    domain: "anthropic.com",
    logo: "anthropic.svg",
  },
  EY: {
    color: "#2e2e38",
    mark: "EY",
    category: "Global Consulting",
    domain: "ey.com",
    logo: "ey.jpg",
  },
  PwC: {
    color: "#d04a02",
    mark: "PwC",
    category: "Global Consulting",
    domain: "pwc.com",
    logo: "pwc.png",
  },
  Bain: {
    color: "#cc0000",
    mark: "BAIN",
    category: "Global Consulting",
    domain: "bain.com",
    logo: "bain.svg",
  },
  Confluent: {
    color: "#0433ff",
    mark: "CF",
    category: "Data & AI Platform",
    domain: "confluent.io",
    logo: "confluent.png",
  },
  TCS: {
    color: "#0066b3",
    mark: "TCS",
    category: "Global Consulting",
    domain: "tcs.com",
    logo: "tcs.svg",
  },
  LangChain: {
    color: "#1c3c3c",
    mark: "LC",
    category: "Foundation Models & AI",
    domain: "langchain.com",
    logo: "langchain.svg",
  },
  Mistral: {
    color: "#fa520f",
    mark: "MI",
    category: "Foundation Models & AI",
    domain: "mistral.ai",
    logo: "mistral.svg",
  },
  DXC: {
    color: "#5f249f",
    mark: "DXC",
    category: "Global Consulting",
    domain: "dxc.com",
    logo: "dxc.png",
  },
  BCG: {
    color: "#00a859",
    mark: "BCG",
    category: "Global Consulting",
    domain: "bcg.com",
    logo: "bcg.png",
  },
  Cohere: {
    color: "#39594d",
    mark: "CO",
    category: "Foundation Models & AI",
    domain: "cohere.com",
    logo: "cohere.png",
  },
  Intel: {
    color: "#0068b5",
    mark: "INTC",
    category: "AI Compute & Silicon",
    domain: "intel.com",
    logo: "intel.svg",
  },
  SLB: {
    color: "#0114dc",
    mark: "SLB",
    category: "Enterprise & Industry",
    domain: "slb.com",
    logo: "slb.svg",
  },
  Cognizant: {
    color: "#0033a0",
    mark: "CTSH",
    category: "Global Consulting",
    domain: "cognizant.com",
    logo: "cognizant.svg",
  },
  Atos: {
    color: "#0066a1",
    mark: "ATOS",
    category: "Global Consulting",
    domain: "atos.net",
    logo: "atos.svg",
  },
  BytePlus: {
    color: "#325ab4",
    mark: "BP",
    category: "China Cloud & AI",
    domain: "byteplus.com",
    logo: "byteplus.svg",
  },
  Adobe: {
    color: "#fa0f00",
    mark: "ADB",
    category: "Enterprise Software",
    domain: "adobe.com",
    logo: "adobe.svg",
  },
  Infosys: {
    color: "#007cc3",
    mark: "INFY",
    category: "Global Consulting",
    domain: "infosys.com",
    logo: "infosys.svg",
  },
  KPMG: {
    color: "#00338d",
    mark: "KPMG",
    category: "Global Consulting",
    domain: "kpmg.com",
    logo: "kpmg.png",
  },
  SAP: {
    color: "#0070f2",
    mark: "SAP",
    category: "Enterprise Software",
    domain: "sap.com",
    logo: "sap.svg",
  },
  Wipro: {
    color: "#341f65",
    mark: "WIP",
    category: "Global Consulting",
    domain: "wipro.com",
    logo: "wipro.svg",
  },
  Deloitte: {
    color: "#86bc25",
    mark: "DEL",
    category: "Global Consulting",
    domain: "deloitte.com",
    logo: "deloitte.svg",
  },
  Eviden: {
    color: "#ff5500",
    mark: "EVI",
    category: "Global Consulting",
    domain: "eviden.com",
    logo: "eviden.svg",
  },
  "Deutsche Telekom": {
    color: "#e20074",
    mark: "DT",
    category: "Enterprise & Industry",
    domain: "telekom.com",
    logo: "deutsche-telekom.svg",
  },
  Mastercard: {
    color: "#eb001b",
    mark: "MA",
    category: "Enterprise & Industry",
    domain: "mastercard.com",
    logo: "mastercard.svg",
  },
  Medtronic: {
    color: "#0085ca",
    mark: "MDT",
    category: "Enterprise & Industry",
    domain: "medtronic.com",
    logo: "medtronic.png",
  },
  Halliburton: {
    color: "#cc0000",
    mark: "HAL",
    category: "Enterprise & Industry",
    domain: "halliburton.com",
    logo: "halliburton.png",
  },
  "Rockwell Automation": {
    color: "#cd163f",
    mark: "ROK",
    category: "Enterprise & Industry",
    domain: "rockwellautomation.com",
    logo: "rockwell-automation.svg",
  },
  Sprinklr: {
    color: "#0875e1",
    mark: "CXM",
    category: "Enterprise Software",
    domain: "sprinklr.com",
    logo: "sprinklr.png",
  },
  "Telefónica": {
    color: "#0066ff",
    mark: "TEF",
    category: "Enterprise & Industry",
    domain: "telefonica.com",
    logo: "telefonica.svg",
  },
  Windward: {
    color: "#0284c7",
    mark: "WNW",
    category: "Enterprise Software",
    domain: "windward.ai",
    logo: "windward.png",
  },
  "Wolters Kluwer": {
    color: "#007ac3",
    mark: "WK",
    category: "Enterprise Software",
    domain: "wolterskluwer.com",
    logo: "wolters-kluwer.png",
  },
  "7AI": {
    color: "#6366f1",
    mark: "7AI",
    category: "Enterprise Software",
    domain: "7ai.com",
    logo: "7ai.png",
  },
  "In-house": {
    color: "#0f766e",
    mark: "IN",
    category: "Internal Engineering",
    domain: "internal",
    logo: "in-house.svg",
  },
};

function slugifyVendor(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function escapeAttr(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] ?? ch);
}

export function vendorStyle(vendor: string): VendorIdentity {
  const known = VENDOR_STYLES[vendor];
  if (known) return known;
  const initials =
    vendor
      .split(/\s+/)
      .map((part) => part[0] ?? "")
      .join("")
      .slice(0, 3)
      .toUpperCase() || "?";
  const slug = slugifyVendor(vendor) || "unknown";
  return {
    color: "#475569",
    mark: initials,
    category: "Enterprise & Industry",
    domain: `${slug}.com`,
    logo: `${slug}.png`,
  };
}

export function vendorLogoSvg(vendor: string, _fallbackMark?: string): string {
  const info = vendorStyle(vendor);
  const src = escapeAttr(href(`/logos/vendors/${info.logo}`));
  return `<img class="vendor-logo-svg vendor-logo-img" src="${src}" alt="" loading="lazy" decoding="async" />`;
}

