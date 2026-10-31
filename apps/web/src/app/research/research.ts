import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnDestroy,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Project, ProjectApi } from '../projects/project-api';
import { ProviderStatus, ResearchApi, researchError, Stage, Workspace } from './research-api';

@Component({
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe],
  templateUrl: './research.html',
  styleUrl: './research.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Research implements OnDestroy {
  private readonly api = inject(ResearchApi);
  private readonly projects = inject(ProjectApi);
  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly project = signal<Project | null>(null);
  readonly workspace = signal<Workspace | null>(null);
  readonly provider = signal<ProviderStatus | null>(null);
  readonly selected = signal<Stage | 'source' | 'evidence' | 'history'>('source');
  readonly busy = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly auto = signal(false);
  readonly selectedPage = signal(1);
  readonly running = computed(() =>
    this.workspace()?.runs.find((r) => r.id === this.workspace()?.active_run),
  );
  readonly current = computed(() => this.workspace()?.artifacts[this.selected() as Stage]);
  readonly latestAttempt = computed(() =>
    this.workspace()?.runs.find(
      (run) => run.stage === this.selected() && run.workspace_version === this.workspace()?.version,
    ),
  );
  readonly sourcePage = computed(() =>
    this.workspace()?.source?.pages.find((p) => p.page === this.selectedPage()),
  );
  readonly chats = computed(() =>
    [...(this.workspace()?.runs ?? [])]
      .reverse()
      .filter((r) => r.stage === 'chat' && r.workspace_version === this.workspace()?.version),
  );
  readonly stages: { id: Stage; name: string; role: string }[] = [
    { id: 'analysis', name: 'Understand the paper', role: 'Research analyst' },
    { id: 'plan', name: 'Plan the experiment', role: 'Experiment planner' },
    { id: 'implementation', name: 'Draft the code', role: 'Implementation author' },
    { id: 'review', name: 'Review the method', role: 'Independent reviewer' },
    { id: 'results', name: 'Compare results', role: 'Results analyst' },
    { id: 'extensions', name: 'Explore extensions', role: 'Research analyst' },
    { id: 'report', name: 'Write the report', role: 'Documentation author' },
  ];
  paperText = '';
  paperName = '';
  feedbackText = '';
  feedbackStage: Stage = 'plan';
  question = '';
  metrics = '';
  hardware = '';
  command = '';
  evidenceNotes = '';
  private timer?: ReturnType<typeof setTimeout>;
  private destroyed = false;

  constructor() {
    void this.load();
  }
  ngOnDestroy() {
    this.destroyed = true;
    this.auto.set(false);
    clearTimeout(this.timer);
  }

  async load() {
    this.error.set('');
    try {
      const [project, workspace, provider] = await Promise.all([
        this.projects.get(this.id),
        this.api.get(this.id),
        this.api.status(),
      ]);
      this.project.set(project);
      this.workspace.set(workspace);
      this.provider.set(provider);
      this.schedule();
    } catch (e) {
      this.error.set(researchError(e));
    }
  }

  private schedule() {
    clearTimeout(this.timer);
    if (!this.destroyed) this.timer = setTimeout(() => void this.refresh(), 2000);
  }

  async refresh() {
    try {
      const previous = this.workspace();
      const next = await this.api.get(this.id);
      if (this.destroyed) return;
      // A completed local action owns its newer state; discard an older poll response.
      if (this.busy() || this.workspace() !== previous) return;
      this.workspace.set(next);
      if (previous && previous.version !== next.version) this.auto.set(false);
      if (this.auto() && !next.active_run && !this.busy()) {
        const last = next.runs[0];
        if (last && last.status !== 'completed') this.auto.set(false);
        else {
          const stage = this.nextStage();
          if (stage) await this.run(stage);
          else this.auto.set(false);
        }
      }
    } catch (e) {
      this.error.set(researchError(e));
      this.auto.set(false);
    } finally {
      this.schedule();
    }
  }

  nextStage(): Stage | undefined {
    const state = this.workspace();
    if (!state?.source) return undefined;
    return this.stages
      .map((s) => s.id)
      .find(
        (stage) => !(stage === 'results' && !state.evidence.metrics) && !state.artifacts[stage],
      );
  }

  stageName(stage: string) {
    return this.stages.find((s) => s.id === stage)?.name ?? stage;
  }
  blockReason(stage: Stage): string {
    const state = this.workspace();
    if (!state?.source) return 'Attach a paper first.';
    if (!this.provider()?.configured) return 'Configure GROQ_API_KEY on the backend.';
    if (state.active_run) return 'Another AI step is running.';
    const required: Partial<Record<Stage, Stage>> = {
      plan: 'analysis',
      implementation: 'plan',
      review: 'implementation',
      results: 'review',
      extensions: 'analysis',
      report: 'review',
    };
    const dependency = required[stage];
    if (dependency && !state.artifacts[dependency])
      return `Complete “${this.stageName(dependency)}” first.`;
    if (
      stage === 'implementation' &&
      this.project()?.setup.control_mode === 'guided' &&
      state.approved_plan !== state.artifacts.plan?.id
    )
      return 'Approve the current plan before generating code.';
    if (stage === 'results' && !state.evidence.metrics)
      return 'Record metrics from an actual run first.';
    return '';
  }

  async run(stage: Stage, message = '') {
    const state = this.workspace();
    if (!state || this.busy()) return;
    const blocked = this.blockReason(stage);
    if (blocked) {
      this.error.set(blocked);
      this.auto.set(false);
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.notice.set('');
    try {
      await this.api.run(this.id, state.version, stage, message);
      this.selected.set(stage);
      this.workspace.set(await this.api.get(this.id));
      if (stage === 'chat') this.question = '';
    } catch (e) {
      this.error.set(researchError(e));
      this.auto.set(false);
    } finally {
      this.busy.set(false);
      this.schedule();
    }
  }

  async continueWorkflow() {
    if (this.project()?.setup.control_mode !== 'autonomous') return;
    this.auto.set(true);
    const next = this.nextStage();
    if (next) await this.run(next);
  }

  private async mutate(path: string, data: object, success: string): Promise<boolean> {
    const state = this.workspace();
    if (!state || this.busy()) return false;
    this.busy.set(true);
    this.auto.set(false);
    this.error.set('');
    this.notice.set('');
    try {
      this.workspace.set(
        await this.api.post(this.id, path, { expected_version: state.version, ...data }),
      );
      this.notice.set(success);
      return true;
    } catch (e) {
      this.error.set(researchError(e));
      return false;
    } finally {
      this.busy.set(false);
      this.schedule();
    }
  }

  async pastePaper() {
    if (
      await this.mutate(
        'source/text',
        { text: this.paperText, name: this.paperName.trim() || 'Pasted paper' },
        'Paper saved. Start the analysis when ready.',
      )
    ) {
      this.paperText = '';
      this.selectedPage.set(1);
    }
  }
  async importUrl() {
    if (
      await this.mutate(
        'source/url',
        {},
        'Paper imported. Check the extracted text before analysis.',
      )
    )
      this.selectedPage.set(1);
  }
  async upload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    const state = this.workspace();
    if (!file || !state) return;
    if (file.size > 10 * 1024 * 1024) {
      this.error.set('Choose a PDF no larger than 10 MB.');
      return;
    }
    this.busy.set(true);
    this.auto.set(false);
    this.error.set('');
    try {
      this.workspace.set(await this.api.upload(this.id, state.version, file));
      this.selectedPage.set(1);
      this.notice.set('PDF text saved. Check the extraction before analysis.');
    } catch (e) {
      this.error.set(researchError(e));
    } finally {
      this.busy.set(false);
      input.value = '';
      this.schedule();
    }
  }
  approve() {
    return this.mutate(
      'approve',
      { plan_id: this.workspace()?.artifacts.plan?.id },
      'Current plan approved. Code generation is now available.',
    );
  }
  cancel() {
    return this.mutate(
      'cancel',
      {},
      'Stopped. A model request already sent may still incur usage.',
    );
  }
  async applyFeedback() {
    const stage = this.feedbackStage;
    if (
      await this.mutate(
        'feedback',
        { stage, message: this.feedbackText },
        'Feedback saved; affected work has been invalidated.',
      )
    ) {
      this.feedbackText = '';
      this.selected.set(stage);
      if (!this.blockReason(stage)) await this.run(stage);
    }
  }
  async saveEvidence() {
    try {
      const metrics: unknown = JSON.parse(this.metrics);
      if (
        !metrics ||
        Array.isArray(metrics) ||
        typeof metrics !== 'object' ||
        !Object.keys(metrics).length ||
        Object.values(metrics).some((v) => typeof v !== 'number' || !Number.isFinite(v))
      )
        throw new Error();
      if (
        await this.mutate(
          'evidence',
          { metrics, hardware: this.hardware, command: this.command, notes: this.evidenceNotes },
          'Metrics saved as self-reported evidence.',
        )
      )
        this.selected.set('results');
    } catch {
      this.error.set('Enter a JSON object of numeric metrics, such as {"accuracy": 0.91}.');
    }
  }
  showCitation(page: number) {
    this.selectedPage.set(page);
    this.selected.set('source');
  }
  downloadFile(path: string, content: string) {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = path.split('/').pop()!;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
