import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { errorMessage, ProjectApi, ProjectSetup } from './project-api';

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
    max_gpu_hours: [2, [Validators.required, Validators.min(0), Validators.max(10000)]],
    max_llm_cost_usd: [5, [Validators.required, Validators.min(0), Validators.max(100000)]],
    hardware: ['To be confirmed', requiredText(200)],
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
      this.form.reset({ ...project.setup, note: '' });
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
      hardware: 'To be confirmed',
    });
  }

  async save() {
    if (this.saving() || this.loading()) return;
    this.submitted.set(true);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const { note, ...setup } = this.form.getRawValue();
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
