import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { errorMessage, Project, ProjectApi } from './project-api';

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
