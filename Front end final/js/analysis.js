// Analysis page — real rooftop analysis via /analyze-rooftop
(function () {
  'use strict';

  function initAnalysis() {
    var detectBtn     = document.getElementById('detectLocationBtn');
    var uploadBtn     = document.getElementById('upload-btn');
    var analyzeBtn    = document.getElementById('analyze-btn');
    var downloadBtn   = document.getElementById('download-btn');
    var fileInput     = document.getElementById('file-input');
    var fileNameEl    = document.getElementById('file-name');
    var locationResult = document.getElementById('locationResult');
    var dropZone      = document.getElementById('drop-zone');
    var heatmapImg    = document.querySelector('.heatmap img');
    var origPreview   = document.getElementById('original-preview');
    var dropContent   = dropZone ? dropZone.querySelector('.relative.z-10') : null;

    var selectedFile  = null;
    var lastResult    = null;
    var heatmapZoom   = 1.0;
    var heatmapThumb  = document.getElementById('heatmap-thumb');
    var heatmapModal  = document.getElementById('heatmap-modal');
    var heatmapMImg   = document.getElementById('heatmap-modal-img');
    var API_BASE =
      (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost")
        ? "http://127.0.0.1:5000"
        : "https://heliosense-ai-1.onrender.com";
    console.log('[HelioSense] Rooftop analysis — API base:', API_BASE || '(relative — served by Flask)');
    var toast = window.showToast || function (msg, t) {
      try {
        var d = document.createElement('div');
        d.className = 'toast'; d.textContent = msg;
        document.body.appendChild(d);
        setTimeout(function () { try { d.remove(); } catch (e) {} }, t || 3000);
      } catch (e) {}
    };

    // ── helpers ────────────────────────────────────────────────────────────
    function safeEl(id) { return document.getElementById(id); }

    function setShadeRiskBadge(risk) {
      var el = safeEl('shadeRiskValue');
      if (!el) return;
      el.textContent = risk || '—';
      var cls = risk === 'Low' ? 'badge--success'
               : risk === 'Medium' ? 'badge--warning'
               : 'badge--error';
      el.className = 'badge ' + cls;
    }

    function applyResult(data) {
      // Prefer the explicit field names; fall back to legacy keys for older responses
      var roofM2val   = data.roof_area_m2   != null ? data.roof_area_m2   : data.total_roof_area;
      var usableM2val = data.usable_area_m2 != null ? data.usable_area_m2 : data.usable_area;
      var obsM2val    = data.obstruction_area_m2 != null ? data.obstruction_area_m2 : null;

      var totalM2  = roofM2val   != null ? roofM2val   + ' m²' : '—';
      var usableM2 = usableM2val != null ? usableM2val + ' m²' : '—';
      var pct = (roofM2val && usableM2val)
        ? Math.round(usableM2val / roofM2val * 100) : 0;

      var el;
      el = safeEl('roofAreaValue');      if (el) el.textContent = totalM2;
      el = safeEl('usableAreaValue');    if (el) el.textContent = usableM2;
      el = safeEl('roofAreaProgress');   if (el) el.style.width = '100%';
      el = safeEl('usableAreaProgress'); if (el) el.style.width = pct + '%';
      setShadeRiskBadge(data.shade_risk);
      el = safeEl('placementValue');
      if (el) el.textContent = (data.recommended_capacity_kw || '—') + ' kW · ' + (data.panel_count || '—') + ' panels';
      el = safeEl('pitchValue');
      if (el) el.textContent = data.confidence != null ? data.confidence + '%' : '—';
      el = safeEl('obstructionsValue');
      if (el) {
        var obsText = data.obstruction_count != null ? data.obstruction_count + ' detected' : '—';
        if (obsM2val != null) obsText += ' (' + obsM2val + ' m²)';
        el.textContent = obsText;
      }

      var overlayImg = document.getElementById('heatmap-img') || heatmapImg;
      if (overlayImg && data.overlay_image) {
        overlayImg.src = data.overlay_image;
        overlayImg.alt = 'Solar placement overlay';
      }
      if (heatmapMImg && data.overlay_image) {
        heatmapMImg.src = data.overlay_image;
      }

      if (data._debug) {
        console.log('[HelioSense] Detection debug:', data._debug);
      }

      lastResult = data;
      try { localStorage.setItem('rooftopAnalysis', JSON.stringify(data)); } catch (e) {}
      if (downloadBtn) downloadBtn.disabled = false;
    }

    function downloadReport() {
      if (!lastResult) { toast('No analysis available to download'); return; }
      var roofVal   = lastResult.roof_area_m2   != null ? lastResult.roof_area_m2   : lastResult.total_roof_area;
      var usableVal = lastResult.usable_area_m2 != null ? lastResult.usable_area_m2 : lastResult.usable_area;
      var lines = [
        'Rooftop Analysis Report',
        '-----------------------',
        'Total Roof Area:        ' + (roofVal   || '—') + ' m²  (estimated)',
        'Usable Roof Area:       ' + (usableVal || '—') + ' m²  (estimated)',
        'Setback Area:           ' + (lastResult.setback_area_m2       != null ? lastResult.setback_area_m2       + ' m²' : '—'),
        'Obstruction Area:       ' + (lastResult.obstruction_area_m2   != null ? lastResult.obstruction_area_m2   + ' m²' : '—'),
        'Suitability Score:      ' + (lastResult.suitability_score     != null ? lastResult.suitability_score     + '/100' : '—'),
        'Confidence:             ' + (lastResult.confidence            != null ? lastResult.confidence            + '%'    : '—'),
        'Shade Risk:             ' + (lastResult.shade_risk            || '—'),
        'Obstruction Count:      ' + (lastResult.obstruction_count     != null ? lastResult.obstruction_count     : '—'),
        'Recommended Capacity:   ' + (lastResult.recommended_capacity_kw || '—') + ' kW',
        'Panel Count:            ' + (lastResult.panel_count           || '—'),
        'Analysis Method:        ' + (lastResult.analysis_method       || '—'),
      ];
      var blob = new Blob([lines.join('\n')], { type: 'text/plain' });
      var url  = URL.createObjectURL(blob);
      var a    = document.createElement('a');
      a.href = url; a.download = 'rooftop_analysis.txt';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast('Analysis results downloaded.');
    }

    // ── file selection ──────────────────────────────────────────────────────
    function handleFile(f) {
      if (!f) return;
      if (['image/jpeg', 'image/png', 'image/jpg'].indexOf(f.type) === -1) {
        toast('Please select a JPG or PNG image'); return;
      }
      selectedFile = f;
      if (fileNameEl) fileNameEl.textContent = f.name;

      var previewUrl = URL.createObjectURL(f);
      if (origPreview) {
        origPreview.src = previewUrl;
        origPreview.style.display = 'block';
      }
      if (dropContent) dropContent.style.visibility = 'hidden';
      toast('Image loaded — click Analyze Rooftop');
    }

    if (uploadBtn && fileInput) {
      uploadBtn.addEventListener('click', function () { fileInput.click(); });
      fileInput.addEventListener('change', function (e) {
        handleFile(e.target.files && e.target.files[0]);
      });
    }

    // ── drag & drop ─────────────────────────────────────────────────────────
    if (dropZone && fileInput) {
      dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('drop-zone--active');
      });
      dropZone.addEventListener('dragleave', function () {
        dropZone.classList.remove('drop-zone--active');
      });
      dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('drop-zone--active');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          fileInput.files = e.dataTransfer.files;
          handleFile(e.dataTransfer.files[0]);
        }
      });
    }

    // ── detect location ─────────────────────────────────────────────────────
    if (detectBtn) {
      detectBtn.addEventListener('click', function () {
        detectBtn.disabled = true;
        detectBtn.innerHTML = '<span class="spinner-inline"></span> Detecting...';
        if (!navigator.geolocation) {
          toast('Geolocation not supported');
          detectBtn.disabled = false;
          detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
          return;
        }
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude.toFixed(6);
            var lng = pos.coords.longitude.toFixed(6);
            if (locationResult) locationResult.textContent = 'Location: ' + lat + ', ' + lng;
            toast('Location detected');
            detectBtn.disabled = false;
            detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
          },
          function () {
            toast('Unable to detect location');
            detectBtn.disabled = false;
            detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
          },
          { timeout: 10000, enableHighAccuracy: true }
        );
      });
    }

    // ── analyze ──────────────────────────────────────────────────────────────
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', function () {
        if (!selectedFile) { toast('Please upload a rooftop image first'); return; }
        analyzeBtn.disabled = true;
        var orig = analyzeBtn.innerHTML;
        analyzeBtn.innerHTML = '<span class="spinner-inline"></span> Analyzing...';

        var form = new FormData();
        form.append('image', selectedFile);

        var endpoint = API_BASE + '/analyze-rooftop';
        console.log('[HelioSense] POST', endpoint);
        fetch(endpoint, { method: 'POST', body: form })
          .then(function (resp) {
            var ct = resp.headers.get('content-type') || '';
            if (!resp.ok) {
              if (ct.indexOf('application/json') !== -1) {
                return resp.json().then(function (errData) {
                  throw new Error('HTTP ' + resp.status + ': ' + (errData.error || resp.statusText));
                });
              }
              return resp.text().then(function (body) {
                throw new Error('HTTP ' + resp.status + ' ' + resp.statusText +
                  (body ? ' — ' + body.slice(0, 200) : ''));
              });
            }
            if (ct.indexOf('application/json') === -1) {
              return resp.text().then(function (body) {
                throw new Error('Expected JSON but got "' + ct + '". Is the request hitting Flask? Response: ' + body.slice(0, 200));
              });
            }
            return resp.json();
          })
          .then(function (data) {
            if (!data.success) throw new Error(data.error || 'Analysis failed');
            applyResult(data);
            if (fileNameEl) fileNameEl.textContent = selectedFile.name + ' — Analyzed';
            toast('Rooftop analysis complete.');
          })
          .catch(function (err) {
            console.error('[HelioSense] Rooftop analysis error:', err);
            toast('Analysis failed: ' + err.message, 6000);
          })
          .finally(function () {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = orig;
          });
      });
    }

    // ── download ─────────────────────────────────────────────────────────────
    if (downloadBtn) {
      downloadBtn.addEventListener('click', function (e) {
        e.preventDefault();
        downloadReport();
      });
      downloadBtn.disabled = true;
    }

    // ── heatmap fullscreen modal ──────────────────────────────────────────────
    function openHeatmapModal() {
      if (!heatmapModal) return;
      heatmapZoom = 1.0;
      if (heatmapMImg) heatmapMImg.style.transform = 'scale(1)';
      heatmapModal.style.display = 'flex';
    }
    function closeHeatmapModal() {
      if (heatmapModal) heatmapModal.style.display = 'none';
    }
    function applyZoom() {
      if (heatmapMImg) heatmapMImg.style.transform = 'scale(' + heatmapZoom + ')';
    }

    if (heatmapThumb) {
      heatmapThumb.addEventListener('click', openHeatmapModal);
    }
    var mClose = document.getElementById('heatmap-modal-close');
    if (mClose) mClose.addEventListener('click', closeHeatmapModal);

    if (heatmapModal) {
      heatmapModal.addEventListener('click', function (e) {
        if (e.target === heatmapModal) closeHeatmapModal();
      });
    }

    var zoomIn = document.getElementById('heatmap-zoom-in');
    var zoomOut = document.getElementById('heatmap-zoom-out');
    var zoomReset = document.getElementById('heatmap-zoom-reset');
    if (zoomIn)    zoomIn.addEventListener('click',    function () { heatmapZoom = Math.min(5, heatmapZoom + 0.25); applyZoom(); });
    if (zoomOut)   zoomOut.addEventListener('click',   function () { heatmapZoom = Math.max(0.5, heatmapZoom - 0.25); applyZoom(); });
    if (zoomReset) zoomReset.addEventListener('click', function () { heatmapZoom = 1.0; applyZoom(); });
  }

  window.initAnalysis = initAnalysis;
})();
