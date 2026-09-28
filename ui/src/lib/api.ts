export interface Page<T> {
  total: number;
  page: number;
  size: number;
  items: T[];
}
export interface University {
  id: number;
  name: string;
  cities: string[];
}
export interface Program {
  id: number;
  name: string;
  code: string;
}
export interface Subject {
  id: number;
  name: string;
}
export interface Recommendation {
  id: number;
  name: string;
  subject: Subject;
  complexity: number;
  benefit: { type: string };
}
export interface Olympiad {
  id: number;
  name: string;
  complexity: number;
  description: string;
  host_university: { id: number; name: string };
  subjects: Subject[];
}
export interface Stage {
  id: number;
  name: string;
  is_online: boolean;
  location: string | null;
  start_date: string;
  end_date: string | null;
}
export interface TaskListItem {
  id: string;
  title: string;
  snippet: string | null;
  difficulty: number | null;
  olympiad: string | null;
  olympiad_short_name: string | null;
  number: string | null;
}
export interface TaskDetail {
  id: string;
  title: string;
  statement: string;
  answer: string | null;
  difficulty: number | null;
  subject: string | null;
  grade: number | null;
  topics: { id: string; name: string }[];
  olympiads: { id: string; name: string; short_name: string | null }[];
  source: {
    url: string | null;
    year: number | null;
    stage: string | null;
    number: string | null;
  };
  has_solution: boolean;
  hints_count: number;
}
export interface Solution {
  id: string;
  content: string;
  is_generated: boolean;
  is_verified: boolean;
}

export class ApiError extends Error {
  constructor(public status: number) {
    super(`HTTP ${status}`);
  }
}
async function request<T>(
  base: string,
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${base}${path}`, { signal });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}
export const olympiadApi = {
  universities: (query = "", signal?: AbortSignal) =>
    request<Page<University>>(
      "/api/olympiads",
      `/universities?${new URLSearchParams({ q: query, size: "100" })}`,
      signal,
    ),
  programs: (id: number, query = "", signal?: AbortSignal) =>
    request<Page<Program>>(
      "/api/olympiads",
      `/universities/${id}/programs?${new URLSearchParams({ q: query, size: "100" })}`,
      signal,
    ),
  recommendations: (params: URLSearchParams, signal?: AbortSignal) =>
    request<Page<Recommendation>>(
      "/api/olympiads",
      `/olympiads/recommendations?${params}`,
      signal,
    ),
  detail: (id: number, signal?: AbortSignal) =>
    request<Olympiad>("/api/olympiads", `/olympiads/${id}`, signal),
  stages: (id: number, signal?: AbortSignal) =>
    request<{ items: Stage[] }>(
      "/api/olympiads",
      `/olympiads/${id}/stages`,
      signal,
    ),
};
export const taskApi = {
  list: (params: URLSearchParams, signal?: AbortSignal) =>
    request<Page<TaskListItem>>("/api/tasks", `/tasks?${params}`, signal),
  olympiads: (signal?: AbortSignal) =>
    request<{
      items: { id: string; name: string; short_name: string | null }[];
    }>("/api/tasks", "/olympiads", signal),
  detail: (id: string, signal?: AbortSignal) =>
    request<TaskDetail>(
      "/api/tasks",
      `/tasks/${encodeURIComponent(id)}`,
      signal,
    ),
  solutions: (id: string, signal?: AbortSignal) =>
    request<{ items: Solution[] }>(
      "/api/tasks",
      `/tasks/${encodeURIComponent(id)}/solutions`,
      signal,
    ),
};
