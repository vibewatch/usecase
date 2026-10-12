// Vendor identity marks. Colors are used only for small badges that always sit
// beside the vendor name — never as chart encoding.
const VENDOR_STYLES: Record<string, { color: string; mark: string }> = {
  AWS: { color: "#ff9900", mark: "AWS" },
  Microsoft: { color: "#0078d4", mark: "MS" },
  "Google Cloud": { color: "#4285f4", mark: "GC" },
  Oracle: { color: "#c74634", mark: "OR" },
  "Alibaba Cloud": { color: "#ff6a00", mark: "AC" },
  Snowflake: { color: "#29b5e8", mark: "SNW" },
  Databricks: { color: "#ff3621", mark: "DB" },
  IBM: { color: "#0f62fe", mark: "IBM" },
  Salesforce: { color: "#00a1e0", mark: "SF" },
  NVIDIA: { color: "#76b900", mark: "NV" },
  LangChain: { color: "#1c3c3c", mark: "LC" },
  OpenAI: { color: "#10a37f", mark: "OA" },
  Anthropic: { color: "#d97757", mark: "AN" },
  ServiceNow: { color: "#1f8476", mark: "SN" },
  MongoDB: { color: "#00684a", mark: "MDB" },
  Confluent: { color: "#0a3d62", mark: "CF" },
  SAP: { color: "#0070f2", mark: "SAP" },
  Mistral: { color: "#fa520f", mark: "MI" },
  Cohere: { color: "#39594d", mark: "CO" },
  "Tencent Cloud": { color: "#0052d9", mark: "TC" },
  "Baidu AI Cloud": { color: "#2932e1", mark: "BD" },
  "Huawei Cloud": { color: "#c7000b", mark: "HW" },
  BytePlus: { color: "#325ab4", mark: "BP" },
  "In-house": { color: "#475569", mark: "IN" },
};

export function vendorStyle(vendor: string): { color: string; mark: string } {
  const known = VENDOR_STYLES[vendor];
  if (known) return known;
  const initials = vendor
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 3)
    .toUpperCase();
  return { color: "#64748b", mark: initials || "?" };
}
