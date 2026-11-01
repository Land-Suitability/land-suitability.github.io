"""
Deep-learning track for land suitability (PyTorch).

Idea
  The rule-based engine (scoring.py) encodes expert knowledge but uses fixed thresholds.
  A learned model can discover patterns the rules miss (e.g. interactions between slope,
  rainfall and soil). We train it in two steps:
    1. Pre-train on rule-based labels (weak labels, cheap and everywhere).
    2. Fine-tune on field truth (trial yields, farmer-reported performance) where available.
  Analogy: an apprentice first learns from the textbook (rules), then from the master
  farmer's experience (field data), and is graded on the latter.

Input   : (B, C, H, W) stack of co-registered layers (Sentinel-2 bands/indices, DEM
          derivatives, soil and climate grids), normalised per channel.
Output  : dict crop -> (B, 4, H, W) logits over [N, S3, S2, S1].
Missing : label -1 is ignored in the loss.
Uncertainty: Monte Carlo dropout at inference.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

N_CLASSES = 4          # index 0=N, 1=S3, 2=S2, 3=S1 (same as class rank in scoring.py)
IGNORE_INDEX = -1


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, p_drop: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(c_in, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True),
            nn.Conv2d(c_out, c_out, 3, padding=1, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(inplace=True),
            nn.Dropout2d(p_drop),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class MultiCropSuitabilityNet(nn.Module):
    """Small U-Net style encoder-decoder with one segmentation head per crop."""

    def __init__(self, in_channels: int, crops: list[str], width: int = 32, p_drop: float = 0.1):
        super().__init__()
        if not crops:
            raise ValueError("At least one crop is required")
        self.crops = list(crops)
        self.enc1 = ConvBlock(in_channels, width, p_drop)
        self.enc2 = ConvBlock(width, width * 2, p_drop)
        self.bottleneck = ConvBlock(width * 2, width * 4, p_drop)
        self.up2 = nn.ConvTranspose2d(width * 4, width * 2, 2, stride=2)
        self.dec2 = ConvBlock(width * 4, width * 2, p_drop)
        self.up1 = nn.ConvTranspose2d(width * 2, width, 2, stride=2)
        self.dec1 = ConvBlock(width * 2, width, p_drop)
        self.heads = nn.ModuleDict({c: nn.Conv2d(width, N_CLASSES, 1) for c in self.crops})

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        if x.dim() != 4:
            raise ValueError(f"Expected input (B, C, H, W), got {tuple(x.shape)}")
        if x.shape[-1] % 4 or x.shape[-2] % 4:
            raise ValueError(f"H and W must be divisible by 4 (two pooling steps), got {tuple(x.shape[-2:])}")
        if not torch.isfinite(x).all():
            raise ValueError("Input contains NaN/Inf: fill or mask nodata before the model")
        e1 = self.enc1(x)
        e2 = self.enc2(F.max_pool2d(e1, 2))
        b = self.bottleneck(F.max_pool2d(e2, 2))
        d2 = self.dec2(torch.cat([self.up2(b), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return {c: head(d1) for c, head in self.heads.items()}


def multi_crop_loss(logits: dict[str, torch.Tensor], targets: dict[str, torch.Tensor],
                    crop_weights: dict[str, float] | None = None) -> torch.Tensor:
    """Sum of per-crop cross-entropy, ignoring missing labels (-1)."""
    total = None
    for crop, lg in logits.items():
        if crop not in targets:
            continue
        y = targets[crop]
        if y.shape != (lg.shape[0], *lg.shape[2:]):
            raise ValueError(f"{crop}: target shape {tuple(y.shape)} does not match logits {tuple(lg.shape)}")
        if (y != IGNORE_INDEX).sum() == 0:
            continue
        loss = F.cross_entropy(lg, y, ignore_index=IGNORE_INDEX)
        loss = loss * (crop_weights or {}).get(crop, 1.0)
        total = loss if total is None else total + loss
    if total is None:
        raise ValueError("No valid labels in this batch for any crop")
    return total


@torch.no_grad()
def predict_with_uncertainty(model: MultiCropSuitabilityNet, x: torch.Tensor, n_samples: int = 20):
    """
    Monte Carlo dropout: keep dropout active, average softmax over n_samples passes.
    Returns crop -> (class map, confidence = max mean prob, entropy).
    """
    model.eval()
    for m in model.modules():                 # re-enable dropout only
        if isinstance(m, nn.Dropout2d):
            m.train()
    probs = {c: [] for c in model.crops}
    for _ in range(n_samples):
        out = model(x)
        for c in model.crops:
            probs[c].append(F.softmax(out[c], dim=1))
    model.eval()
    result = {}
    for c in model.crops:
        p = torch.stack(probs[c]).mean(0)                    # (B, K, H, W)
        entropy = -(p * torch.log(p.clamp_min(1e-8))).sum(1)
        conf, cls = p.max(1)
        result[c] = {"class": cls, "confidence": conf, "entropy": entropy}
    return result
