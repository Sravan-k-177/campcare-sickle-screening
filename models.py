import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def get_polar_grid(height: int, width: int, target_device: torch.device):
    """Calculates angular (theta) and radial (r) polar coordinates in Fourier space."""
    y = torch.linspace(-1, 1, height, device=target_device)
    x = torch.linspace(-1, 1, width, device=target_device)
    yy, xx = torch.meshgrid(y, x, indexing="ij")
    theta = torch.atan2(yy, xx) % (2 * np.pi)
    radius = torch.sqrt(xx**2 + yy**2)
    return theta, radius


class DirectionalCurveletBlock(nn.Module):
    """Directional Fourier wedge filter bank targeting crescent sickle boundary angles."""
    def __init__(self, num_angles: int = 8):
        super().__init__()
        self.num_angles = num_angles

    def forward(self, x_fft: torch.Tensor, theta: torch.Tensor, radius: torch.Tensor) -> torch.Tensor:
        step = (2 * np.pi) / self.num_angles
        outs = []
        for i in range(self.num_angles):
            center = i * step
            d = torch.min(torch.abs(theta - center), 2 * np.pi - torch.abs(theta - center))
            angular_mask = torch.exp(-(d**2) / (2 * (step / 2.0)**2))
            radial_mask = (radius > 0.08) & (radius < 0.95)
            wedge = (angular_mask * radial_mask).unsqueeze(0).unsqueeze(0)
            outs.append(torch.fft.ifft2(torch.fft.ifftshift(x_fft * wedge, dim=(-2, -1)), dim=(-2, -1)).real)
        return torch.cat(outs, dim=1)


class CircularHarmonicBlock(nn.Module):
    """Radial concentric ring shells with m=0, 2, 4 harmonic modulations."""
    def __init__(self, num_rings: int = 4):
        super().__init__()
        self.num_rings = num_rings

    def forward(self, x_fft: torch.Tensor, theta: torch.Tensor, radius: torch.Tensor) -> torch.Tensor:
        outs = []
        radii = torch.linspace(0.10, 0.85, self.num_rings + 1, device=x_fft.device)
        for i in range(self.num_rings):
            rc = (radii[i] + radii[i + 1]) / 2.0
            rw = (radii[i + 1] - radii[i]) / 2.0
            ring = torch.exp(-((radius - rc)**2) / (2 * (rw / 1.5)**2)) * ((radius >= 0.08) & (radius <= 0.92))

            # Mode m=0: Pure isotropic circular discocyte symmetry
            outs.append(torch.fft.ifft2(torch.fft.ifftshift(x_fft * ring.unsqueeze(0).unsqueeze(0), dim=(-2, -1)), dim=(-2, -1)).real)

            # Modes m=2, 4: Elliptical and sickle curvature deformation modes
            for m in [2, 4]:
                c_mask = ring * torch.cos(m * theta)
                s_mask = ring * torch.sin(m * theta)
                outs.append(torch.fft.ifft2(torch.fft.ifftshift(x_fft * c_mask.unsqueeze(0).unsqueeze(0), dim=(-2, -1)), dim=(-2, -1)).real)
                outs.append(torch.fft.ifft2(torch.fft.ifftshift(x_fft * s_mask.unsqueeze(0).unsqueeze(0), dim=(-2, -1)), dim=(-2, -1)).real)
        return torch.cat(outs, dim=1)


class CurveCircleNet(nn.Module):
    """Dual-stream gated hybrid architecture for blood smear erythrocyte classification."""
    def __init__(self, num_angles: int = 8, num_rings: int = 4, dropout_rate: float = 0.45, base_ch: int = 32, num_classes: int = 2):
        super().__init__()
        self.curvelet = DirectionalCurveletBlock(num_angles=num_angles)
        self.circle = CircularHarmonicBlock(num_rings=num_rings)

        in_ch_curv = 3 * num_angles
        in_ch_circ = 3 * (num_rings * 5)

        self.curv_stream = nn.Sequential(
            nn.Conv2d(in_ch_curv, base_ch, 1, bias=False),
            nn.BatchNorm2d(base_ch),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Conv2d(base_ch, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1, inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 96, 3, padding=1),
            nn.BatchNorm2d(96),
            nn.LeakyReLU(0.1, inplace=True)
        )

        self.circ_stream = nn.Sequential(
            nn.Conv2d(in_ch_circ, base_ch, 1, bias=False),
            nn.BatchNorm2d(base_ch),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Conv2d(base_ch, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1, inplace=True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 96, 3, padding=1),
            nn.BatchNorm2d(96),
            nn.LeakyReLU(0.1, inplace=True)
        )

        self.fusion_gate = nn.Sequential(
            nn.Conv2d(96 * 2, 64, 1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Conv2d(64, 2, 1),
            nn.Softmax(dim=1)
        )

        self.refine = nn.Sequential(
            nn.Conv2d(96, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.1, inplace=True)
        )

        self.pool_avg = nn.AdaptiveAvgPool2d((1, 1))
        self.pool_max = nn.AdaptiveMaxPool2d((1, 1))

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 2, 64),
            nn.BatchNorm1d(64),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Dropout(dropout_rate),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, h, w = x.shape
        x_fft = torch.fft.fftshift(torch.fft.fft2(x, dim=(-2, -1)), dim=(-2, -1))
        theta, radius = get_polar_grid(h, w, x.device)

        fc = self.curv_stream(self.curvelet(x_fft, theta, radius))
        fr = self.circ_stream(self.circle(x_fft, theta, radius))

        gates = self.fusion_gate(torch.cat([fc, fr], dim=1))
        fused = self.refine(gates[:, 0:1, :, :] * fc + gates[:, 1:2, :, :] * fr)
        return self.classifier(torch.cat([self.pool_avg(fused), self.pool_max(fused)], dim=1))