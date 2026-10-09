"""Explainable-AI layer for CurveCircleNet.

Two complementary explanations per microscope field:

1. Grad-CAM heatmap on the fused features (``refine`` block) — shows WHERE
   the model looked. Red regions pushed the predicted class most.
2. Fusion-gate evidence mix — the model's own ``fusion_gate`` blends the
   curvelet stream (crescent-edge cues) and the circular stream (healthy
   round-cell symmetry). Their average weights show WHICH kind of evidence
   dominated, as a percentage.
"""

from __future__ import annotations

import cv2
import numpy as np
import torch


def explain_field(
    model: torch.nn.Module, tensor_input: torch.Tensor, target: int | None = None
) -> dict:
    """Run Grad-CAM + gate capture in a single forward/backward pass."""
    model.zero_grad(set_to_none=True)
    captured: dict = {}

    def _save_act(_m, _i, out):
        captured["act"] = out

    def _save_grad(_m, _gi, go):
        captured["grad"] = go[0]

    h_act = model.refine.register_forward_hook(_save_act)
    h_grad = model.refine.register_full_backward_hook(_save_grad)
    h_gate = model.fusion_gate.register_forward_hook(
        lambda _m, _i, out: captured.setdefault("gate", out.detach())
    )
    try:
        logits = model(tensor_input)
        if target is None:
            target = int(logits[0].argmax())
        logits[0, target].backward()
    finally:
        h_act.remove()
        h_grad.remove()
        h_gate.remove()

    act = captured["act"][0].detach()      # C,H,W fused features
    grad = captured["grad"][0].detach()    # C,H,W gradients
    weights = grad.mean(dim=(1, 2))        # global-average-pooled importance
    cam = (weights[:, None, None] * act).sum(dim=0).clamp(min=0)
    cam = cam / (cam.max() + 1e-8)
    cam = cam.cpu().numpy().astype(np.float32)
    cam = cv2.resize(cam, (224, 224))

    gate = captured["gate"][0].detach()    # 2,H,W softmax stream weights
    mix = gate.mean(dim=(1, 2)).cpu().numpy()
    total = float(mix.sum()) or 1.0
    gate_curv, gate_circ = float(mix[0] / total), float(mix[1] / total)

    return {
        "cam": cam,
        "gate_curv": round(gate_curv, 4),
        "gate_circ": round(gate_circ, 4),
        "target": target,
    }


def overlay(raw224: np.ndarray, cam: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Blend a JET heatmap over the 224x224 RGB field (returns RGB)."""
    heat = cv2.applyColorMap((np.clip(cam, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    return cv2.addWeighted(raw224.astype(np.uint8), 1 - alpha, heat_rgb, alpha, 0)


def rationale_text(is_sickle: bool, gate_curv: float, gate_circ: float, margin: float) -> list[str]:
    """Plain-language 'why' for volunteers and medical officers."""
    dominant = (
        "crescent-edge stream" if gate_curv >= gate_circ else "round-symmetry stream"
    )
    points = [
        f"Evidence mix — crescent-edge {gate_curv * 100:.0f}% vs "
        f"round-symmetry {gate_circ * 100:.0f}%. The {dominant} dominated."
    ]
    if is_sickle:
        points.append(
            "Red zones in the overlay hold the curved boundary patterns the model "
            "associates with sickle morphology."
        )
        if margin < 0.15:
            points.append(
                f"Borderline call — only {margin * 100:.1f} points above the threshold. "
                "Confirm with a lab test before acting."
            )
        else:
            points.append(
                f"Clear margin ({margin * 100:.1f} points above threshold) — "
                "still needs lab confirmation per protocol."
            )
    else:
        points.append(
            "No strong crescent-edge evidence; round-cell symmetry dominated "
            "the highlighted regions."
        )
        if margin > -0.15:
            points.append(
                f"Close to the line ({abs(margin) * 100:.1f} points below threshold) — "
                "if symptoms persist, rescreen or refer anyway."
            )
    points.append(
        "The heatmap shows where the model looked, not a diagnosis. Poor focus or "
        "lighting (see quality check) weakens this explanation."
    )
    return points
