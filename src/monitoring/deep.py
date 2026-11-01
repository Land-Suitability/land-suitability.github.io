"""
PyTorch yield model on NDVI time series (optional deep-learning track).

A small 1D convolutional network reads the smoothed, resampled NDVI profile up to the forecast day and
predicts yield (t/ha). Monte Carlo dropout gives a spread. Training data: past plot-seasons with known
yields (from stage 12 deliveries and crop-cut surveys).
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

N_POINTS = 32


def resample(grid: np.ndarray, sm: np.ndarray, upto_day: int, season_days: int = 140) -> np.ndarray:
    """Fixed-length input: values on a regular grid over the whole season, zero after `upto_day` plus a mask."""
    t = np.linspace(0, season_days, N_POINTS)
    v = np.interp(t, grid, sm)
    mask = (t <= upto_day).astype(float)
    return np.stack([v * mask, mask])


class NDVIYieldNet(nn.Module):
    def __init__(self, p_drop: float = 0.2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(2, 16, 5, padding=2), nn.ReLU(), nn.Dropout(p_drop),
            nn.Conv1d(16, 16, 5, padding=2), nn.ReLU(), nn.Dropout(p_drop),
            nn.AdaptiveAvgPool1d(4), nn.Flatten(), nn.Linear(64, 32), nn.ReLU(), nn.Dropout(p_drop), nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() != 3 or x.shape[1] != 2:
            raise ValueError(f"Expected (B, 2, {N_POINTS}), got {tuple(x.shape)}")
        if not torch.isfinite(x).all():
            raise ValueError("NaN/Inf in NDVI input")
        return self.net(x).squeeze(-1)


def train(X: np.ndarray, y: np.ndarray, epochs: int = 300, seed: int = 0, verbose: bool = True) -> NDVIYieldNet:
    torch.manual_seed(seed)
    model = NDVIYieldNet()
    opt = torch.optim.Adam(model.parameters(), lr=3e-3, weight_decay=1e-4)
    xt, yt = torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
    for ep in range(1, epochs + 1):
        model.train()
        perm = torch.randperm(len(xt))
        for i in range(0, len(xt), 64):
            b = perm[i:i + 64]
            opt.zero_grad()
            loss = nn.functional.mse_loss(model(xt[b]), yt[b])
            if not torch.isfinite(loss):
                raise RuntimeError(f"Loss diverged at epoch {ep}")
            loss.backward()
            opt.step()
        if verbose and ep in (1, epochs // 2, epochs):
            print(f"  [DEBUG] epoch {ep:3d} batch loss {loss.item():.3f}")
    return model


@torch.no_grad()
def predict_mc(model: NDVIYieldNet, X: np.ndarray, n: int = 30) -> tuple[np.ndarray, np.ndarray]:
    model.train()                      # keep dropout active (MC dropout)
    xt = torch.tensor(X, dtype=torch.float32)
    preds = torch.stack([model(xt) for _ in range(n)]).numpy()
    model.eval()
    return preds.mean(0), preds.std(0)
