document.addEventListener("DOMContentLoaded", function () {
  // ROI elements
  const installationCostEl = document.getElementById("installationCost");
  const roiPercentageEl = document.getElementById("roiPercentage");
  const annualSavingsEl = document.getElementById("annualSavings");
  const paybackPeriodEl = document.getElementById("paybackPeriod");
  const investmentRecoveryEl = document.getElementById("investmentRecoveryPeriod");
  const breakEvenDateEl = document.getElementById("breakEvenDate");
  const lifetimeSavingsEl = document.getElementById("lifetimeSavings");
  const roiMessageEl = document.getElementById("roiMessage");
  const roiContentEl = document.getElementById("roiContent");

  // Rooftop analysis UI
  const detectBtn = document.getElementById("detect-location-btn");
  const latlngValue = document.getElementById("latlng-value");
  const uploadBtn = document.getElementById("upload-image-btn");
  const fileInput = document.getElementById("roof-image-input");
  const previewImg = document.getElementById("image-preview");
  const analyzeBtn = document.getElementById("analyze-btn");
  const downloadBtn = document.getElementById("download-btn");
  const resultsContainer = document.getElementById("analysis-results");

  const INSTALL_COST_PER_KW = 55000;
  const ELECTRICITY_TARIFF = 7;
  const SYSTEM_LIFETIME_YEARS = 25;

  // Demo rooftop analysis values
  const DEMO_RESULTS = {
    roofArea: "148 m²",
    usableArea: "121 m²",
    bestPlacement: "South-West Facing Section",
    shadeRisk: "8%",
    avgPitch: "22°",
    obstructions: "2",
    recommendedCapacity: "8 kW",
    panelCount: "18",
    annualGeneration: "11,600 kWh/year",
    solarScore: "91/100",
  };

  // Helpers
  const showToast = (msg, timeout = 3000) => {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), timeout);
  };

  const safeText = (v) => (v == null ? "N/A" : String(v));

  const renderResults = (data) => {
    if (!resultsContainer) return;
    resultsContainer.innerHTML = "";
    const entries = [
      ["Roof Area", data.roofArea],
      ["Usable Area", data.usableArea],
      ["Best Placement", data.bestPlacement],
      ["Shade Risk", data.shadeRisk],
      ["Average Roof Pitch", data.avgPitch],
      ["Obstructions", data.obstructions],
      ["Recommended Capacity", data.recommendedCapacity],
      ["Estimated Panel Count", data.panelCount],
      ["Expected Annual Generation", data.annualGeneration],
      ["Solar Potential Score", data.solarScore],
    ];

    entries.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "result-card";
      card.innerHTML = `<div class='label'>${label}</div><div class='value'>${safeText(value)}</div>`;
      resultsContainer.appendChild(card);
    });
  };

  const downloadResultsAsText = (data, coords) => {
    const lines = [];
    lines.push("Rooftop Analysis Report");
    lines.push("----------------------");
    if (coords) lines.push(`Location: ${coords.lat}, ${coords.lng}`);
    lines.push("");
    Object.entries(data).forEach(([k, v]) => {
      const prettify = k.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase());
      lines.push(`${prettify}: ${v}`);
    });
    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "rooftop_analysis.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  // ROI formatting
  const formatINR = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value) => {
    if (!Number.isFinite(value)) return "N/A";
    return `${Number(value).toFixed(0)}%`;
  };

  const formatYears = (value) => {
    if (!Number.isFinite(value)) return "N/A";
    return `${Number(value).toFixed(1)} Years`;
  };

  const getBreakEvenDate = (years) => {
    if (!Number.isFinite(years) || years <= 0) return "N/A";
    const now = new Date();
    const monthsToAdd = Math.round(years * 12);
    now.setMonth(now.getMonth() + monthsToAdd);
    return now.toLocaleString("en-IN", { month: "long", year: "numeric" });
  };

  // Load ROI data from localStorage (used by ROI cards)
  const loadRoiData = () => {
    let prediction = null;
    try {
      prediction = JSON.parse(localStorage.getItem("solarPrediction"));
    } catch (err) {
      prediction = null;
    }

    const capacity = Number(prediction?.recommended_capacity);
    const annualProjection = Number(prediction?.annual_projection);
    const panelCount = prediction?.panel_count;
    const energyCoverage = prediction?.energy_coverage;

    const hasValidPrediction =
      Number.isFinite(capacity) && Number.isFinite(annualProjection) && panelCount != null && energyCoverage != null;

    if (!hasValidPrediction) {
      if (roiMessageEl) roiMessageEl.style.display = "block";
      if (roiContentEl) roiContentEl.style.display = "none";
      return;
    }

    if (roiMessageEl) roiMessageEl.style.display = "none";
    if (roiContentEl) roiContentEl.style.display = "block";

    const installationCost = capacity * INSTALL_COST_PER_KW;
    const annualSavings = annualProjection * ELECTRICITY_TARIFF;
    const lifetimeSavings = annualSavings * SYSTEM_LIFETIME_YEARS;
    const paybackYears = annualSavings > 0 ? installationCost / annualSavings : Infinity;
    const roiPercentage = installationCost > 0 ? (annualSavings / installationCost) * 100 : NaN;
    const breakEvenDate = getBreakEvenDate(paybackYears);

    if (installationCostEl) installationCostEl.textContent = formatINR(installationCost);
    if (annualSavingsEl) annualSavingsEl.textContent = formatINR(annualSavings);
    if (lifetimeSavingsEl) lifetimeSavingsEl.textContent = formatINR(lifetimeSavings);
    if (roiPercentageEl) roiPercentageEl.textContent = formatPercent(roiPercentage);
    if (paybackPeriodEl) paybackPeriodEl.textContent = formatYears(paybackYears);
    if (investmentRecoveryEl) investmentRecoveryEl.textContent = formatYears(paybackYears);
    if (breakEvenDateEl) breakEvenDateEl.textContent = breakEvenDate;
  };

  // Event listeners
  if (detectBtn) {
    detectBtn.addEventListener("click", (e) => {
      e.preventDefault();
      if (!navigator.geolocation) {
        showToast("Geolocation is not supported by your browser.");
        return;
      }
      detectBtn.disabled = true;
      detectBtn.innerHTML = '<span class="spinner-inline"></span> Detecting...';
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude.toFixed(6);
          const lng = pos.coords.longitude.toFixed(6);
          if (latlngValue) latlngValue.textContent = `${lat}, ${lng}`;
          showToast("Location detected successfully.");
          detectBtn.disabled = false;
          detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
        },
        (err) => {
          showToast("Location permission denied or unavailable.");
          detectBtn.disabled = false;
          detectBtn.innerHTML = '<span class="material-symbols-outlined">my_location</span> Detect Location';
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener("click", (e) => {
      e.preventDefault();
      fileInput.click();
    });

    fileInput.addEventListener("change", (ev) => {
      const file = ev.target.files && ev.target.files[0];
      if (!file) {
        showToast("No file selected.");
        return;
      }
      const validTypes = ["image/jpeg", "image/png", "image/jpg"];
      if (!validTypes.includes(file.type)) {
        showToast("Please select a JPG or PNG image.");
        fileInput.value = "";
        return;
      }
      const url = URL.createObjectURL(file);
      if (previewImg) {
        previewImg.src = url;
        previewImg.style.display = "block";
      }
      showToast("Image loaded for analysis.");
    });
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      if (!previewImg || previewImg.style.display === "none" || !previewImg.src) {
        showToast("Please upload a rooftop image before analysis.");
        return;
      }
      // simulate analysis
      analyzeBtn.disabled = true;
      const origHtml = analyzeBtn.innerHTML;
      analyzeBtn.innerHTML = '<span class="spinner-inline"></span> Analyzing...';

      setTimeout(() => {
        // populate results
        renderResults(DEMO_RESULTS);

        // store prediction so ROI updates
        const prediction = {
          recommended_capacity: 8,
          annual_projection: 11600,
          panel_count: 18,
          energy_coverage: 100,
        };
        try {
          localStorage.setItem("solarPrediction", JSON.stringify(prediction));
        } catch (err) {
          console.warn("Could not save prediction to localStorage", err);
        }

        loadRoiData();
        showToast("Rooftop analysis complete.");
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = origHtml;
        if (downloadBtn) downloadBtn.disabled = false;
      }, 2000);
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const coordsText = latlngValue ? latlngValue.textContent : null;
      let coords = null;
      if (coordsText && coordsText !== "Not detected") {
        const parts = coordsText.split(",").map((s) => s.trim());
        coords = { lat: parts[0], lng: parts[1] };
      }
      downloadResultsAsText(DEMO_RESULTS, coords);
      showToast("Analysis results downloaded.");
    });
  }

  // Initialize: try to load ROI if prediction already exists
  loadRoiData();

  // Provide safe initialization of results container if prediction exists
  try {
    const existing = JSON.parse(localStorage.getItem("solarPrediction"));
    if (existing && existing.recommended_capacity) {
      // if a prediction exists, show demo results to the panel (so cards aren't empty)
      renderResults(DEMO_RESULTS);
      if (downloadBtn) downloadBtn.disabled = false;
    }
  } catch (err) {}
});
