export interface SolvedTask {
  id: string;
  title: string;
  solvedAt: string;
  olympiads: string[];
  tags: string[];
}
const solvedKey = "maxolimp-solved-v2";
const oldKey = "maxolimp-solved";
const favoritesKey = "olympiad-favorites-local-v1";
const criteriaKey = "onboarding-live-v1";

function read<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "") as T;
  } catch {
    return fallback;
  }
}
export function solvedTasks(): SolvedTask[] {
  const data = read<unknown>(solvedKey, []);
  return Array.isArray(data)
    ? data.filter(
        (x): x is SolvedTask =>
          typeof x?.id === "string" &&
          typeof x?.solvedAt === "string" &&
          typeof x?.title === "string",
      )
    : [];
}
export function legacySolved(): string[] {
  const data = read<unknown>(oldKey, []);
  return Array.isArray(data)
    ? [...new Set(data.filter((x): x is string => typeof x === "string"))]
    : [];
}
export function markSolved(task: {
  id: string;
  title: string;
  olympiads: { name: string }[];
  topics: { name: string }[];
}): void {
  const current = solvedTasks();
  if (current.some((item) => item.id === task.id)) return;
  current.push({
    id: task.id,
    title: task.title,
    solvedAt: new Date().toISOString(),
    olympiads: task.olympiads.map((x) => x.name),
    tags: task.topics.map((x) => x.name),
  });
  localStorage.setItem(solvedKey, JSON.stringify(current));
  window.dispatchEvent(new Event("maxolimp:solved"));
}
export interface Criteria {
  university: number | null;
  program: number | null;
}
export function getCriteria(): Criteria {
  const raw = read<Record<string, unknown>>(criteriaKey, {});
  return {
    university: Number(raw.university) || null,
    program: Number(raw.direction) || null,
  };
}
export function saveCriteria(value: Criteria): void {
  localStorage.setItem(
    criteriaKey,
    JSON.stringify({
      university: value.university || "",
      direction: value.program || "",
      step: value.program ? 2 : value.university ? 1 : 0,
    }),
  );
}
export function favorites(): number[] {
  const data = read<unknown>(favoritesKey, []);
  return Array.isArray(data)
    ? data.filter((x): x is number => typeof x === "number")
    : [];
}
export function toggleFavorite(id: number): number[] {
  const current = new Set(favorites());
  if (current.has(id)) current.delete(id);
  else current.add(id);
  const next = [...current];
  localStorage.setItem(favoritesKey, JSON.stringify(next));
  return next;
}
