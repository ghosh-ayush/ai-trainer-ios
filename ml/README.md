# Offline model tooling

This directory is reserved for Python training, evaluation and future CoreML export
utilities. There is no trained model or validated form/recovery model in this change.

Keep heavyweight development dependencies (for example PyTorch or coremltools) in a
separate, pinned development environment here. Do not import them from `core/python`
or bundle them into the iOS Python runtime. Export versioned CoreML artifacts with
input/output metadata and validation results; native Swift/Vision/CoreML owns
inference, camera timing and lifecycle. Model observations remain uncertain and
never automatically become confirmed sets or accepted recommendations.
