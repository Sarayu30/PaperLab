import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';

export type Stage =
  'analysis' | 'plan' | 'implementation' | 'review' | 'results' | 'extensions' | 'report' | 'chat';
export interface Artifact {
  title: string;
  summary: string;
  sections: { heading: string; body: string }[];
  citations: { page: number; quote: string }[];
  tasks: {
    id: string;
    title: string;
    description: string;
    depends_on: string[];
    acceptance: string;
  }[];
  files: { path: string; content: string }[];
  warnings: string[];
}
export interface Run {
  id: string;
  stage: Stage;
  status: string;
  workspace_version: number;
  project_revision: number;
  output: Partial<Artifact>;
  error: string;
  message: string;
  feedback: string;
  usage: { model?: string; total_tokens?: number; estimated_usd?: number; reserved_usd?: number };
  created_at: string;
  finished_at: string | null;
}
export interface Workspace {
  version: number;
  project_revision: number;
  active_run: string | null;
  approved_plan: string | null;
  source: {
    id: string;
    name: string;
    digest: string;
    pages: { page: number; text: string }[];
  } | null;
  artifacts: Partial<Record<Stage, Run>>;
  feedback: string;
  evidence: {
    metrics?: Record<string, number>;
    hardware?: string;
    command?: string;
    notes?: string;
    provenance?: string;
  };
  runs: Run[];
  total_tokens: number;
  cost_note: string;
}
export interface ProviderStatus {
  configured: boolean;
  model: string;
  provider: string;
}

export function researchError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (typeof error.error?.detail === 'string') return error.error.detail;
    if (Array.isArray(error.error?.detail))
      return error.error.detail.map((e: { msg: string }) => e.msg).join(' ');
    if (error.status === 0) return 'The backend is unavailable. Check that FastAPI is running.';
  }
  return 'The request did not finish. Refresh the workspace to check its saved state before retrying.';
}

@Injectable({ providedIn: 'root' })
export class ResearchApi {
  private readonly http = inject(HttpClient);
  private base(id: string) {
    return `/api/projects/${id}/research`;
  }
  status() {
    return firstValueFrom(this.http.get<ProviderStatus>('/api/ai/status').pipe(timeout(15000)));
  }
  get(id: string) {
    return firstValueFrom(this.http.get<Workspace>(this.base(id)).pipe(timeout(15000)));
  }
  post(id: string, path: string, body: unknown) {
    return firstValueFrom(
      this.http.post<Workspace>(`${this.base(id)}/${path}`, body).pipe(timeout(60000)),
    );
  }
  run(id: string, version: number, stage: Stage, message = '') {
    return firstValueFrom(
      this.http
        .post<Run>(`${this.base(id)}/runs`, {
          expected_version: version,
          stage,
          message,
          request_id: crypto.randomUUID(),
        })
        .pipe(timeout(15000)),
    );
  }
  upload(id: string, version: number, file: File) {
    const body = new FormData();
    body.append('file', file);
    return firstValueFrom(
      this.http
        .post<Workspace>(`${this.base(id)}/source/pdf?expected_version=${version}`, body)
        .pipe(timeout(60000)),
    );
  }
}
