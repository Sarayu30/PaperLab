export const resourceCatalog = {
  cpu_cores: {
    label: 'CPU cores available',
    unit: 'cores',
    hint: 'Available parallel workers; not a promise of faster execution.',
    type: 'count',
  },
  ram_gb: {
    label: 'System RAM available',
    unit: 'GB',
    hint: 'Host memory for data, preprocessing and workers.',
    type: 'number',
  },
  storage_gb: {
    label: 'Disk space available',
    unit: 'GB',
    hint: 'Include datasets, cached weights and checkpoints.',
    type: 'number',
  },
  vram_gb: {
    label: 'Accelerator memory available',
    unit: 'GB / device',
    hint: 'Memory per GPU or accelerator, separate from system RAM.',
    type: 'number',
  },
  gpu_hours: {
    label: 'GPU time ceiling',
    unit: 'GPU-hours',
    hint: 'Total across devices and runs: 2 GPUs × 3 hours = 6 GPU-hours.',
    type: 'number',
  },
  wall_hours: {
    label: 'Run duration ceiling',
    unit: 'hours / run',
    hint: 'Maximum elapsed time for one run, including preprocessing.',
    type: 'number',
  },
  experiment_budget: {
    label: 'Experiment API budget',
    unit: 'USD',
    hint: 'Hosted model calls made by the experiment. Excludes compute rental.',
    type: 'number',
  },
  assistant_budget: {
    label: 'PaperLab assistant budget',
    unit: 'USD',
    hint: 'Agent assistance across this project, separate from experiment API calls.',
    type: 'number',
  },
  requests_per_minute: {
    label: 'API request quota',
    unit: 'requests / min',
    hint: 'Your provider/account quota; check the provider console.',
    type: 'count',
  },
  tokens_per_minute: {
    label: 'API token quota',
    unit: 'tokens / min',
    hint: 'Specify separate input/output quotas as custom requirements if needed.',
    type: 'count',
  },
  hardware: {
    label: 'Hardware details',
    unit: '',
    hint: 'Device model, count, accelerator type or CPU-only requirement.',
    type: 'text',
  },
  software: {
    label: 'Software or simulator',
    unit: '',
    hint: 'Framework versions, CUDA, simulator, solver or operating system.',
    type: 'text',
  },
  data_access: {
    label: 'Data access',
    unit: '',
    hint: 'Dataset license, access approval, storage location or offline copy.',
    type: 'text',
  },
  network: {
    label: 'Network requirements',
    unit: '',
    hint: 'Internet access, offline execution or restricted endpoints.',
    type: 'text',
  },
  custom: {
    label: 'Custom requirement',
    unit: '',
    hint: 'A project-specific condition to review before running.',
    type: 'text',
  },
} as const;
export type ResourceKind = keyof typeof resourceCatalog;
export interface ResourceRequirement {
  kind: ResourceKind;
  label: string;
  value: number | string | null;
}
export const workloads = {
  undecided: {
    label: 'Decide after reading',
    description: 'Start with the paper. Add requirements when you know what the experiment needs.',
    suggestions: [],
  },
  cpu: {
    label: 'CPU / classical ML',
    description: 'Think data size, parallel workers, memory and runtime. A GPU may be irrelevant.',
    suggestions: ['cpu_cores', 'ram_gb', 'storage_gb', 'wall_hours'],
  },
  training: {
    label: 'Training / fine-tuning',
    description:
      'Training may need accelerator memory, checkpoint storage and a total compute ceiling.',
    suggestions: ['hardware', 'vram_gb', 'gpu_hours', 'storage_gb', 'software'],
  },
  inference: {
    label: 'Inference / evaluation',
    description:
      'Loading weights is only part of memory use. Account for batches and evaluation data.',
    suggestions: ['hardware', 'vram_gb', 'ram_gb', 'storage_gb', 'wall_hours'],
  },
  api: {
    label: 'Hosted API experiment',
    description:
      'Record provider quotas and experiment spend. Local GPU fields are usually unnecessary.',
    suggestions: ['experiment_budget', 'requests_per_minute', 'tokens_per_minute', 'network'],
  },
  simulation: {
    label: 'Simulation / RL',
    description:
      'Simulator versions, parallel environments and run duration can be the main constraints.',
    suggestions: ['software', 'cpu_cores', 'ram_gb', 'wall_hours', 'hardware'],
  },
  other: {
    label: 'Other / mixed workload',
    description: 'Combine any fields below, or describe a requirement specific to this paper.',
    suggestions: ['software', 'data_access', 'custom'],
  },
} satisfies Record<string, { label: string; description: string; suggestions: ResourceKind[] }>;
export const environments = {
  undecided: 'Decide later',
  local: 'Local / VS Code',
  colab: 'Google Colab',
  kaggle: 'Kaggle',
  remote: 'Remote machine / cluster',
  other: 'Other',
};
export interface ResourcePlan {
  workload: keyof typeof workloads;
  environment: keyof typeof environments;
  requirements: ResourceRequirement[];
}
export function resourceValue(row: ResourceRequirement): string {
  if (row.value === null) return 'To be confirmed';
  return `${row.value}${resourceCatalog[row.kind].unit ? ' ' + resourceCatalog[row.kind].unit : ''}`;
}
export function resourceSummary(plan: ResourcePlan): string {
  return [
    workloads[plan.workload].label,
    environments[plan.environment],
    ...plan.requirements.map((r) => `${r.label}: ${resourceValue(r)}`),
  ].join(' · ');
}
