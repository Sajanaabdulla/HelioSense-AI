import os
import logging
import base64
import threading
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.abspath(
    os.path.join(BASE_DIR, '..', 'runs', 'detect', 'train-2', 'weights', 'best.pt')
)

# ── Validation thresholds ─────────────────────────────────────────────────────
# Coverage: fraction of image that the largest contour fills.
# < MIN  → too small to be a real rooftop (random object, vehicle, small detail)
# > MAX  → image IS the document — a bill or screenshot fills ~100% of frame
MIN_ROOF_COVERAGE = 0.08
MAX_ROOF_COVERAGE = 0.94

# Solidity = contour area / convex-hull area.
# Rooftops are roughly convex (0.65–0.95); vegetation and torn/irregular edges
# score much lower (0.20–0.50).
MIN_SOLIDITY = 0.50

# Aspect ratio of the minimum-area bounding rectangle.
# Rooftops are compact; values above ~7 indicate a road, field edge, or portrait.
MAX_ASPECT_RATIO = 7.0

# Document/bill/screenshot detection.
# A white page with dark text has: very high brightness, near-grey colour,
# high local contrast (std dev).  All three must be true to trigger rejection.
DOC_BRIGHTNESS_MIN  = 205   # mean V channel (0-255) above this → bright background
DOC_SATURATION_MAX  = 22    # mean S channel below this → near-grey (paper/UI)
DOC_GRAY_STD_MIN    = 65    # std dev of grayscale → high = text contrast

# Vegetation detection.
# Green hue in OpenCV HSV occupies roughly 35-85 / 180.  If more than half the
# detected region is distinctly green, it is most likely a tree canopy or lawn.
GREEN_FRACTION_MAX = 0.52

# ── YOLO inference settings ───────────────────────────────────────────────────
# YOLO model was trained on one class: "solar-panelsS" (class 0).
# It was trained on close-overhead aerial images of buildings, so its activations
# act as a weak confirmation that an image matches rooftop aerial photography.
#
# When YOLO fires with high confidence it is a POSITIVE validation signal;
# zero detections is neutral (bare rooftop expected on most buildings).
# YOLO alone cannot reject non-rooftops — that is handled by geometry + colour.
YOLO_CONF_THRESHOLD    = 0.30   # discard boxes below this confidence
YOLO_OVERLAP_THRESHOLD = 0.20   # min fraction of a YOLO box area that must
                                  # overlap the roof mask; lower → outside-mask
                                  # false positives are dropped

# ── Scene scale ───────────────────────────────────────────────────────────────
SCENE_M2 = 900.0   # assumed 30 m × 30 m for a close-overhead drone / satellite view

_yolo_model     = None
_yolo_attempted = False
_yolo_lock      = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_yolo():
    """Return cached YOLO model, loading once on first call.  Thread-safe."""
    global _yolo_model, _yolo_attempted
    if _yolo_attempted:
        return _yolo_model
    with _yolo_lock:
        if _yolo_attempted:
            return _yolo_model
        _yolo_attempted = True
        try:
            from ultralytics import YOLO
            if os.path.exists(YOLO_MODEL_PATH):
                _yolo_model = YOLO(YOLO_MODEL_PATH)
                logger.info('[rooftop] YOLO loaded: %s', YOLO_MODEL_PATH)
            else:
                logger.warning('[rooftop] YOLO weights not found at %s — OpenCV-only mode',
                               YOLO_MODEL_PATH)
        except Exception as exc:
            logger.warning('[rooftop] YOLO load failed (%s) — OpenCV-only mode', exc)
    return _yolo_model


def _pil_to_bgr(pil_img):
    return cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)


def _get_roof_mask_opencv(bgr):
    """Segment the largest plausible roof region using adaptive threshold + contour.

    Returns
    -------
    mask           : uint8 H×W binary image, 255 inside the detected region
    contour_found  : True when the largest contour exceeds the 4% minimum
    contour_area_px: geometric polygon area (Shoelace formula), 0 if not found
    solidity       : contour_area / convex_hull_area — how convex the shape is
    aspect_ratio   : long-side / short-side of the minimum enclosing rectangle

    The caller uses solidity and aspect_ratio as additional geometry gates to
    separate building rooftops (convex, compact) from vegetation, roads, and
    vehicles (irregular, elongated).
    """
    h, w = bgr.shape[:2]
    gray  = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (9, 9), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 4
    )
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k, iterations=3)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k, iterations=1)

    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask        = np.zeros((h, w), dtype=np.uint8)
    min_area_px = h * w * 0.04   # 4% hard floor — smaller blobs are not rooftops

    if not cnts:
        logger.debug('[rooftop] no contours found')
        return mask, False, 0, 0.0, 0.0

    largest = max(cnts, key=cv2.contourArea)
    area    = cv2.contourArea(largest)

    # Convex hull for solidity
    hull      = cv2.convexHull(largest)
    hull_area = cv2.contourArea(hull)
    solidity  = float(area / hull_area) if hull_area > 0 else 0.0

    # Minimum-area bounding rectangle for aspect ratio
    _, (rw, rh), _ = cv2.minAreaRect(largest)
    long_side  = max(rw, rh)
    short_side = min(rw, rh)
    aspect     = float(long_side / short_side) if short_side > 0 else 999.0

    logger.debug(
        '[rooftop] largest contour: %.0f px (%.1f%%), solidity=%.2f, aspect=%.2f',
        area, area / (h * w) * 100, solidity, aspect,
    )

    if area <= min_area_px:
        logger.debug('[rooftop] contour too small — rejected')
        return mask, False, 0, solidity, aspect

    cv2.drawContours(mask, [largest], -1, 255, cv2.FILLED)
    return mask, True, int(area), solidity, aspect


def _classify_region(bgr, mask):
    """Analyse the colour and texture of the masked region.

    Returns a rejection_reason string when the region does not look like a
    rooftop, or None when it passes all colour/texture checks.

    Checks
    ------
    Document / bill / screenshot
        White background + near-grey colour + high text-contrast.
        All three conditions must be true simultaneously to avoid rejecting
        pale concrete or metal rooftops (which share some but not all traits).

    Vegetation
        Predominantly green-hued pixels (HSV hue 35–85 out of 180, with
        meaningful saturation > 50).  Trees and grass have > 52% green pixels.

    Returns None when the region is plausibly a rooftop.
    """
    roi_count = int(np.sum(mask > 0))
    if roi_count < 100:
        return None   # mask too sparse to classify — let geometry gates decide

    hsv  = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    roi_hsv  = hsv[mask > 0]    # shape (N, 3)
    roi_gray = gray[mask > 0]   # shape (N,)

    mean_brightness = float(np.mean(roi_hsv[:, 2]))
    mean_saturation = float(np.mean(roi_hsv[:, 1]))
    gray_contrast   = float(np.std(roi_gray))

    # ── Document / bill / screenshot ─────────────────────────────────────────
    # All three must be true: bright + grey + high-contrast (from text / UI lines)
    is_doc = (
        mean_brightness > DOC_BRIGHTNESS_MIN and
        mean_saturation < DOC_SATURATION_MAX and
        gray_contrast   > DOC_GRAY_STD_MIN
    )
    if is_doc:
        logger.info(
            '[rooftop] colour check: document detected '
            '(brightness=%.0f, sat=%.0f, contrast=%.0f)',
            mean_brightness, mean_saturation, gray_contrast,
        )
        return (
            'Image appears to be a document, bill, or screenshot — not a rooftop '
            'photograph. Please upload a satellite or aerial image of a building rooftop.'
        )

    # ── Vegetation ───────────────────────────────────────────────────────────
    green_px    = int(np.sum(
        (roi_hsv[:, 0] >= 35) & (roi_hsv[:, 0] <= 85) & (roi_hsv[:, 1] > 50)
    ))
    green_frac  = green_px / roi_count
    if green_frac > GREEN_FRACTION_MAX:
        logger.info(
            '[rooftop] colour check: vegetation detected (green_frac=%.2f)', green_frac
        )
        return (
            f'Image shows predominantly vegetation ({green_frac * 100:.0f}% green pixels). '
            'Please upload a clear overhead view of a building rooftop.'
        )

    logger.debug(
        '[rooftop] colour check passed '
        '(brightness=%.0f, sat=%.0f, contrast=%.0f, green=%.2f)',
        mean_brightness, mean_saturation, gray_contrast, green_frac,
    )
    return None   # region looks like a plausible rooftop


def _detect_obstructions_yolo(bgr):
    """Run YOLO detection with confidence filtering.

    The model detects class 0 ("solar-panelsS") — existing solar panels in
    aerial images.  High-confidence detections confirm the image is a legitimate
    overhead rooftop photograph.  Zero detections is neutral (bare rooftop).

    Returns
    -------
    boxes          : list of (x1, y1, x2, y2) ints, clipped to image bounds
    confs          : list of float confidence scores, parallel to boxes
    yolo_available : True when the model is loaded (even with 0 detections)
    """
    model = _get_yolo()
    if model is None:
        logger.debug('[rooftop] YOLO not available')
        return [], [], False

    try:
        h_img, w_img = bgr.shape[:2]
        results = model(bgr, verbose=False, conf=YOLO_CONF_THRESHOLD)
        boxes, confs = [], []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                # Clip to image bounds so downstream mask slices are always valid
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)
                if x2 > x1 and y2 > y1:
                    boxes.append((x1, y1, x2, y2))
                    confs.append(conf)

        logger.info(
            '[rooftop] YOLO: %d box(es) at conf ≥ %.2f',
            len(boxes), YOLO_CONF_THRESHOLD,
        )
        for i, (b, c) in enumerate(zip(boxes, confs)):
            logger.debug('[rooftop]  box[%d] %s conf=%.3f', i, b, c)
        return boxes, confs, True

    except Exception as exc:
        logger.warning('[rooftop] YOLO inference error: %s', exc)
        return [], [], True


# ─────────────────────────────────────────────────────────────────────────────
# Overlay visualisation
# ─────────────────────────────────────────────────────────────────────────────

def _draw_zone_label(img, green_mask, cap_kw, panels):
    """Annotate the optimal solar placement zone on the overlay image.

    Draws a visible boundary around the green zone contour and places a
    floating label with 'Recommended Solar Zone' plus the capacity and
    panel count derived from the actual analysis.

    All coordinates come from contour moments and bounding-rect of the
    detected green zone — nothing is hardcoded.
    """
    h, w = img.shape[:2]
    cnts, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return

    cv2.drawContours(img, cnts, -1, (255, 255, 255), 3)
    cv2.drawContours(img, cnts, -1, (40,  210,  60), 1)

    largest = max(cnts, key=cv2.contourArea)
    M = cv2.moments(largest)
    if M['m00'] == 0:
        return
    cx = int(M['m10'] / M['m00'])
    cy = int(M['m01'] / M['m00'])
    bx, by, bw_z, bh_z = cv2.boundingRect(largest)

    font  = cv2.FONT_HERSHEY_SIMPLEX
    fs    = max(0.40, min(0.85, min(h, w) / 600))
    thick = 1 if fs < 0.60 else 2
    pad   = max(6, round(fs * 14))

    line1 = 'Recommended Solar Zone'
    line2 = f'{cap_kw} kW  |  {panels} panels'

    (tw1, th1), _ = cv2.getTextSize(line1, font, fs,        thick)
    (tw2, th2), _ = cv2.getTextSize(line2, font, fs * 0.85, thick)
    gap   = th1 // 2 + 4
    box_w = max(tw1, tw2) + pad * 2
    box_h = th1 + gap + th2 + pad * 2

    tx = max(0, min(w - box_w, cx - box_w // 2))
    ty = by - box_h - pad
    if ty < 0:
        ty = by + bh_z + pad
    ty = max(0, min(h - box_h, ty))

    roi = img[ty:ty + box_h, tx:tx + box_w]
    if roi.size == 0:
        return
    img[ty:ty + box_h, tx:tx + box_w] = (roi * 0.22).astype(np.uint8)
    cv2.rectangle(img, (tx, ty), (tx + box_w, ty + box_h), (40, 210, 60), 1)

    y1_base = ty + pad + th1
    y2_base = y1_base + gap + th2
    cv2.putText(img, line1, (tx + pad, y1_base),
                font, fs,        (50, 245,  90), thick, cv2.LINE_AA)
    cv2.putText(img, line2, (tx + pad, y2_base),
                font, fs * 0.85, (200, 240, 210), thick, cv2.LINE_AA)

    label_cx = tx + box_w // 2
    label_cy = ty + box_h if (ty + box_h) <= cy else ty
    cv2.line(img, (label_cx, label_cy), (cx, cy), (200, 255, 200), 1, cv2.LINE_AA)


def _build_overlay(bgr, mask, obs_boxes, cap_kw, panels):
    """Paint placement zones and annotate the optimal zone on a copy of the image.

    Zone colours (distance-transform rings):
      Green  (BGR 30,200,55)  — core, dn > 0.45, best solar placement
      Yellow (BGR 0,200,230)  — middle ring, 0.15 < dn ≤ 0.45, partial suitability
      Red    (BGR 30,50,220)  — edge setback + obstruction halos, unsuitable
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

    layer[green_zone]  = (30, 200,  55)
    layer[yellow_zone] = (0,  200, 230)
    layer[red_zone]    = (30,  50, 220)

    for (x1, y1, x2, y2) in obs_boxes:
        layer[max(0, y1 - 8):min(h, y2 + 8),
              max(0, x1 - 8):min(w, x2 + 8)] = (30, 50, 220)

    colored = np.any(layer > 0, axis=2)
    blended = cv2.addWeighted(result, 0.55, layer, 0.45, 0)
    result[colored] = blended[colored]

    for (x1, y1, x2, y2) in obs_boxes:
        cv2.rectangle(result, (x1, y1), (x2, y2), (0, 40, 220), 2)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(result, cnts, -1, (200, 200, 200), 2)

    green_mask_bin = green_zone.astype(np.uint8) * 255
    _draw_zone_label(result, green_mask_bin, cap_kw, panels)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def _compute_metrics(mask, h, w, obs_boxes, yolo_available, contour_area_px,
                     solidity=1.0, yolo_confs=None):
    """Derive solar planning metrics from the validated roof mask.

    Area methodology
    ----------------
    px_scale = SCENE_M2 / (h × w)  — converts pixel count to m².

    roof_area_m2
        From cv2.contourArea (Shoelace formula), not the rasterised fill.
        Polygon-area avoids per-pixel rounding; capped at 600 m² and a
        clamp_factor propagated to all raster-derived areas so they stay
        proportional, preventing usable_area_m2 > roof_area_m2.

    obstruction_area_m2
        For each YOLO box, only the pixels inside the roof mask are counted
        (np.sum(mask[y1:y2, x1:x2] > 0) × px_scale).  The old full-box-area
        approach over-subtracted when boxes extended beyond the roof edge.

    setback_area_m2
        distanceTransform band where dn ≤ 0.15 (perimeter strip unsuitable
        for panels due to edge effects, water runoff, and building codes).

    usable_area_m2
        inner_m2 − obstruction_area_m2, then shade-derated.
        Hard-clamped to ≤ roof_area_m2 with an error log if that fires.

    Confidence scoring (multi-factor)
    ----------------------------------
    Base     : coverage tiers (45 / 60 / 72 / 82)
    Solidity : contour convexity quality (−10 to +8)
    YOLO     : model available and ran (+8)
    YOLO conf: high mean confidence of in-mask detections (+2 to +5)
    """
    roof_px  = int(np.sum(mask > 0))
    coverage = roof_px / (h * w)
    px_scale = SCENE_M2 / (h * w)   # m² per pixel

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dmax = dist.max()
    dn   = dist / dmax if dmax > 0 else dist

    # ── Roof area (polygon geometry, proportionally clamped) ──────────────────
    unclamped_roof_m2 = float(contour_area_px * px_scale)
    roof_area_m2      = round(float(np.clip(unclamped_roof_m2, 10.0, 600.0)), 1)
    clamp_factor      = (roof_area_m2 / unclamped_roof_m2) if unclamped_roof_m2 > 0 else 1.0

    # ── Setback zone ──────────────────────────────────────────────────────────
    setback_px = int(np.sum((mask > 0) & (dn <= 0.15)))
    setback_m2 = round(setback_px * px_scale * clamp_factor, 1)

    # ── Obstruction footprints: mask-pixel intersection ───────────────────────
    # Count only the roof-mask pixels under each YOLO box.
    # This is more accurate than the full bounding-box area when boxes extend
    # slightly beyond the detected roof boundary.
    obs_px_total = 0
    for (x1, y1, x2, y2) in obs_boxes:
        obs_px_total += int(np.sum(mask[y1:y2, x1:x2] > 0))
    obstruction_area_m2 = round(obs_px_total * px_scale * clamp_factor, 1)

    # ── Suitability score and shade risk ──────────────────────────────────────
    score = min(95, max(30, 82 - len(obs_boxes) * 8))
    shade = 'Low' if score >= 70 else ('Medium' if score >= 50 else 'High')
    shade_deduction = {'Low': 0.00, 'Medium': 0.08, 'High': 0.18}[shade]

    # ── Usable area ───────────────────────────────────────────────────────────
    inner_px       = int(np.sum((mask > 0) & (dn > 0.15)))
    inner_m2       = round(inner_px * px_scale * clamp_factor, 1)
    gross_usable   = max(0.0, inner_m2 - obstruction_area_m2)
    usable_area_m2 = round(max(5.0, gross_usable * (1.0 - shade_deduction)), 1)

    # ── Physical invariant ────────────────────────────────────────────────────
    if usable_area_m2 > roof_area_m2:
        logger.error(
            '[rooftop] invariant violated: usable (%.1f) > roof (%.1f) '
            '— clamp_factor=%.4f, unclamped=%.1f, inner=%.1f, obs=%.1f, shade=%.2f — clamping',
            usable_area_m2, roof_area_m2, clamp_factor,
            unclamped_roof_m2, inner_m2, obstruction_area_m2, shade_deduction,
        )
        usable_area_m2 = roof_area_m2

    # ── System sizing ─────────────────────────────────────────────────────────
    cap_kw = round(usable_area_m2 / 9.0, 1)
    panels = max(1, round(usable_area_m2 / 1.95))
    method = 'YOLO + OpenCV' if yolo_available else 'OpenCV'

    # ── Multi-factor confidence score (0–95) ──────────────────────────────────
    # Factor 1 — roof coverage quality
    if coverage >= 0.25:
        confidence = 82
    elif coverage >= 0.15:
        confidence = 72
    elif coverage >= 0.08:
        confidence = 60
    else:
        confidence = 45

    # Factor 2 — contour solidity: more convex = cleaner measurement
    if solidity >= 0.80:
        confidence = min(95, confidence + 8)
    elif solidity >= 0.65:
        confidence = min(95, confidence + 4)
    elif solidity < 0.50:
        confidence = max(30, confidence - 10)

    # Factor 3 — YOLO model available (better feature confirmation)
    if yolo_available:
        confidence = min(95, confidence + 8)

    # Factor 4 — high-confidence YOLO in-mask detections confirm rooftop context
    if yolo_confs:
        mean_conf = sum(yolo_confs) / len(yolo_confs)
        if mean_conf >= 0.65:
            confidence = min(95, confidence + 5)
        elif mean_conf >= 0.45:
            confidence = min(95, confidence + 2)
        logger.debug(
            '[rooftop] YOLO conf boost: n=%d, mean=%.3f', len(yolo_confs), mean_conf
        )

    logger.info(
        '[rooftop] metrics — roof: %.1f m² (unclamped: %.1f, factor: %.3f), '
        'inner: %.1f m², setback: %.1f m², obs: %.1f m², usable: %.1f m², '
        'shade: %s (ded: %.0f%%), score: %d, coverage: %.1f%%, '
        'solidity: %.2f, yolo: %s, confidence: %d',
        roof_area_m2, unclamped_roof_m2, clamp_factor,
        inner_m2, setback_m2, obstruction_area_m2, usable_area_m2,
        shade, shade_deduction * 100, score, coverage * 100,
        solidity, yolo_available, confidence,
    )

    return {
        'roof_area_m2':            roof_area_m2,
        'usable_area_m2':          usable_area_m2,
        'obstruction_area_m2':     obstruction_area_m2,
        'setback_area_m2':         setback_m2,
        # Legacy keys — frontend continues to work without changes
        'total_roof_area':         roof_area_m2,
        'usable_area':             usable_area_m2,
        'suitability_score':       score,
        'shade_risk':              shade,
        'obstruction_count':       len(obs_boxes),
        'recommended_capacity_kw': cap_kw,
        'panel_count':             panels,
        'analysis_method':         method,
        'confidence':              confidence,
        '_debug': {
            'coverage_pct':          round(coverage * 100, 2),
            'mask_px':               roof_px,
            'contour_px':            contour_area_px,
            'image_px':              h * w,
            'px_scale_m2':           round(px_scale, 8),
            'unclamped_roof_m2':     round(unclamped_roof_m2, 1),
            'clamp_factor':          round(clamp_factor, 4),
            'solidity':              round(solidity, 3),
            'setback_px':            setback_px,
            'inner_px':              inner_px,
            'inner_m2':              inner_m2,
            'obs_px_total':          obs_px_total,
            'obstruction_area_m2':   obstruction_area_m2,
            'shade_deduction_pct':   round(shade_deduction * 100, 0),
            'yolo_available':        yolo_available,
            'yolo_confs':            [round(c, 3) for c in (yolo_confs or [])],
            'yolo_detection_class':  'solar-panelsS',
            'scene_assumed_m2':      SCENE_M2,
            'conf_threshold':        YOLO_CONF_THRESHOLD,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def analyze_rooftop(file_storage):
    """Analyse a rooftop image and return solar planning metrics.

    Validation pipeline (applied in order — first failure returns an error):

    Gate 1 — OpenCV contour
        The image must contain a connected region that covers > 4% of the frame.
        Images with no large planar region (portraits, street scenes, most cars)
        fail here.

    Gate 2 — Coverage bounds (8% – 94%)
        Below 8%: the region is too small to be a usable rooftop in the photo.
        Above 94%: the entire image is one region → document or screenshot.
        Without YOLO the lower bound is raised to 10%.

    Gate 3 — Geometry quality
        Solidity ≥ 0.50 (raised to 0.55 without YOLO): eliminates vegetation,
        torn shapes, and complex scenes with low convexity.
        Aspect ratio ≤ 7.0: eliminates roads, field edges, and portrait-oriented
        building facades.

    Gate 4 — Colour / texture
        Document / bill / screenshot: bright + near-grey + high text contrast.
        Vegetation: > 52% of region pixels are distinctly green-hued.

    Gate 5 — YOLO mask-overlap filter
        YOLO detections with < 20% overlap with the roof mask are discarded as
        false positives (fires outside the detected roof boundary).  This does
        NOT reject the image — zero in-mask detections simply means no existing
        solar installations were found (normal for a bare rooftop).

    Returns
    -------
    On success : dict with roof/usable/obstruction areas, solar metrics, overlay.
    On failure : {'success': False, 'error': '<human-readable reason>',
                  'confidence': 0}
    """
    pil = Image.open(file_storage).convert('RGB')
    bgr = _pil_to_bgr(pil)
    h, w = bgr.shape[:2]
    logger.info('[rooftop] received image %dx%d px', w, h)

    # ── Gate 1 & YOLO: run both in parallel (YOLO first so its result informs
    #    threshold tightening but does not block the geometry checks) ──────────
    all_boxes, all_confs, yolo_available = _detect_obstructions_yolo(bgr)
    mask, contour_found, contour_area_px, solidity, aspect_ratio = _get_roof_mask_opencv(bgr)

    roof_px  = int(np.sum(mask > 0))
    coverage = roof_px / (h * w)

    logger.info(
        '[rooftop] contour=%s, coverage=%.1f%%, solidity=%.2f, aspect=%.2f, '
        'yolo_available=%s, yolo_raw=%d',
        contour_found, coverage * 100, solidity, aspect_ratio,
        yolo_available, len(all_boxes),
    )

    # ── Gate 1: contour found ─────────────────────────────────────────────────
    if not contour_found:
        logger.info('[rooftop] rejected — no roof contour')
        return {
            'success': False,
            'error': (
                'No rooftop detected. Please upload a clear aerial or satellite '
                'image of a building rooftop.'
            ),
            'confidence': 0,
        }

    # ── Gate 2: coverage bounds ───────────────────────────────────────────────
    # Tighten the lower bound when YOLO is unavailable — without AI validation
    # we need a stronger geometric signal.
    min_cov = MIN_ROOF_COVERAGE if yolo_available else max(MIN_ROOF_COVERAGE, 0.10)

    if coverage < min_cov:
        logger.info('[rooftop] rejected — coverage %.1f%% < min %.1f%%',
                    coverage * 100, min_cov * 100)
        return {
            'success': False,
            'error': (
                f'Roof coverage too low ({coverage * 100:.1f}% of image). '
                'Upload a closer overhead view so the rooftop fills more of the frame.'
            ),
            'confidence': 0,
        }

    if coverage > MAX_ROOF_COVERAGE:
        logger.info('[rooftop] rejected — coverage %.1f%% exceeds max %.1f%% (document/screenshot)',
                    coverage * 100, MAX_ROOF_COVERAGE * 100)
        return {
            'success': False,
            'error': (
                'Image appears to be a document, screenshot, or extreme close-up '
                f'({coverage * 100:.0f}% of the frame is a single flat region). '
                'Please upload a satellite or aerial rooftop photograph.'
            ),
            'confidence': 0,
        }

    # ── Gate 3: geometry quality ──────────────────────────────────────────────
    min_sol = MIN_SOLIDITY if yolo_available else max(MIN_SOLIDITY, 0.55)

    if solidity < min_sol:
        logger.info('[rooftop] rejected — solidity %.2f < min %.2f', solidity, min_sol)
        return {
            'success': False,
            'error': (
                f'Detected region is too irregular to be a rooftop '
                f'(shape score {solidity:.2f}, minimum {min_sol:.2f}). '
                'This may be a tree canopy, vehicle, or non-overhead photograph.'
            ),
            'confidence': 0,
        }

    if aspect_ratio > MAX_ASPECT_RATIO:
        logger.info('[rooftop] rejected — aspect ratio %.1f > max %.1f',
                    aspect_ratio, MAX_ASPECT_RATIO)
        return {
            'success': False,
            'error': (
                f'Detected region is too elongated to be a rooftop '
                f'(ratio {aspect_ratio:.1f}:1). '
                'Please upload a direct overhead view of a building.'
            ),
            'confidence': 0,
        }

    # ── Gate 4: colour / texture ──────────────────────────────────────────────
    colour_rejection = _classify_region(bgr, mask)
    if colour_rejection:
        return {'success': False, 'error': colour_rejection, 'confidence': 0}

    # ── Gate 5: YOLO mask-overlap filter ─────────────────────────────────────
    # Discard detections whose pixel footprint does not meaningfully overlap the
    # roof mask.  These are false positives on features outside the roof boundary.
    obs_boxes, obs_confs = [], []
    for (x1, y1, x2, y2), conf in zip(all_boxes, all_confs):
        box_area     = (x2 - x1) * (y2 - y1)
        if box_area == 0:
            continue
        overlap_px   = int(np.sum(mask[y1:y2, x1:x2] > 0))
        overlap_frac = overlap_px / box_area
        if overlap_frac >= YOLO_OVERLAP_THRESHOLD:
            obs_boxes.append((x1, y1, x2, y2))
            obs_confs.append(conf)
        else:
            logger.debug(
                '[rooftop] YOLO box dropped — %.1f%% mask overlap: %s conf=%.3f',
                overlap_frac * 100, (x1, y1, x2, y2), conf,
            )

    if all_boxes and not obs_boxes:
        logger.warning(
            '[rooftop] %d YOLO detection(s) found outside roof mask — '
            'treating as bare rooftop (no on-roof features detected)',
            len(all_boxes),
        )

    logger.info(
        '[rooftop] %d/%d YOLO box(es) accepted (overlap ≥ %.0f%%)',
        len(obs_boxes), len(all_boxes), YOLO_OVERLAP_THRESHOLD * 100,
    )

    # ── Compute metrics → build overlay → return ──────────────────────────────
    metrics = _compute_metrics(
        mask, h, w, obs_boxes, yolo_available, contour_area_px,
        solidity=solidity, yolo_confs=obs_confs,
    )
    overlay = _build_overlay(
        bgr, mask, obs_boxes,
        metrics['recommended_capacity_kw'], metrics['panel_count'],
    )

    _, buf = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 88])
    b64 = base64.b64encode(buf.tobytes()).decode()
    metrics['overlay_image'] = 'data:image/jpeg;base64,' + b64
    metrics['success'] = True
    return metrics
