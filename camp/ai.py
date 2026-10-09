"""CurveCircleNet inference + image quality checks for the camp app."""

from __future__ import annotations

import cv2
import numpy as np
import streamlit as st
import torch
import torch.nn.functional as F
from PIL import Image

from models import CurveCircleNet

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MODEL_PATH = "curvecirclenet_sickle_best.pth"


@st.cache_resource
def load_model(model_path: str = MODEL_PATH):
    """Load the trained checkpoint once and share it across pages."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(model_path, map_location=device)
    params = checkpoint.get("hyperparameters", {})
    model = CurveCircleNet(
        num_angles=params.get("num_angles", 8),
        num_rings=params.get("num_rings", 4),
        dropout_rate=params.get("dropout_rate", 0.45),
        base_ch=32,
        num_classes=2,
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    calibrated_threshold = float(params.get("threshold", 0.55))
    return model, str(device), calibrated_threshold


def to_tensor(resized_rgb: np.ndarray, device) -> torch.Tensor:
    """Normalize a 224x224 RGB field exactly as the model was trained."""
    norm = (resized_rgb / 255.0 - MEAN) / STD
    return torch.tensor(norm, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0).to(device)


def predict(pil_image: Image.Image, model: torch.nn.Module, device) -> dict:
    """Run one microscope-field photo through CurveCircleNet."""
    raw = np.array(pil_image.convert("RGB"))
    resized = cv2.resize(raw, (224, 224))
    tensor_input = to_tensor(resized, device)
    with torch.no_grad():
        logits = model(tensor_input)
        probs = F.softmax(logits, dim=1)[0].cpu().numpy()
    return {
        "clear_prob": float(probs[0]),
        "sickle_prob": float(probs[1]),
        "raw": raw,
        "resized": resized,
        "tensor": tensor_input,
    }


def spectrum(resized_img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(resized_img, cv2.COLOR_RGB2GRAY)
    fft = np.fft.fftshift(np.fft.fft2(gray))
    power = 20 * np.log(np.abs(fft) + 1e-8)
    normed = cv2.normalize(power, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.applyColorMap(normed, cv2.COLORMAP_VIRIDIS)


def qc_check(resized_img: np.ndarray) -> dict:
    """Fast field-quality heuristics so volunteers can retake poor photos."""
    gray = cv2.cvtColor(resized_img, cv2.COLOR_RGB2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    warnings: list[str] = []
    if blur < 60:
        warnings.append("Looks out of focus — wipe the lens, hold steady, retake.")
    if brightness < 40:
        warnings.append("Too dark — improve illumination before screening.")
    elif brightness > 220:
        warnings.append("Overexposed — reduce light / exposure and retake.")
    return {
        "blur": round(blur, 1),
        "brightness": round(brightness, 1),
        "ok": not warnings,
        "warnings": warnings,
    }
