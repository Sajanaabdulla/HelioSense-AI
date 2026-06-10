import os
import base64
import threading
import numpy as np
import cv2
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.abspath(
    os.path.join(BASE_DIR, '..', 'runs', 'detect', 'train-2', 'weights', 'best.pt')
)

# Lazy-loaded on first /analyze-rooftop request; None if unavailable.
_yolo_model = None
_yolo_attempted = False
_yolo_lock = threading.Lock()


def _get_yolo():
    """Return the cached YOLO model, loading it on the first call.

    Never called at import time — only from _detect_obstructions_yolo(),
    which is only called from analyze_rooftop(), which is only called from
    the /analyze-rooftop endpoint. The lock prevents a double-load race
    when two requests arrive simultaneously before the first load finishes.
    """
    global _yolo_model, _yolo_attempted
    if _yolo_attempted:
        return _yolo_model
    with _yolo_lock:
        if _yolo_attempted:          # re-check after acquiring lock
            return _yolo_model
        _yolo_attempted = True
        try:
            from ultralytics import YOLO
            if os.path.exists(YOLO_MODEL_PATH):
                _yolo_model = YOLO(YOLO_MODEL_PATH)
        except Exception:
            pass                     # falls back to OpenCV-only analysis
    return _yolo_model


def _pil_to_bgr(pil_img):
    return cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)


def _get_roof_mask_opencv(bgr):
    """Segment the roof region via adaptive threshold + largest contour."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 4
    )
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k, iterations=3)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k, iterations=1)

    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros((h, w), dtype=np.uint8)

    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(largest) > h * w * 0.04:
            cv2.drawContours(mask, [largest], -1, 255, cv2.FILLED)
        else:
            _fill_center_rect(mask, h, w)
    else:
        _fill_center_rect(mask, h, w)

    return mask


def _fill_center_rect(mask, h, w, pad=0.12):
    cv2.rectangle(
        mask,
        (int(w * pad),       int(h * pad)),
        (int(w * (1 - pad)), int(h * (1 - pad))),
        255, cv2.FILLED
    )


def _detect_obstructions_yolo(bgr):
    """
    Run YOLO detection. Returns (boxes, yolo_available).
    boxes is a list of (x1, y1, x2, y2) ints.
    """
    model = _get_yolo()
    if model is None:
        return [], False
    try:
        results = model(bgr, verbose=False)
        boxes = []
        for r in results:
            if r.boxes is not None:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    boxes.append((x1, y1, x2, y2))
        return boxes, True
    except Exception:
        return [], True


def _build_overlay(bgr, mask, obs_boxes):
    """
    Paint placement zones onto a copy of the image:
      Green  — best solar placement (inner roof core)
      Yellow — partially suitable (middle ring)
      Red    — unsuitable (edge strip + obstructions)
    """
    h, w = bgr.shape[:2]
    result = bgr.copy()
    layer  = np.zeros_like(bgr)

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dmax = dist.max()
    dn   = dist / dmax if dmax > 0 else dist

    green_zone  = (mask > 0) & (dn > 0.45)
    yellow_zone = (mask > 0) & (dn > 0.15) & (dn <= 0.45)
    red_zone    = (mask > 0) & (dn <= 0.15)

    layer[green_zone]  = (30,  200,  55)   # BGR green
    layer[yellow_zone] = (0,   200, 230)   # BGR yellow
    layer[red_zone]    = (30,   50, 220)   # BGR red

    # Expand obstruction boxes to red
    for (x1, y1, x2, y2) in obs_boxes:
        px1 = max(0, x1 - 8); py1 = max(0, y1 - 8)
        px2 = min(w, x2 + 8); py2 = min(h, y2 + 8)
        layer[py1:py2, px1:px2] = (30, 50, 220)

    # Blend
    colored = np.any(layer > 0, axis=2)
    blended = cv2.addWeighted(result, 0.55, layer, 0.45, 0)
    result[colored] = blended[colored]

    # Obstruction box outlines
    for (x1, y1, x2, y2) in obs_boxes:
        cv2.rectangle(result, (x1, y1), (x2, y2), (0, 40, 220), 2)

    # Roof perimeter outline
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(result, cnts, -1, (200, 200, 200), 2)

    return result


def _compute_metrics(mask, h, w, obs_boxes, yolo_available):
    roof_px   = int(np.sum(mask > 0))
    fraction  = roof_px / (h * w)

    # Scene ~400 m² for a close-up single-building image; scale by fraction
    total_m2 = max(20, min(500, round(fraction * 1000)))

    usable_frac = max(0.40, min(0.85, 0.75 - len(obs_boxes) * 0.05))
    usable_m2   = max(10, round(total_m2 * usable_frac))

    score = min(95, max(30, 82 - len(obs_boxes) * 8))
    shade = 'Low' if score >= 70 else ('Medium' if score >= 50 else 'High')

    cap_kw  = round(usable_m2 / 9.0, 1)
    panels  = max(1, round(usable_m2 / 1.95))
    method  = 'YOLO + OpenCV' if yolo_available else 'OpenCV'

    return {
        'total_roof_area':       total_m2,
        'usable_area':           usable_m2,
        'suitability_score':     score,
        'shade_risk':            shade,
        'obstruction_count':     len(obs_boxes),
        'recommended_capacity_kw': cap_kw,
        'panel_count':           panels,
        'analysis_method':       method,
    }


def analyze_rooftop(file_storage):
    """
    Main entry point called from the Flask endpoint.
    Returns a dict with analysis metrics and a base64 overlay image.
    """
    pil = Image.open(file_storage).convert('RGB')
    bgr = _pil_to_bgr(pil)
    h, w = bgr.shape[:2]

    obs_boxes, yolo_available = _detect_obstructions_yolo(bgr)
    mask    = _get_roof_mask_opencv(bgr)
    overlay = _build_overlay(bgr, mask, obs_boxes)
    metrics = _compute_metrics(mask, h, w, obs_boxes, yolo_available)

    _, buf = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 88])
    b64 = base64.b64encode(buf.tobytes()).decode()
    metrics['overlay_image'] = 'data:image/jpeg;base64,' + b64
    metrics['success'] = True

    return metrics
