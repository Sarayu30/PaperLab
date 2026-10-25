import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { errorMessage, ProjectApi, ProjectSetup } from './project-api';
import {
  resourceCatalog,
  workloads,
  environments,
  ResourceKind,
  ResourcePlan,
  ResourceRequirement,
} from './resources';

const requiredText = (max: number, min = 1) => [
  Validators.required,
  Validators.pattern(/\S/),
  Validators.minLength(min),
  Validators.maxLength(max),
];

@Component({
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './project-form.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProjectForm {
  private readonly api = inject(ProjectApi);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id');
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly conflict = signal(false);
  readonly revision = signal(0);
  readonly submitted = signal(false);
  readonly catalog = resourceCatalog;
  readonly resourceKinds = Object.keys(resourceCatalog) as ResourceKind[];
  readonly workloads = workloads;
  readonly workloadKeys = Object.keys(workloads) as (keyof typeof workloads)[];
  readonly environments = environments;
  readonly environmentKeys = Object.keys(environments) as (keyof typeof environments)[];
  readonly requirements = signal<ResourceRequirement[]>([]);
  readonly resourceError = signal('');
  private legacy: Pick<ProjectSetup, 'max_gpu_hours' | 'max_llm_cost_usd' | 'hardware'> = {};
  readonly form = this.fb.group({
    name: ['', requiredText(120)],
    paper_url: [
      '',
      [Validators.required, Validators.pattern(/^https?:\/\/\S+$/), Validators.maxLength(2048)],
    ],
    target_result: ['', requiredText(1000, 3)],
    dataset: ['', requiredText(200)],
    metric: ['', requiredText(80)],
    reproduction_mode: this.fb.control<ProjectSetup['reproduction_mode']>('reimplement'),
    control_mode: this.fb.control<ProjectSetup['control_mode']>('guided'),
    learning_mode: true,
    workload: this.fb.control<ResourcePlan['workload']>('undecided'),
    environment: this.fb.control<ResourcePlan['environment']>('undecided'),
    note: [''],
  });

  constructor() {
    if (this.id) {
      this.form.controls.note.setValidators(requiredText(2000, 3));
      void this.reload();
    }
  }

  invalid(field: keyof typeof this.form.controls): boolean {
    const control = this.form.controls[field];
    return control.invalid && (control.touched || this.submitted());
  }

  async reload() {
    if (!this.id) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const project = await this.api.get(this.id);
      this.form.reset({
        ...project.setup,
        workload: project.setup.resource_plan.workload,
        environment: project.setup.resource_plan.environment,
        note: '',
      });
      this.requirements.set(project.setup.resource_plan.requirements.map((r) => ({ ...r })));
      this.legacy = {
        max_gpu_hours: project.setup.max_gpu_hours,
        max_llm_cost_usd: project.setup.max_llm_cost_usd,
        hardware: project.setup.hardware,
      };
      this.resourceError.set('');
      this.revision.set(project.revision);
      this.conflict.set(false);
      this.submitted.set(false);
    } catch (error) {
      this.error.set(errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  sample() {
    this.form.patchValue({
      name: 'ResNet reproduction — setup example',
      paper_url: 'https://arxiv.org/abs/1512.03385',
      target_result: 'Select and verify one CIFAR-10 result from the paper before implementation.',
      dataset: 'CIFAR-10',
      metric: 'test_error',
      workload: 'training',
    });
  }

  hasResource(kind: ResourceKind) {
    return kind !== 'custom' && this.requirements().some((r) => r.kind === kind);
  }
  addResource(kind: ResourceKind) {
    if (this.hasResource(kind) || this.requirements().length >= 30) return;
    this.requirements.update((rows) => [
      ...rows,
      { kind, label: kind === 'custom' ? '' : this.catalog[kind].label, value: null },
    ]);
  }
  removeResource(index: number) {
    this.requirements.update((rows) => rows.filter((_, i) => i !== index));
  }
  editResource(index: number, field: 'value' | 'label', event: Event) {
    const input = event.target as HTMLInputElement;
    const raw = input.value;
    this.requirements.update((rows) =>
      rows.map((row, i) => {
        if (i !== index) return row;
        if (field === 'label') return { ...row, label: raw };
        return {
          ...row,
          value: input.validity.badInput
            ? Number.NaN
            : raw.trim() === ''
              ? null
              : this.catalog[row.kind].type === 'text'
                ? raw
                : Number(raw),
        };
      }),
    );
  }
  validateResources(): boolean {
    const labels = new Set<string>();
    for (const row of this.requirements()) {
      if (!row.label.trim() || labels.has(row.label.trim().toLowerCase())) {
        this.resourceError.set('Give each custom requirement a unique, nonempty name.');
        return false;
      }
      labels.add(row.label.trim().toLowerCase());
      if (
        typeof row.value === 'number' &&
        (!Number.isFinite(row.value) ||
          row.value < 0 ||
          (this.catalog[row.kind].type === 'count' && !Number.isInteger(row.value)))
      ) {
        this.resourceError.set(
          'Use nonnegative numbers and whole numbers for counts. Leave unknown values blank.',
        );
        return false;
      }
    }
    this.resourceError.set('');
    return true;
  }

  async save() {
    if (this.saving() || this.loading() || this.conflict()) return;
    this.submitted.set(true);
    if (!this.validateResources() || this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const { note, workload, environment, ...fields } = this.form.getRawValue();
    const setup: ProjectSetup = {
      ...fields,
      ...this.legacy,
      resource_plan: {
        workload,
        environment,
        requirements: this.requirements().map((r) => ({
          ...r,
          label: r.label.trim(),
          value: typeof r.value === 'string' ? r.value.trim() || null : r.value,
        })),
      },
    };
    try {
      const result = this.id
        ? await this.api.revise(this.id, this.revision(), setup, note)
        : await this.api.create(setup);
      await this.router.navigate(['/projects', result.id], { state: { saved: true } });
    } catch (error) {
      this.conflict.set(error instanceof HttpErrorResponse && error.status === 409);
      this.error.set(errorMessage(error));
    } finally {
      this.saving.set(false);
    }
  }
}
