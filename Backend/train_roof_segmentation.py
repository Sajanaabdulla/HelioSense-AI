# =============================================================================
# HelioSense AI — Roof Segmentation Training
# =============================================================================
# Purpose: Train a U-Net roof segmentation model for rooftop imagery.
# Model:   U-Net with ResNet34 encoder
# Input:   512x512 RGB rooftop images
# Output:  Binary roof mask prediction
# Data:    Backend/data/roof_segmentation/{train,train_mask,validate,validate_mask,test,test_mask}
# =============================================================================

import argparse
import os
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
import torchvision.transforms as T
import segmentation_models_pytorch as smp


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = BASE_DIR / "data" / "roof_segmentation"
TRAIN_IMAGES = DATA_ROOT / "train"
TRAIN_MASKS = DATA_ROOT / "train_mask"
VAL_IMAGES = DATA_ROOT / "validate"
VAL_MASKS = DATA_ROOT / "validate_mask"
TEST_IMAGES = DATA_ROOT / "test"
TEST_MASKS = DATA_ROOT / "test_mask"
MODELS_DIR = BASE_DIR / "models"
PLOTS_DIR = BASE_DIR / "plots"
BEST_MODEL_PATH = MODELS_DIR / "roof_segmentation_best.pth"
TRAIN_PLOT_PATH = PLOTS_DIR / "roof_segmentation_training_curves.png"
LOSS_PLOT_PATH = PLOTS_DIR / "roof_segmentation_loss_curve.png"
PREDICTION_MASK_PATH = MODELS_DIR / "roof_segmentation_prediction_mask.png"
PREDICTION_OVERLAY_PATH = MODELS_DIR / "roof_segmentation_prediction_overlay.png"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# -----------------------------------------------------------------------------
# Dataset
# -----------------------------------------------------------------------------
class RoofSegmentationDataset(Dataset):
    def __init__(self, images_dir, masks_dir, augment=False):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.augment = augment

        self.image_paths = self._load_paths(self.images_dir)
        self.mask_paths = self._load_paths(self.masks_dir)
        self.mask_map = {p.stem: p for p in self.mask_paths}

        self.samples = []
        for image_path in self.image_paths:
            mask_path = self.mask_map.get(image_path.stem)
            if mask_path is not None:
                self.samples.append((image_path, mask_path))

        if not self.samples:
            raise FileNotFoundError(
                f"No matched image/mask pairs found in {images_dir} and {masks_dir}."
            )

        self.transform_image = T.Compose([
            T.Resize((512, 512), interpolation=Image.BILINEAR),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        self.transform_mask = T.Compose([
            T.Resize((512, 512), interpolation=Image.NEAREST),
            T.ToTensor(),
        ])

    @staticmethod
    def _load_paths(folder):
        return sorted(
            [p for p in Path(folder).glob("**/*") if p.suffix.lower() in IMAGE_EXTENSIONS]
        )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        image_path, mask_path = self.samples[index]
        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")

        image = self.transform_image(image)
        mask = self.transform_mask(mask)
        mask = (mask > 0.5).float()

        if self.augment:
            image, mask = self._apply_augmentations(image, mask)

        return image, mask

    @staticmethod
    def _apply_augmentations(image, mask):
        if torch.rand(1) < 0.5:
            image = torch.flip(image, dims=[2])
            mask = torch.flip(mask, dims=[2])
        if torch.rand(1) < 0.5:
            image = torch.flip(image, dims=[1])
            mask = torch.flip(mask, dims=[1])
        return image, mask


# -----------------------------------------------------------------------------
# Metrics and loss
# -----------------------------------------------------------------------------
class DiceBCELoss(nn.Module):
    def __init__(self, smooth=1e-6):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        bce_loss = self.bce(logits, targets)
        intersection = (probs * targets).sum(dim=(2, 3))
        dice_score = (2.0 * intersection + self.smooth) / (
            probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3)) + self.smooth
        )
        dice_loss = 1.0 - dice_score.mean()
        return bce_loss + dice_loss


def compute_metrics(logits, targets, threshold=0.5):
    probs = torch.sigmoid(logits)
    preds = (probs >= threshold).float()
    targets = (targets >= 0.5).float()

    intersection = (preds * targets).sum(dim=(2, 3))
    union = (preds + targets - preds * targets).sum(dim=(2, 3))
    preds_sum = preds.sum(dim=(2, 3))
    targets_sum = targets.sum(dim=(2, 3))

    iou = (intersection + 1e-6) / (union + 1e-6)
    dice = (2.0 * intersection + 1e-6) / (preds_sum + targets_sum + 1e-6)

    return iou.mean().item(), dice.mean().item()


# -----------------------------------------------------------------------------
# Model builder
# -----------------------------------------------------------------------------
def build_model():
    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights="imagenet",
        in_channels=3,
        classes=1,
        activation=None,
    )
    return model.to(DEVICE)


# -----------------------------------------------------------------------------
# Training / validation loops
# -----------------------------------------------------------------------------

def epoch_step(model, loader, optimizer, criterion, training=False):
    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_iou = 0.0
    total_dice = 0.0
    count = 0

    for images, masks in loader:
        images = images.to(DEVICE, non_blocking=True)
        masks = masks.to(DEVICE, non_blocking=True)

        with torch.set_grad_enabled(training):
            logits = model(images)
            loss = criterion(logits, masks)
            iou, dice = compute_metrics(logits, masks)

            if training:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        batch_size = images.size(0)
        total_loss += loss.item() * batch_size
        total_iou += iou * batch_size
        total_dice += dice * batch_size
        count += batch_size

    return {
        "loss": total_loss / max(count, 1),
        "iou": total_iou / max(count, 1),
        "dice": total_dice / max(count, 1),
    }


# -----------------------------------------------------------------------------
# Plotting
# -----------------------------------------------------------------------------

def plot_training_curves(history):
    plt.style.use("seaborn-darkgrid")
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(history["epoch"], history["train_loss"], label="Train Loss", color="#FFB300", linewidth=2)
    ax.plot(history["epoch"], history["val_loss"], label="Val Loss", color="#1976D2", linewidth=2)
    ax.set_xlabel("Epoch", fontsize=12)
    ax.set_ylabel("Loss", fontsize=12)
    ax.set_title("Roof Segmentation Training Curves", fontsize=14)
    ax.legend()
    fig.tight_layout()
    fig.savefig(TRAIN_PLOT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(history["epoch"], history["val_iou"], label="Val IoU", color="#00BFA5", linewidth=2)
    ax.plot(history["epoch"], history["val_dice"], label="Val Dice", color="#D32F2F", linewidth=2)
    ax.set_xlabel("Epoch", fontsize=12)
    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Roof Segmentation Metrics", fontsize=14)
    ax.set_ylim(0.0, 1.0)
    ax.legend()
    fig.tight_layout()
    fig.savefig(LOSS_PLOT_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)


# -----------------------------------------------------------------------------
# Predict and save mask
# -----------------------------------------------------------------------------

def predict_roof_mask(model, image_path, output_mask_path, output_overlay_path):
    model.eval()
    image = Image.open(image_path).convert("RGB")
    original_size = image.size
    image_resized = image.resize((512, 512), resample=Image.BILINEAR)

    preprocess = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    tensor = preprocess(image_resized).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)[0, 0].cpu().numpy()

    mask = (probs >= 0.5).astype(np.uint8) * 255
    mask_image = Image.fromarray(mask).convert("L").resize(original_size, resample=Image.NEAREST)
    mask_image.save(output_mask_path)

    overlay = Image.new("RGBA", original_size)
    base = image.convert("RGBA")
    overlay_mask = Image.fromarray((np.stack([mask] * 3, axis=-1)).astype(np.uint8), mode="RGB")
    overlay_mask = overlay_mask.resize(original_size, resample=Image.NEAREST)
    overlay_mask = Image.fromarray(np.array(overlay_mask) * np.array([255, 0, 0], dtype=np.uint8) // 255).convert("RGBA")
    alpha = Image.fromarray((mask).astype(np.uint8)).convert("L")
    alpha = alpha.point(lambda x: min(120, x))
    overlay_mask.putalpha(alpha)
    overlay = Image.alpha_composite(base, overlay_mask)
    overlay.save(output_overlay_path)

    return output_mask_path, output_overlay_path


# -----------------------------------------------------------------------------
# Main flow
# -----------------------------------------------------------------------------

def run_training(args):
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    train_dataset = RoofSegmentationDataset(TRAIN_IMAGES, TRAIN_MASKS, augment=True)
    val_dataset = RoofSegmentationDataset(VAL_IMAGES, VAL_MASKS, augment=False)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
    )

    model = build_model()
    criterion = DiceBCELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5, verbose=True
    )

    history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
        "val_iou": [],
        "val_dice": [],
    }

    best_val_loss = float("inf")
    start_time = time.time()

    print("\nStarting roof segmentation training")
    print(f"Device: {DEVICE}")
    print(f"Train samples: {len(train_dataset)} | Validation samples: {len(val_dataset)}")
    print(f"Epochs: {args.epochs} | Batch size: {args.batch_size}\n")

    for epoch in range(1, args.epochs + 1):
        train_stats = epoch_step(model, train_loader, optimizer, criterion, training=True)
        val_stats = epoch_step(model, val_loader, optimizer, criterion, training=False)

        history["epoch"].append(epoch)
        history["train_loss"].append(train_stats["loss"])
        history["val_loss"].append(val_stats["loss"])
        history["val_iou"].append(val_stats["iou"])
        history["val_dice"].append(val_stats["dice"])

        scheduler.step(val_stats["loss"])

        print(
            f"Epoch {epoch:02d}/{args.epochs:02d} "
            f"| Train Loss: {train_stats['loss']:.4f} "
            f"| Val Loss: {val_stats['loss']:.4f} "
            f"| Val IoU: {val_stats['iou']:.4f} "
            f"| Val Dice: {val_stats['dice']:.4f}"
        )

        if val_stats["loss"] < best_val_loss:
            best_val_loss = val_stats["loss"]
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": best_val_loss,
                },
                BEST_MODEL_PATH,
            )
            print(f"  ✔ Best model saved to {BEST_MODEL_PATH}")

    elapsed = time.time() - start_time
    print(f"\nTraining complete in {elapsed/60:.2f} minutes.")
    plot_training_curves(history)
    print(f"Training curves saved: {TRAIN_PLOT_PATH}")
    print(f"Metric plots saved: {LOSS_PLOT_PATH}")

    return BEST_MODEL_PATH


def run_prediction(args):
    if not Path(args.image).exists():
        raise FileNotFoundError(f"Image not found: {args.image}")
    if not Path(BEST_MODEL_PATH).exists():
        raise FileNotFoundError(
            f"Best model not found. Run training first and save to {BEST_MODEL_PATH}"
        )

    model = build_model()
    checkpoint = torch.load(BEST_MODEL_PATH, map_location=DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])

    os.makedirs(MODELS_DIR, exist_ok=True)

    mask_path, overlay_path = predict_roof_mask(
        model,
        args.image,
        PREDICTION_MASK_PATH,
        PREDICTION_OVERLAY_PATH,
    )

    print(f"Prediction saved:")
    print(f"  Roof mask: {mask_path}")
    print(f"  Overlay:   {overlay_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train and evaluate roof segmentation using U-Net + ResNet34"
    )
    parser.add_argument(
        "--mode",
        choices=["train", "predict"],
        default="train",
        help="Run training or prediction"
    )
    parser.add_argument(
        "--image",
        type=str,
        default="",
        help="Input rooftop image for prediction"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Training batch size"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-4,
        help="Learning rate for optimizer"
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of data loader workers"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.mode == "train":
        run_training(args)
    elif args.mode == "predict":
        run_prediction(args)


if __name__ == "__main__":
    main()
