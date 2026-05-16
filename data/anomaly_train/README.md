# Put normal copper tube training images here

PatchCore, EfficientAD, and FastFlow need copper-tube normal samples before they can produce useful checkpoints.

Expected layout:

```text
data/anomaly_train/ok/
  sample_001.jpg
  sample_002.jpg
  ...
```

After enough OK images are collected, train/export model checkpoints into:

- `models/patchcore/model.ckpt`
- `models/efficientad/model.ckpt`
- `models/fastflow/model.ckpt`
