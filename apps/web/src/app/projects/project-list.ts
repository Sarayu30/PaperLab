import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { errorMessage, Project, ProjectApi } from './project-api';
import { workloads, environments } from './resources';

@Component({
  imports: [RouterLink, DatePipe],
  templateUrl: './project-list.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectList {
  private readonly api = inject(ProjectApi);
  readonly projects = signal<Project[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly hasMore = signal(false);
  readonly query = signal('');
  readonly workloads = workloads;
  readonly environments = environments;
  readonly filtered = computed(() => {
    const term = this.query().trim().toLowerCase();
    return this.projects().filter((p) =>
      [p.setup.name, p.setup.dataset, p.setup.target_result, p.setup.metric]
        .join(' ')
        .toLowerCase()
        .includes(term),
    );
  });
  readonly latest = computed(
    () => [...this.projects()].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0],
  );
  search(event: Event) {
    this.query.set((event.target as HTMLInputElement).value);
  }
  paperReference(url: string) {
    try {
      const paper = new URL(url);
      return (
        paper.hostname +
        (paper.hostname === 'arxiv.org' ? paper.pathname.replace('/abs/', ' / ') : '')
      );
    } catch {
      return 'Paper reference';
    }
  }

  constructor() {
    void this.load();
  }

  async load(more = false) {
    this.loading.set(true);
    this.error.set('');
    try {
      const items = await this.api.list(more ? this.projects().length : 0);
      this.projects.update((previous) => (more ? [...previous, ...items] : items));
      this.hasMore.set(items.length === 100);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
}
