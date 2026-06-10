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

    var selectedFile = null;
    var lastResult   = null;
    var API_BASE     = window.HELIOSENSE_API_URL || '';
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
      var totalM2  = data.total_roof_area != null ? data.total_roof_area  + ' m²' : '—';
      var usableM2 = data.usable_area     != null ? data.usable_area      + ' m²' : '—';
      var pct = (data.total_roof_area && data.usable_area)
        ? Math.round(data.usable_area / data.total_roof_area * 100) : 0;

      var el;
      el = safeEl('roofAreaValue');      if (el) el.textContent = totalM2;
      el = safeEl('usableAreaValue');    if (el) el.textContent = usableM2;
      el = safeEl('roofAreaProgress');   if (el) el.style.width = '100%';
      el = safeEl('usableAreaProgress'); if (el) el.style.width = pct + '%';
      setShadeRiskBadge(data.shade_risk);
      el = safeEl('placementValue');
      if (el) el.textContent = (data.recommended_capacity_kw || '—') + ' kW · ' + (data.panel_count || '—') + ' panels';
      el = safeEl('pitchValue');
      if (el) el.textContent = (data.suitability_score != null ? data.suitability_score + '/100' : '—');
      el = safeEl('obstructionsValue');
      if (el) el.textContent = data.obstruction_count != null ? data.obstruction_count : '—';

      if (heatmapImg && data.overlay_image) {
        heatmapImg.src = data.overlay_image;
        heatmapImg.alt = 'Solar placement overlay';
      }

      lastResult = data;
      try { localStorage.setItem('rooftopAnalysis', JSON.stringify(data)); } catch (e) {}
      if (downloadBtn) downloadBtn.disabled = false;
    }

    function downloadReport() {
      if (!lastResult) { toast('No analysis available to download'); return; }
      var lines = [
        'Rooftop Analysis Report',
        '-----------------------',
        'Total Roof Area:        ' + (lastResult.total_roof_area || '—') + ' m²',
        'Usable Roof Area:       ' + (lastResult.usable_area     || '—') + ' m²',
        'Suitability Score:      ' + (lastResult.suitability_score != null ? lastResult.suitability_score + '/100' : '—'),
        'Shade Risk:             ' + (lastResult.shade_risk       || '—'),
        'Obstruction Count:      ' + (lastResult.obstruction_count != null ? lastResult.obstruction_count : '—'),
        'Recommended Capacity:   ' + (lastResult.recommended_capacity_kw || '—') + ' kW',
        'Panel Count:            ' + (lastResult.panel_count      || '—'),
        'Analysis Method:        ' + (lastResult.analysis_method  || '—'),
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

        fetch(API_BASE + '/analyze-rooftop', { method: 'POST', body: form })
          .then(function (resp) {
            if (!resp.ok) throw new Error('Server error ' + resp.status);
            return resp.json();
          })
          .then(function (data) {
            if (!data.success) throw new Error(data.error || 'Analysis failed');
            applyResult(data);
            if (fileNameEl) fileNameEl.textContent = selectedFile.name + ' — Analyzed';
            toast('Rooftop analysis complete.');
          })
          .catch(function (err) {
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
  }

  window.initAnalysis = initAnalysis;
})();
