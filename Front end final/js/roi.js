document.addEventListener("DOMContentLoaded", function () {
  const installationCostEl = document.getElementById("installationCost");
  const roiPercentageEl    = document.getElementById("roiPercentage");
  const annualSavingsEl    = document.getElementById("annualSavings");
  const paybackPeriodEl    = document.getElementById("paybackPeriod");
  const breakEvenDateEl    = document.getElementById("breakEvenDate");
  const lifetimeSavingsEl  = document.getElementById("lifetimeSavings");
  const carbonReductionEl  = document.getElementById("carbonReduction");
  const roiMessageEl       = document.getElementById("roiMessage");
  const roiContentEl       = document.getElementById("roiContent");
  const gotoPredictionBtn  = document.getElementById("gotoPredictionBtn");
  const inflationSlider    = document.getElementById("inflationSlider");
  const inflationDisplay   = document.getElementById("inflationDisplay");
  const degradationSlider  = document.getElementById("degradationSlider");
  const degradationDisplay = document.getElementById("degradationDisplay");
  const recalculateBtn     = document.getElementById("recalculate-btn");

  const INSTALL_COST_PER_KW    = 55000;
  const ELECTRICITY_TARIFF     = 7;       // ₹/kWh
  const SYSTEM_LIFETIME_YEARS  = 25;
  const CO2_PER_MWH            = 1.04;   // tons

  const formatINR = (v) =>
    new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v);

  const formatPercent = (v) => (Number.isFinite(v) ? v.toFixed(1) + "%" : "0%");
  const formatYears   = (v) => (Number.isFinite(v) ? v.toFixed(1) + " Years" : "0.0 Years");

  const showToast = (msg) => {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  };

  const getBreakEvenDate = (years) => {
    if (!Number.isFinite(years) || years <= 0) return "N/A";
    const d = new Date();
    d.setMonth(d.getMonth() + Math.round(years * 12));
    return d.toLocaleString("en-IN", { month: "long", year: "numeric" });
  };

  const loadPrediction = () => {
    try { return JSON.parse(localStorage.getItem("solarPrediction")); } catch { return null; }
  };

  const isValid = (p) =>
    p &&
    Number.isFinite(Number(p.recommended_capacity)) &&
    Number.isFinite(Number(p.annual_projection));

  // Core ROI engine — uses yearFactor = (1+inflation%)*(1-degradation%) per year
  const computeRoi = (prediction, inflationPct, degradationPct) => {
    const capacity    = Number(prediction.recommended_capacity);
    const annualKwh   = Number(prediction.annual_projection);
    const installCost = capacity * INSTALL_COST_PER_KW;
    const year1Saving = annualKwh * ELECTRICITY_TARIFF;
    const yearFactor  = (1 + inflationPct / 100) * (1 - degradationPct / 100);

    const yearlyData = [];
    let cumulative   = 0;
    let paybackYears = SYSTEM_LIFETIME_YEARS;

    for (let i = 0; i < SYSTEM_LIFETIME_YEARS; i++) {
      const savingsThisYear = year1Saving * Math.pow(yearFactor, i);
      yearlyData.push(savingsThisYear);
      const prev = cumulative;
      cumulative += savingsThisYear;
      if (paybackYears === SYSTEM_LIFETIME_YEARS && cumulative >= installCost) {
        paybackYears = i + (installCost - prev) / savingsThisYear;
      }
    }

    const lifetimeSavings  = yearlyData.reduce((a, b) => a + b, 0);
    const roiPct           = installCost > 0 ? (year1Saving / installCost) * 100 : 0;
    const carbonReduction  = (annualKwh / 1000) * CO2_PER_MWH;

    return { installCost, year1Saving, lifetimeSavings, paybackYears, roiPct, carbonReduction, yearlyData };
  };

  const renderSmartInsights = (roiPct, paybackYears, inflationPct, degradationPct) => {
    const ratingValueEl  = document.getElementById("insightRatingValue");
    const ratingChipEl   = document.getElementById("insightRatingChip");
    const ratingDescEl   = document.getElementById("insightRatingDesc");
    const recValueEl     = document.getElementById("insightRecommendValue");
    const recChipEl      = document.getElementById("insightRecommendChip");
    const recDescEl      = document.getElementById("insightRecommendDesc");
    const riskValueEl    = document.getElementById("insightRiskValue");
    const riskChipEl     = document.getElementById("insightRiskChip");
    const riskDescEl     = document.getElementById("insightRiskDesc");

    // ROI Rating
    let rText, rClass, rChipClass, rChipText, rDesc;
    if (roiPct >= 15) {
      rText = "Excellent"; rClass = "value-large value-accent"; rChipClass = "insight-chip chip--success"; rChipText = "Excellent";
      rDesc = "Outstanding returns — this is a high-performing solar investment.";
    } else if (roiPct >= 10) {
      rText = "Good"; rClass = "value-large value-accent"; rChipClass = "insight-chip chip--success"; rChipText = "Good";
      rDesc = "Performance is strong for the current plan.";
    } else if (roiPct >= 5) {
      rText = "Fair"; rClass = "value-large value-warning"; rChipClass = "insight-chip chip--warning"; rChipText = "Fair";
      rDesc = "Acceptable returns. Consider optimising system size.";
    } else {
      rText = "Poor"; rClass = "value-large"; rChipClass = "insight-chip chip--danger"; rChipText = "Poor";
      rDesc = "Returns below expectations — review system parameters.";
    }
    if (ratingValueEl) { ratingValueEl.className = rClass; ratingValueEl.textContent = rText; }
    if (ratingChipEl)  { ratingChipEl.className  = rChipClass; ratingChipEl.textContent = rChipText; }
    if (ratingDescEl)  ratingDescEl.textContent = rDesc;

    // Financial Recommendation
    let recText, recColor, recChipClass, recChipText, recDesc;
    if (paybackYears <= 5) {
      recText = "Strong Buy"; recColor = "#10b981"; recChipClass = "insight-chip chip--success"; recChipText = "Strong Buy";
      recDesc = "Exceptional payback period — proceed with confidence.";
    } else if (paybackYears <= 8) {
      recText = "Buy"; recColor = "#10b981"; recChipClass = "insight-chip chip--success"; recChipText = "Buy";
      recDesc = "Good payback period — solar investment is advisable.";
    } else if (paybackYears <= 12) {
      recText = "Review"; recColor = "#f59e0b"; recChipClass = "insight-chip chip--warning"; recChipText = "Review";
      recDesc = "Fine-tune assumptions before final approval.";
    } else {
      recText = "Hold"; recColor = "#ef4444"; recChipClass = "insight-chip chip--danger"; recChipText = "Hold";
      recDesc = "Payback period is long — consider financing options.";
    }
    if (recValueEl) { recValueEl.style.color = recColor; recValueEl.textContent = recText; }
    if (recChipEl)  { recChipEl.className = recChipClass; recChipEl.textContent = recChipText; }
    if (recDescEl)  recDescEl.textContent = recDesc;

    // Risk Level
    let riskText, riskClass, riskChipClass, riskChipText, riskDesc;
    if (degradationPct <= 0.5 && inflationPct >= 3) {
      riskText = "Low"; riskClass = "value-large value-accent"; riskChipClass = "insight-chip chip--success"; riskChipText = "Low";
      riskDesc = "Favourable degradation and inflation parameters.";
    } else if (degradationPct >= 1.5 || inflationPct <= 1) {
      riskText = "High"; riskClass = "value-large"; riskChipClass = "insight-chip chip--danger"; riskChipText = "High";
      riskDesc = "High degradation or low inflation increases exposure.";
    } else {
      riskText = "Moderate"; riskClass = "value-large value-warning"; riskChipClass = "insight-chip chip--warning"; riskChipText = "Moderate";
      riskDesc = "Main exposure is tariff and policy movement.";
    }
    if (riskValueEl) { riskValueEl.className = riskClass; riskValueEl.textContent = riskText; }
    if (riskChipEl)  { riskChipEl.className  = riskChipClass; riskChipEl.textContent = riskChipText; }
    if (riskDescEl)  riskDescEl.textContent = riskDesc;
  };

  let annualChart   = null;
  let lifetimeChart = null;

  const renderCharts = (yearlyData) => {
    const annualCtx = document.getElementById("annualSavingsChart");
    if (annualCtx && typeof Chart !== "undefined") {
      if (annualChart) annualChart.destroy();
      const labels = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"];
      const data = [];
      let cum = 0;
      for (let i = 0; i < 5; i++) { cum += yearlyData[i] || 0; data.push(Math.round(cum)); }
      try {
        annualChart = new Chart(annualCtx, {
          type: "line",
          data: {
            labels,
            datasets: [{
              label: "Cumulative Savings (₹)",
              data,
              borderColor: "#10b981",
              backgroundColor: "rgba(16,185,129,0.1)",
              borderWidth: 2,
              fill: true,
              tension: 0.4,
              pointBackgroundColor: "#10b981",
              pointBorderColor: "#ffffff",
              pointBorderWidth: 2,
              pointRadius: 5
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { labels: { color: "#d1d5db", font: { size: 12 } } } },
            scales: {
              y: { beginAtZero: true, ticks: { color: "#9CA3AF", callback: (v) => "₹" + (v / 100000).toFixed(1) + "L" }, grid: { color: "rgba(255,255,255,0.05)" } },
              x: { ticks: { color: "#9CA3AF" }, grid: { color: "rgba(255,255,255,0.05)" } }
            }
          }
        });
      } catch (e) { console.warn("annual chart:", e); }
    }

    const lifetimeCtx = document.getElementById("lifetimeSavingsChart");
    if (lifetimeCtx && typeof Chart !== "undefined") {
      if (lifetimeChart) lifetimeChart.destroy();
      const labels = ["0-5 Yrs", "5-10 Yrs", "10-15 Yrs", "15-20 Yrs", "20-25 Yrs"];
      const data = [];
      for (let i = 0; i < 5; i++) {
        let sum = 0;
        for (let j = 0; j < 5; j++) sum += yearlyData[i * 5 + j] || 0;
        data.push(Math.round(sum));
      }
      try {
        lifetimeChart = new Chart(lifetimeCtx, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: "Savings by Period (₹)",
              data,
              backgroundColor: [
                "rgba(16,185,129,0.8)", "rgba(16,185,129,0.7)",
                "rgba(16,185,129,0.6)", "rgba(16,185,129,0.5)", "rgba(16,185,129,0.4)"
              ],
              borderColor: "#10b981",
              borderWidth: 1,
              borderRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { labels: { color: "#d1d5db", font: { size: 12 } } } },
            scales: {
              y: { beginAtZero: true, ticks: { color: "#9CA3AF", callback: (v) => "₹" + (v / 100000).toFixed(0) + "L" }, grid: { color: "rgba(255,255,255,0.05)" } },
              x: { ticks: { color: "#9CA3AF" }, grid: { color: "rgba(255,255,255,0.05)" } }
            }
          }
        });
      } catch (e) { console.warn("lifetime chart:", e); }
    }
  };

  const displayRoiValues = (prediction, inflationPct, degradationPct) => {
    if (!isValid(prediction)) return;
    const roi = computeRoi(prediction, inflationPct, degradationPct);

    if (installationCostEl) installationCostEl.textContent = formatINR(roi.installCost);
    if (annualSavingsEl)    annualSavingsEl.textContent    = formatINR(roi.year1Saving);
    if (lifetimeSavingsEl)  lifetimeSavingsEl.textContent  = formatINR(roi.lifetimeSavings);
    if (roiPercentageEl)    roiPercentageEl.textContent    = formatPercent(roi.roiPct);
    if (paybackPeriodEl)    paybackPeriodEl.textContent    = formatYears(roi.paybackYears);
    if (breakEvenDateEl)    breakEvenDateEl.textContent    = getBreakEvenDate(roi.paybackYears);
    if (carbonReductionEl)  carbonReductionEl.textContent  = roi.carbonReduction.toFixed(1) + " tons/year";

    renderSmartInsights(roi.roiPct, roi.paybackYears, inflationPct, degradationPct);
    renderCharts(roi.yearlyData);

    localStorage.setItem("solarROI", JSON.stringify({
      installationCost: roi.installCost,
      annualSavings:    roi.year1Saving,
      lifetimeSavings:  roi.lifetimeSavings,
      paybackPeriod:    roi.paybackYears,
      roiPercentage:    roi.roiPct,
      carbonReduction:  roi.carbonReduction
    }));
  };

  const getSliderValues = () => ({
    inflationPct:   parseFloat(inflationSlider   ? inflationSlider.value   : "4.5"),
    degradationPct: parseFloat(degradationSlider ? degradationSlider.value : "0.5")
  });

  const initROI = () => {
    const prediction = loadPrediction();
    if (!isValid(prediction)) {
      if (roiMessageEl) roiMessageEl.style.display = "block";
      if (roiContentEl) roiContentEl.style.display = "none";
    } else {
      if (roiMessageEl) roiMessageEl.style.display = "none";
      if (roiContentEl) roiContentEl.style.display = "block";
      const { inflationPct, degradationPct } = getSliderValues();
      displayRoiValues(prediction, inflationPct, degradationPct);
    }
  };

  // Slider: live display update on drag, recalculate on release
  if (inflationSlider) {
    inflationSlider.addEventListener("input", () => {
      if (inflationDisplay) inflationDisplay.textContent = parseFloat(inflationSlider.value).toFixed(1) + "%";
    });
    inflationSlider.addEventListener("change", () => {
      const p = loadPrediction();
      if (isValid(p)) { const sv = getSliderValues(); displayRoiValues(p, sv.inflationPct, sv.degradationPct); }
    });
  }

  if (degradationSlider) {
    degradationSlider.addEventListener("input", () => {
      if (degradationDisplay) degradationDisplay.textContent = parseFloat(degradationSlider.value).toFixed(1) + "%";
    });
    degradationSlider.addEventListener("change", () => {
      const p = loadPrediction();
      if (isValid(p)) { const sv = getSliderValues(); displayRoiValues(p, sv.inflationPct, sv.degradationPct); }
    });
  }

  if (recalculateBtn) {
    recalculateBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const p = loadPrediction();
      if (isValid(p)) {
        const sv = getSliderValues();
        displayRoiValues(p, sv.inflationPct, sv.degradationPct);
        showToast("ROI calculations updated.");
      } else {
        showToast("No prediction data found. Run a solar prediction first.");
      }
    });
  }

  if (gotoPredictionBtn) {
    gotoPredictionBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.href = "/prediction";
    });
  }

  initROI();

  window.addEventListener("storage", (e) => {
    if (e.key === "solarPrediction") initROI();
  });
});
