# Helia AI - Solar Rooftop Assessment

This repository contains a scaffold for the Helia AI project: frontend (React+TS+Tailwind) and backend (Flask).

See `backend/` and `frontend/` folders for details. Use `database/schema.sql` to create MySQL schema.

## Roof Segmentation Training

A new roof segmentation training script is available at `Backend/train_roof_segmentation.py`.

It trains a binary roof mask model using U-Net with ResNet34 encoder on rooftop imagery.

Usage:

```bash
python Backend/train_roof_segmentation.py --mode train --epochs 50 --batch-size 8
```

To infer on a single image:

```bash
python Backend/train_roof_segmentation.py --mode predict --image path/to/rooftop.jpg
```

Generated artifacts:

- `Backend/models/roof_segmentation_best.pth`
- `Backend/plots/roof_segmentation_training_curves.png`
- `Backend/plots/roof_segmentation_loss_curve.png`
- `Backend/models/roof_segmentation_prediction_mask.png`
- `Backend/models/roof_segmentation_prediction_overlay.png`

