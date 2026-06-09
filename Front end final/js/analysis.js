// Analysis page behavior: detect location, upload image, analyze demo, download
(function(){
  'use strict';
  function initAnalysis(){
    var detectBtn = document.getElementById('detectLocationBtn');
    var uploadBtn = document.getElementById('upload-btn');
    var analyzeBtn = document.getElementById('analyze-btn');
    var downloadBtn = document.getElementById('download-btn');
    var fileInput = document.getElementById('file-input');
    var fileNameEl = document.getElementById('file-name');
    var locationResult = document.getElementById('locationResult');
    var dropZone = document.getElementById('drop-zone');
    var heatmapImg = document.querySelector('.heatmap img');

    var selectedFile = null;
    var analysisDone = false;
    var toast = window.showToast || function(msg, timeout){ try{ var t=document.createElement('div'); t.className='toast'; t.textContent=msg; document.body.appendChild(t); setTimeout(function(){ try{ t.remove(); }catch(e){} }, timeout||3000);}catch(e){console.warn('toast',e);} };
    var demo = {
      roofArea: '148 m²',
      usableArea: '121 m²',
      shadeRisk: '8%',
      placement: 'South-West Facing Section',
      pitch: '22°',
      obstructions: '2'
    };

    function safeEl(id){ return document.getElementById(id); }

    function applyDemo(){
      var roofAreaValue = safeEl('roofAreaValue');
      var usableAreaValue = safeEl('usableAreaValue');
      var roofAreaProgress = safeEl('roofAreaProgress');
      var usableAreaProgress = safeEl('usableAreaProgress');
      var shadeRiskValue = safeEl('shadeRiskValue');
      var placementValue = safeEl('placementValue');
      var pitchValue = safeEl('pitchValue');
      var obstructionsValue = safeEl('obstructionsValue');

      if (roofAreaValue) roofAreaValue.textContent = demo.roofArea;
      if (usableAreaValue) usableAreaValue.textContent = demo.usableArea;
      if (roofAreaProgress) roofAreaProgress.style.width = '100%';
      if (usableAreaProgress) {
        // usable percent = 121/148 ~ 82%
        usableAreaProgress.style.width = '82%';
      }
      if (shadeRiskValue) shadeRiskValue.textContent = demo.shadeRisk;
      if (placementValue) placementValue.textContent = demo.placement;
      if (pitchValue) pitchValue.textContent = demo.pitch;
      if (obstructionsValue) obstructionsValue.textContent = demo.obstructions;

      analysisDone = true;
    }

    function downloadReport(){
      var lines = [];
      lines.push('Rooftop Analysis Report');
      lines.push('-----------------------');
      lines.push('Roof Area: ' + demo.roofArea);
      lines.push('Usable Area: ' + demo.usableArea);
      lines.push('Best Placement: ' + demo.placement);
      lines.push('Shade Risk: ' + demo.shadeRisk);
      lines.push('Average Pitch: ' + demo.pitch);
      lines.push('Obstructions: ' + demo.obstructions);
      var blob = new Blob([lines.join('\n')], { type: 'text/plain' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = 'rooftop_analysis.txt'; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast('Analysis results downloaded.');
    }

    if (detectBtn){
      detectBtn.addEventListener('click', function(){
        detectBtn.disabled = true; detectBtn.innerHTML = '<span class="spinner-inline"></span> Detecting...';
        if (!navigator.geolocation){
          console.warn('Geolocation not supported');
          toast('Geolocation not supported');
          detectBtn.disabled = false; detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
          return;
        }
        navigator.geolocation.getCurrentPosition(function(pos){
          var lat = pos.coords.latitude.toFixed(6); var lng = pos.coords.longitude.toFixed(6);
          if (locationResult) locationResult.textContent = 'Location: ' + lat + ', ' + lng;
          toast('Location detected');
          detectBtn.disabled = false; detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
        }, function(err){
          console.error('Geolocation error', err);
          toast('Unable to detect location');
          detectBtn.disabled = false; detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
        }, { timeout: 10000, enableHighAccuracy: true });
      });
    }

    if (uploadBtn && fileInput){
      uploadBtn.addEventListener('click', function(){ fileInput.click(); });
      fileInput.addEventListener('change', function(e){
        var f = e.target.files && e.target.files[0];
        if (!f) return;
        var valid = ['image/jpeg','image/png','image/jpg'];
        if (valid.indexOf(f.type) === -1){ toast('Please select a JPG or PNG image'); fileInput.value = ''; return; }
        selectedFile = f;
        if (fileNameEl) fileNameEl.textContent = f.name;
        if (heatmapImg){ try{ heatmapImg.src = URL.createObjectURL(f); } catch(e){ console.warn(e); } }
        toast('Image loaded');
      });
    }

    // drag & drop
    if (dropZone && fileInput){
      dropZone.addEventListener('dragover', function(e){ e.preventDefault(); dropZone.classList.add('drop-zone--active'); });
      dropZone.addEventListener('dragleave', function(){ dropZone.classList.remove('drop-zone--active'); });
      dropZone.addEventListener('drop', function(e){
        e.preventDefault(); dropZone.classList.remove('drop-zone--active');
        if (e.dataTransfer.files && e.dataTransfer.files[0]){
          fileInput.files = e.dataTransfer.files; var evt = new Event('change'); fileInput.dispatchEvent(evt);
        }
      });
    }

    if (analyzeBtn){
      analyzeBtn.addEventListener('click', function(e){
        e.preventDefault();
        if (!selectedFile){ toast('Please upload a rooftop image before analysis'); return; }
        analyzeBtn.disabled = true; var orig = analyzeBtn.innerHTML; analyzeBtn.innerHTML = '<span class="spinner-inline"></span> Analyzing...';
        setTimeout(function(){
          applyDemo();
          analyzeBtn.disabled = false; analyzeBtn.innerHTML = orig; if (fileNameEl) fileNameEl.textContent = (selectedFile && selectedFile.name) + ' — Analyzed';
          if (downloadBtn) downloadBtn.disabled = false;
          toast('Rooftop analysis complete.');
        }, 2000);
      });
    }

    if (downloadBtn){
      downloadBtn.addEventListener('click', function(e){ e.preventDefault(); if (!analysisDone){ toast('No analysis available to download'); return; } downloadReport(); });
      downloadBtn.disabled = true;
    }
  }

  // expose to global so init call works
  window.initAnalysis = initAnalysis;
})();
