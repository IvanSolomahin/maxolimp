declare global {
  interface Window {
    WebApp?: { initData?: string };
  }
}
export interface MaxUser {
  valid: boolean;
  max_id: number;
  user: Record<string, unknown>;
}
export async function validateMax(): Promise<MaxUser | null> {
  const initData = window.WebApp?.initData;
  if (!initData) return null;
  try {
    const response = await fetch("/api/max/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData }),
    });
    if (!response.ok) return null;
    const result = (await response.json()) as MaxUser;
    return result.valid ? result : null;
  } catch {
    return null;
  }
}
