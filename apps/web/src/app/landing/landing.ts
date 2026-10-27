import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProjectApi, Project, errorMessage } from '../projects/project-api';
import { workloads, resourceCatalog, ResourcePlan } from '../projects/resources';

@Component({
  imports: [RouterLink, DatePipe],
  templateUrl: './landing.html',
  styleUrl: './landing.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Landing {
  private readonly api = inject(ProjectApi);
  readonly projects = signal<Project[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly workloads = workloads;
  readonly catalog = resourceCatalog;
  readonly workloadKeys = Object.keys(workloads) as ResourcePlan['workload'][];
  readonly selectedWorkload = signal<ResourcePlan['workload']>('cpu');
  readonly selectedLayer = signal(0);
  readonly paperPage = signal(1);
  readonly layers = [
    {
      name: 'The interface',
      technology: 'Angular / TypeScript',
      title: 'A brief you can keep changing.',
      description:
        'Typed forms collect the paper, target, working mode and resources. The browser sends your expected revision with an edit so the API can detect conflicts.',
      artifact: 'apps/web/src/app/projects/project-api.ts',
      code: 'this.http.post<Project>(`/api/projects/${id}/revisions`, {\n  expected_revision, setup, note\n})',
      link: 'apps/web/src/app/projects/project-api.ts',
    },
    {
      name: 'The decision boundary',
      technology: 'Python / FastAPI',
      title: 'Two edits. Only one advances the revision.',
      description:
        'An atomic update checks the current revision before accepting a change. A stale editor receives a conflict instead of silently overwriting someone else’s work.',
      artifact: 'services/api/paperlab_api/main.py',
      code: 'update(Project)\n.where(Project.id == str(project_id),\n       Project.revision == request.expected_revision)\n.values(revision=next_revision, updated_at=now)',
      link: 'services/api/paperlab_api/main.py',
    },
    {
      name: 'The record',
      technology: 'SQLAlchemy / SQLite locally',
      title: 'The previous setup remains part of the story.',
      description:
        'Each accepted change stores a new setup snapshot and the reason for the revision. Existing revisions remain available after a restart.',
      artifact: 'services/api/paperlab_api/models.py',
      code: 'class ContractRevision(Base):\n    __tablename__ = "contract_revisions"\n\n    setup: Mapped[dict] = mapped_column(JSON, nullable=False)\n    note: Mapped[str] = mapped_column(Text, nullable=False)',
      link: 'services/api/paperlab_api/models.py',
    },
  ];
  constructor() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    this.error.set('');
    try {
      this.projects.set((await this.api.list()).slice(0, 3));
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
}
