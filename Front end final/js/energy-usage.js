// Energy Usage page — dedicated module
// Loaded by energy-usage.html; sets window._heliaSenseEnergyModule so main.js
// skips its own initEnergyUsage() call and avoids double event listeners.
(function () {
  'use strict';
  console.log('[energy] energy-usage.js loaded');

  window._heliaSenseEnergyModule = true;

  var API_BASE_URL =
    (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')
      ? 'http://127.0.0.1:5000'
      : 'https://heliosense-ai-1.onrender.com';

  // ── helpers ─────────────────────────────────────────────────────────────────

  function showOcrResult(data) {
    var block = document.getElementById('ocr-result');
    if (!block) return;
    var unitsEl  = document.getElementById('ocr-units');
    var amountEl = document.getElementById('ocr-amount');
    var periodEl = document.getElementById('ocr-period');
    if (unitsEl)  unitsEl.textContent  = data.units_consumed != null ? data.units_consumed + ' kWh' : 'Not detected';
    if (amountEl) amountEl.textContent = data.bill_amount    != null ? '₹' + data.bill_amount.toLocaleString('en-IN') : 'Not detected';
    if (periodEl) periodEl.textContent = data.billing_period || 'Not detected';
    block.style.display = 'block';
  }

  function calculateFromConsumption(kwh, bill) {
    var capacityKw = Math.max(1, Math.ceil(kwh / 120));
    var panels     = Math.ceil(capacityKw * 2);
    var monthlyGen = Math.round(capacityKw * 120);
    var annualGen  = monthlyGen * 12;
    var savings    = bill > 0
      ? Math.round(bill * 12 * 0.6)
      : Math.round(annualGen * 4.2);
    return {
      capacity: capacityKw + ' kW System',
      panels:   panels + ' Panels',
      monthly:  monthlyGen + ' kWh/month',
      annual:   annualGen + ' kWh/year',
      savings:  '₹' + savings.toLocaleString('en-IN') + '/year'
    };
  }

  function showEnergyOutput(data) {
    var map = {
      'val-capacity': data.capacity,
      'val-panels':   data.panels,
      'val-monthly':  data.monthly,
      'val-annual':   data.annual,
      'val-savings':  data.savings
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = map[id];
    });
    document.querySelectorAll('.energy-output-card').forEach(function (card) {
      card.classList.remove('energy-output-card--hidden');
    });
    var out = document.getElementById('energy-output');
    if (out) out.scrollIntoView({ behavior: 'smooth' });
  }

  // ── init ─────────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    console.log('[energy] page loaded');

    var tabs        = document.querySelectorAll('.energy-tab');
    var fileInput   = document.getElementById('bill-file-input');
    var fileName    = document.getElementById('bill-file-name');
    var dropZone    = document.getElementById('bill-drop-zone');
    var chooseBtn   = document.getElementById('choose-bill-btn');
    var uploadBtn   = document.getElementById('upload-bill-btn');
    var analyzeBtn  = document.getElementById('analyze-bill-btn');
    var calculateBtn = document.getElementById('calculate-btn');
    var resetBtn        = document.getElementById('reset-btn');
    var resetUploadBtn  = document.getElementById('reset-upload-btn');
    var kwhInput    = document.getElementById('monthly-kwh');
    var billInput   = document.getElementById('monthly-bill');

    // Startup diagnostics — visible in browser DevTools → Console
    console.log('[energy] tabs found:',        tabs.length);
    console.log('[energy] chooseBtn:',         chooseBtn      ? 'OK' : 'MISSING');
    console.log('[energy] uploadBtn:',         uploadBtn      ? 'OK' : 'MISSING');
    console.log('[energy] analyzeBtn:',        analyzeBtn     ? 'OK' : 'MISSING');
    console.log('[energy] calculateBtn:',      calculateBtn   ? 'OK' : 'MISSING');
    console.log('[energy] resetBtn:',          resetBtn       ? 'OK' : 'MISSING');
    console.log('[energy] resetUploadBtn:',    resetUploadBtn ? 'OK' : 'MISSING');
    console.log('[energy] fileInput:',         fileInput      ? 'OK' : 'MISSING');

    var toast = window.showToast || function (msg, t) {
      try {
        var d = document.createElement('div');
        d.className = 'toast';
        d.textContent = msg;
        document.body.appendChild(d);
        setTimeout(function () { try { d.remove(); } catch (e) {} }, t || 3000);
      } catch (e) {}
    };

    var _ocrData = null;

    // ── Tab switching ──────────────────────────────────────────────────────────
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('energy-tab--active'); });
        tab.classList.add('energy-tab--active');
        document.querySelectorAll('.energy-panel').forEach(function (p) {
          p.classList.remove('energy-panel--active');
        });
        var panel = document.getElementById('panel-' + tab.getAttribute('data-tab'));
        if (panel) panel.classList.add('energy-panel--active');
      });
    });

    // ── File selection ─────────────────────────────────────────────────────────
    function setFile(file) {
      if (!file) return;
      if (fileName) fileName.textContent = file.name;
      toast('File selected — click Upload Bill to send it to the server.');
    }

    // Choose Bill → open file picker
    if (chooseBtn && fileInput) {
      chooseBtn.addEventListener('click', function () {
        console.log('[energy] choose clicked');
        fileInput.click();
      });
      console.log('[energy] chooseBtn listener attached');
    }

    if (fileInput) {
      fileInput.addEventListener('change', function (e) {
        var file = e.target.files && e.target.files[0];
        console.log('[energy] file selected:', file ? file.name : 'none');
        setFile(file);
      });
    }

    // Drop zone
    if (dropZone && fileInput) {
      dropZone.addEventListener('click', function () { fileInput.click(); });
      dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('bill-upload-zone--active');
      });
      dropZone.addEventListener('dragleave', function () {
        dropZone.classList.remove('bill-upload-zone--active');
      });
      dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('bill-upload-zone--active');
        var file = e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) {
          try { fileInput.files = e.dataTransfer.files; } catch (ex) {}
          setFile(file);
        }
      });
    }

    // ── Upload Bill ────────────────────────────────────────────────────────────
    if (uploadBtn) {
      uploadBtn.addEventListener('click', function () {
        console.log('[energy] upload clicked');
        if (!fileInput || !fileInput.files[0]) {
          toast('Please choose a bill file first.', 4000);
          return;
        }
        var orig = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<span class="spinner-inline"></span> Uploading...';
        uploadBtn.disabled = true;
        _ocrData = null;

        var formData = new FormData();
        formData.append('bill', fileInput.files[0]);

        console.log('[energy] POST', API_BASE_URL + '/upload-bill');
        fetch(API_BASE_URL + '/upload-bill', { method: 'POST', body: formData })
          .then(function (resp) {
            if (!resp.ok) throw new Error('Server error ' + resp.status);
            return resp.json();
          })
          .then(function (data) {
            if (data.success) {
              if (data.ocr_status === 'demo') {
                var DEMO_BILLS = [
                  { units_consumed: 150, bill_amount: 1200, billing_period: 'Monthly' },
                  { units_consumed: 250, bill_amount: 2000, billing_period: 'Monthly' },
                  { units_consumed: 350, bill_amount: 3000, billing_period: 'Monthly' },
                  { units_consumed: 500, bill_amount: 4200, billing_period: 'Monthly' },
                  { units_consumed: 700, bill_amount: 6000, billing_period: 'Monthly' }
                ];
                var currentIdx = parseInt(localStorage.getItem('demoBillIndex') || '0') % DEMO_BILLS.length;
                localStorage.setItem('demoBillIndex', String((currentIdx + 1) % DEMO_BILLS.length));
                var demo = DEMO_BILLS[currentIdx];
                data.units_consumed = demo.units_consumed;
                data.bill_amount    = demo.bill_amount;
                data.billing_period = demo.billing_period;
                console.log('[energy] Demo Bill ' + (currentIdx + 1) + ' loaded');
              } else {
                console.log('[energy] OCR success');
              }

              _ocrData = data;
              if (fileName) fileName.textContent = fileInput.files[0].name + ' — Processed';
              showOcrResult(data);
              toast('KSEB bill processed successfully. Click Analyze Bill for recommendations.', 4000);
            } else {
              if (fileName) fileName.textContent = 'Processing failed';
              toast('Could not process bill. Please try again.', 5000);
            }
          })
          .catch(function (err) {
            console.error('[energy] upload error:', err);
            if (fileName) fileName.textContent = 'Upload error';
            toast('Upload error: ' + err.message, 5000);
          })
          .finally(function () {
            uploadBtn.innerHTML = orig;
            uploadBtn.disabled = false;
          });
      });
      console.log('[energy] uploadBtn listener attached');
    }

    // ── Analyze Bill ───────────────────────────────────────────────────────────
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', function () {
        console.log('[energy] analyze clicked');
        if (!_ocrData) {
          toast('Please upload a bill first.', 4000);
          return;
        }
        var kwh  = _ocrData.units_consumed || 0;
        var bill = _ocrData.bill_amount    || 0;
        if (kwh <= 0) {
          toast('Could not extract usage from bill. Please use Manual Entry instead.', 5000);
          return;
        }
        showEnergyOutput(calculateFromConsumption(kwh, bill));
        toast('Recommendation calculated from your bill data.');
      });
      console.log('[energy] analyzeBtn listener attached');
    }

    // ── Calculate (manual entry) ───────────────────────────────────────────────
    if (calculateBtn) {
      calculateBtn.addEventListener('click', function () {
        console.log('[energy] calculate clicked');
        var kwh  = parseFloat(kwhInput  ? kwhInput.value  : '') || 0;
        var bill = parseFloat(billInput ? billInput.value : '') || 0;
        if (kwh <= 0) {
          toast('Please enter your monthly kWh consumption first.', 4000);
          if (kwhInput) kwhInput.focus();
          return;
        }
        showEnergyOutput(calculateFromConsumption(kwh, bill));
        toast('Solar recommendation calculated.');
      });
      console.log('[energy] calculateBtn listener attached');
    }

    // ── Reset (Manual Entry) ──────────────────────────────────────────────────
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        console.log('[energy] reset clicked');
        if (kwhInput)  kwhInput.value  = '';
        if (billInput) billInput.value = '';
        document.querySelectorAll('.energy-output-card').forEach(function (card) {
          card.classList.add('energy-output-card--hidden');
        });
      });
      console.log('[energy] resetBtn listener attached');
    }

    // ── Reset Upload (KSEB Bill Upload section only) ──────────────────────────
    if (resetUploadBtn) {
      resetUploadBtn.addEventListener('click', function () {
        console.log('[energy] reset-upload clicked');
        _ocrData = null;
        if (fileInput)  fileInput.value = '';
        if (fileName)   fileName.textContent = 'No file selected';
        var ocrBlock = document.getElementById('ocr-result');
        if (ocrBlock)   ocrBlock.style.display = 'none';
        document.querySelectorAll('.energy-output-card').forEach(function (card) {
          card.classList.add('energy-output-card--hidden');
        });
        toast('Energy usage analysis reset successfully.', 3000);
      });
      console.log('[energy] resetUploadBtn listener attached');
    }
  });
})();
