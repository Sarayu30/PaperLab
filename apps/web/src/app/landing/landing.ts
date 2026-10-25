import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  imports: [RouterLink],
  templateUrl: './landing.html',
  styleUrl: './landing.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Landing {
  readonly examples = [
    {
      name: 'On your laptop',
      tag: 'CPU / CLASSICAL ML',
      title: 'Start small. Still ask a real question.',
      description:
        'A CPU experiment has different needs from a training run. Record the resources that matter to the method.',
      fields: [
        ['CPU cores', '4 available'],
        ['System RAM', '16 GB'],
        ['Dataset access', 'Public dataset'],
      ],
      note: 'No GPU requirement added.',
    },
    {
      name: 'Training a model',
      tag: 'TRAINING / FINE-TUNING',
      title: 'Make the compute part of the plan.',
      description:
        'Separate accelerator memory, total GPU time and checkpoint storage. Unknown hardware can stay unknown.',
      fields: [
        ['Accelerator memory', 'To be confirmed'],
        ['GPU time ceiling', '2 GPU-hours'],
        ['Checkpoint storage', '20 GB'],
      ],
      note: 'Availability is verified before execution — planned.',
    },
    {
      name: 'Using a model API',
      tag: 'HOSTED EVALUATION',
      title: 'A model call is an experiment, too.',
      description:
        'Track experiment spend and provider quotas independently. The assistant budget belongs to a different line.',
      fields: [
        ['Experiment API budget', '$10 ceiling'],
        ['Request quota', 'To be confirmed'],
        ['Assistant budget', 'Not specified'],
      ],
      note: 'No local accelerator assumed.',
    },
  ];
  readonly selected = signal(0);
  readonly feedbackApplied = signal(false);
  select(index: number) {
    this.selected.set(index);
    this.feedbackApplied.set(false);
  }
  example() {
    return this.examples[this.selected()];
  }
}
