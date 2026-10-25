import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { errorMessage, fieldLabels, Project, ProjectApi, Revision } from './project-api';
import { resourceSummary, resourceValue, ResourcePlan, workloads, environments } from './resources';

@Component({
  imports: [RouterLink, DatePipe],
  templateUrl: './project-detail.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectDetail {
  private readonly api = inject(ProjectApi);
  private readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly project = signal<Project | null>(null);
  readonly history = signal<Revision[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly labels = fieldLabels;
  readonly keys = Object.keys(fieldLabels) as (keyof typeof fieldLabels)[];
  readonly resourceValue = resourceValue;
  readonly workloads = workloads;
  readonly environments = environments;

  constructor() {
    void this.load();
  }

  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      const [project, history] = await Promise.all([
        this.api.get(this.id),
        this.api.history(this.id),
      ]);
      this.project.set(project);
      this.history.set(history);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  changes(index: number): string[] {
    const current = this.history()[index],
      previous = this.history()[index + 1];
    if (!previous) return [];
    return this.keys
      .filter((key) => JSON.stringify(current.setup[key]) !== JSON.stringify(previous.setup[key]))
      .map((key) => fieldLabels[key]);
  }

  format(value: string | number | boolean | ResourcePlan): string {
    if (typeof value === 'object') return resourceSummary(value);
    if (typeof value === 'boolean') return value ? 'On' : 'Off';
    if (value === 'autonomous') return 'Autonomous within limits';
    if (value === 'reimplement') return 'Reimplement from the paper';
    if (value === 'retrain') return 'Retrain released code';
    if (value === 'run') return 'Run released code and weights';
    if (value === 'guided') return 'Guided';
    return String(value);
  }
}
