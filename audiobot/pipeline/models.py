from __future__ import annotations

import torch
from torch import nn


class DenoiserNet(nn.Module):
    """Small 1D Conv Denoiser for speech.

    Architecture: Conv stack with dilations + residuals, maps noisy->clean.
    Lightweight by design to train fast and serve on CPU.
    """

    def __init__(self, channels: int = 64, n_layers: int = 8, kernel_size: int = 9):
        super().__init__()
        pad = kernel_size // 2
        self.inp = nn.Conv1d(1, channels, kernel_size, padding=pad)
        blocks = []
        for i in range(n_layers):
            dil = 2 ** (i % 4)
            blocks.append(
                nn.Sequential(
                    nn.Conv1d(channels, channels, kernel_size, padding=pad * dil, dilation=dil),
                    nn.ReLU(inplace=True),
                    nn.Conv1d(channels, channels, 1),
                )
            )
        self.blocks = nn.ModuleList(blocks)
        self.out = nn.Conv1d(channels, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T] or [B, 1, T]
        if x.dim() == 2:
            x = x.unsqueeze(1)
        h = self.inp(x)
        for blk in self.blocks:
            h = h + blk(h)
            h = torch.relu(h)
        y = self.out(h)
        return y.squeeze(1)

