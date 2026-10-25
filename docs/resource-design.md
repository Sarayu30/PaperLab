# Resources depend on the experiment

Research reviewed 24 October 2026. These are PaperLab design decisions based on the sources below,
not automatic estimates extracted from an uploaded paper.

## Evidence and implications

- [NeurIPS checklist](https://nips.cc/public/guides/PaperChecklist): compute reporting includes workers,
  memory, storage, time per run and total compute. A single project-level GPU number is insufficient.
- [scikit-learn resource management](https://scikit-learn.org/stable/computing/parallelism.html):
  CPU parallelism involves joblib, OpenMP and BLAS. CPU count and memory matter even without a GPU.
- [Accelerate memory estimator](https://huggingface.co/docs/accelerate/usage_guides/model_size_estimator):
  weight-loading estimates differ from training and inference needs. Do not invent a VRAM requirement
  from the model name alone, or call weight size an end-to-end feasibility check.
- [Claude API limits](https://platform.claude.com/docs/en/api/rate-limits): hosted experiments can be
  constrained by request and token rates independently of spend. PaperLab assistant spend and the
  experiment's API spend are separate concerns.
- [Colab FAQ](https://research.google.com/colaboratory/faq.html): runtime availability and limits vary.
  Selecting Colab must not imply a guaranteed GPU, duration, connection or unattended worker.
- [Ray resources](https://docs.ray.io/en/latest/ray-core/scheduling/resources.html): CPU, GPU, memory
  and custom resources are distinct. Scheduling declarations are not physical usage enforcement.

## Implemented contract

Every project may start with an undecided workload, undecided execution location, and no resource
requirements. Workload suggestions cover CPU analysis, training, inference, API evaluation,
simulation and other work. Users add only relevant fields and can remove them or add a custom
requirement. Changing workload changes suggestions, never silently deletes saved requirements.

Numeric requirements have explicit units and semantics: available CPU/RAM/VRAM/storage; ceilings
on GPU time, wall time, experimental API spend and assistant spend; request/token quotas.
Text requirements cover hardware, software/simulators, data access, networking and custom needs.
Blank values are unknown (`null`). Zero is an explicit zero; an omitted field is unspecified.
Unknown and unspecified never mean unlimited permission to execute.

Plans are saved and versioned, not executed or enforced in this milestone. The user's choice of
location is a preference, not an integration. Existing v0.1 JSON revisions remain intact and are
interpreted as explicit resources on read. Legacy API fields remain accepted during transition.

## Next execution stage

Extract per-experiment requirements with paper citations; distinguish reported facts, estimates,
measured smoke-test usage and user limits. Resolve runtime/device/software/data access, number
of seeds and trials, precision, checkpoints, and interruption policy before proposing a run.
Require human resolution for unknown prerequisites; validate hard limits in the runner and
aggregate spend/compute across runs. Custom free text needs human interpretation before execution.
The current project-level requirements are a starting envelope, not a per-run scheduler.
