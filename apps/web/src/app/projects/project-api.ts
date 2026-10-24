import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom, timeout } from 'rxjs';

export interface ProjectSetup {
  name: string;
  paper_url: string;
  target_result: string;
  dataset: string;
  metric: string;
  reproduction_mode: 'run' | 'retrain' | 'reimplement';
  control_mode: 'guided' | 'autonomous';
  learning_mode: boolean;
  max_gpu_hours: number;
  max_llm_cost_usd: number;
  hardware: string;
}

export interface Project {
  id: string;
  revision: number;
  status: 'draft';
  setup: ProjectSetup;
  created_at: string;
  updated_at: string;
}

export interface Revision {
  revision: number;
  setup: ProjectSetup;
  note: string;
  created_at: string;
}

export const fieldLabels: Record<keyof ProjectSetup, string> = {
  name: 'Project name',
  paper_url: 'Paper URL',
  target_result: 'Target result',
  dataset: 'Dataset',
  metric: 'Evaluation metric',
  reproduction_mode: 'Reproduction approach',
  control_mode: 'Operating mode',
  learning_mode: 'Learning support',
  max_gpu_hours: 'GPU-hour limit',
  max_llm_cost_usd: 'Model budget (USD)',
  hardware: 'Available hardware',
};

export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0 || error.status >= 500) {
      return 'The API is unavailable. Check that the local backend is running, then try again.';
    }
    if (error.status === 404) return 'This project could not be found.';
    if (error.status === 409)
      return 'A newer revision was saved. Reload the latest setup before making your changes again.';
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail))
      return detail
        .map((item: { loc: string[]; msg: string }) => {
          const key = item.loc[item.loc.length - 1] as keyof ProjectSetup;
          return `${fieldLabels[key] ?? key}: ${item.msg}`;
        })
        .join(' ');
  }
  return 'The request did not finish. Reload the project to check whether it was saved before retrying.';
}

@Injectable({ providedIn: 'root' })
export class ProjectApi {
  private readonly http = inject(HttpClient);
  list(offset = 0) {
    return firstValueFrom(
      this.http.get<Project[]>(`/api/projects?offset=${offset}`).pipe(timeout(15000)),
    );
  }
  get(id: string) {
    return firstValueFrom(this.http.get<Project>(`/api/projects/${id}`).pipe(timeout(15000)));
  }
  history(id: string) {
    return firstValueFrom(
      this.http.get<Revision[]>(`/api/projects/${id}/revisions`).pipe(timeout(15000)),
    );
  }
  create(setup: ProjectSetup) {
    return firstValueFrom(this.http.post<Project>('/api/projects', setup).pipe(timeout(15000)));
  }
  revise(id: string, expected_revision: number, setup: ProjectSetup, note: string) {
    return firstValueFrom(
      this.http
        .post<Project>(`/api/projects/${id}/revisions`, { expected_revision, setup, note })
        .pipe(timeout(15000)),
    );
  }
}
