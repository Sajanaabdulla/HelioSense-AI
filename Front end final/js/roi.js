document.addEventListener("DOMContentLoaded", function () {
  const installationCostEl = document.getElementById("installationCost");
  const roiPercentageEl = document.getElementById("roiPercentage");
  const annualSavingsEl = document.getElementById("annualSavings");
  const paybackPeriodEl = document.getElementById("paybackPeriod");
  const investmentRecoveryEl = document.getElementById("investmentRecoveryPeriod");
  const breakEvenDateEl = document.getElementById("breakEvenDate");
  const lifetimeSavingsEl = document.getElementById("lifetimeSavings");
  const roiMessageEl = document.getElementById("roiMessage");
  const roiContentEl = document.getElementById("roiContent");
  const recalcBtn = document.getElementById("recalculate-btn");

  const INSTALL_COST_PER_KW = 55000;
  const ELECTRICITY_TARIFF = 7;
  const SYSTEM_LIFETIME_YEARS = 25;

  const formatINR = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value) => {
    if (!Number.isFinite(value)) {
      return "N/A";
    }
    return `${Number(value).toFixed(0)}%`;
  };

  const formatYears = (value) => {
    if (!Number.isFinite(value)) {
      return "N/A";
    }
    return `${Number(value).toFixed(1)} Years`;
  };

  const getBreakEvenDate = (years) => {
    if (!Number.isFinite(years) || years <= 0) {
      return "N/A";
    }
    const now = new Date();
    const monthsToAdd = Math.round(years * 12);
    now.setMonth(now.getMonth() + monthsToAdd);
    return now.toLocaleString("en-IN", {
      month: "long",
      year: "numeric",
    });
  };

  const loadRoiData = () => {
    let prediction = null;
    try {
      prediction = JSON.parse(localStorage.getItem("solarPrediction"));
    } catch (error) {
      console.warn("Unable to parse solarPrediction from localStorage:", error);
      prediction = null;
    }

    console.log("Prediction Data:", prediction);

    const capacity = Number(prediction?.recommended_capacity);
    const annualProjection = Number(prediction?.annual_projection);
    const panelCount = prediction?.panel_count;
    const energyCoverage = prediction?.energy_coverage;

    const hasValidPrediction =
      Number.isFinite(capacity) &&
      Number.isFinite(annualProjection) &&
      panelCount != null &&
      energyCoverage != null;

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

    console.log("ROI calculated values:", {
      capacity,
      annualProjection,
      panelCount,
      energyCoverage,
      installationCost,
      annualSavings,
      lifetimeSavings,
      paybackYears,
      roiPercentage,
    });

    if (installationCostEl) installationCostEl.textContent = formatINR(installationCost);
    if (annualSavingsEl) annualSavingsEl.textContent = formatINR(annualSavings);
    if (lifetimeSavingsEl) lifetimeSavingsEl.textContent = formatINR(lifetimeSavings);
    if (roiPercentageEl) roiPercentageEl.textContent = formatPercent(roiPercentage);
    if (paybackPeriodEl) paybackPeriodEl.textContent = formatYears(paybackYears);
    if (investmentRecoveryEl) investmentRecoveryEl.textContent = formatYears(paybackYears);
    if (breakEvenDateEl) breakEvenDateEl.textContent = breakEvenDate;
  };

  if (recalcBtn) {
    recalcBtn.addEventListener("click", function () {
      recalcBtn.disabled = true;
      recalcBtn.innerHTML =
        '<span class="material-symbols-outlined animate-spin">progress_activity</span> Calculating...';

      setTimeout(() => {
        loadRoiData();
        recalcBtn.disabled = false;
        recalcBtn.innerHTML =
          '<span class="material-symbols-outlined">refresh</span> Recalculate ROI';
      }, 500);
    });
  }

  loadRoiData();
});
