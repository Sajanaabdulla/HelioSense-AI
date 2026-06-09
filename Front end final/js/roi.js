document.addEventListener("DOMContentLoaded", function () {
  // ROI elements
  const installationCostEl = document.getElementById("installationCost");
  const roiPercentageEl = document.getElementById("roiPercentage");
  const annualSavingsEl = document.getElementById("annualSavings");
  const paybackPeriodEl = document.getElementById("paybackPeriod");
  const investmentRecoveryEl = document.getElementById("investmentRecoveryPeriod");
  const breakEvenDateEl = document.getElementById("breakEvenDate");
  const lifetimeSavingsEl = document.getElementById("lifetimeSavings");
  const carbonReductionEl = document.getElementById("carbonReduction");
  const roiMessageEl = document.getElementById("roiMessage");
  const roiContentEl = document.getElementById("roiContent");
  const gotoPredictionBtn = document.getElementById("gotoPredictionBtn");

  const INSTALL_COST_PER_KW = 55000;
  const ELECTRICITY_TARIFF = 7;
  const SYSTEM_LIFETIME_YEARS = 25;
  const CO2_REDUCTION_PER_MWH = 1.04; // tons

  // Demo prediction values (FALLBACK ONLY)
  const DEMO_PREDICTION = {
    recommended_capacity: 8,
    annual_projection: 11600,
    panel_count: 18,
    energy_coverage: 100,
    potential_score: 91
  };

  // Helper functions
  const showToast = (msg, timeout = 3000) => {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), timeout);
  };

  const formatINR = (value) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value) => {
    if (!Number.isFinite(value)) return "0%";
    return `${Number(value).toFixed(1)}%`;
  };

  const formatYears = (value) => {
    if (!Number.isFinite(value)) return "0.0 Years";
    return `${Number(value).toFixed(1)} Years`;
  };

  const getBreakEvenDate = (years) => {
    if (!Number.isFinite(years) || years <= 0) return "N/A";
    const now = new Date();
    const monthsToAdd = Math.round(years * 12);
    now.setMonth(now.getMonth() + monthsToAdd);
    return now.toLocaleString("en-IN", { month: "long", year: "numeric" });
  };

  // Load and check for prediction data
  const loadPredictionData = () => {
    let prediction = null;
    try {
      prediction = JSON.parse(localStorage.getItem("solarPrediction"));
    } catch (err) {
      console.warn("Could not parse stored prediction:", err);
      prediction = null;
    }

    return prediction;
  };

  // Validate prediction has required fields
  const isPredictionValid = (prediction) => {
    return (
      prediction &&
      Number.isFinite(prediction.recommended_capacity) &&
      Number.isFinite(prediction.annual_projection)
    );
  };

  // Display ROI values
  const displayRoiValues = (prediction) => {
    const capacity = Number(prediction.recommended_capacity);
    const annualProjection = Number(prediction.annual_projection);

    // Ensure finite values
    if (!Number.isFinite(capacity) || !Number.isFinite(annualProjection)) {
      return;
    }

    const installationCost = capacity * INSTALL_COST_PER_KW;
    const annualSavings = annualProjection * ELECTRICITY_TARIFF;
    const lifetimeSavings = annualSavings * SYSTEM_LIFETIME_YEARS;
    const paybackYears = annualSavings > 0 ? installationCost / annualSavings : 0;
    const roiPercentage = installationCost > 0 ? (annualSavings / installationCost) * 100 : 0;
    const breakEvenDate = getBreakEvenDate(paybackYears);
    const carbonReduction = (annualProjection / 1000) * CO2_REDUCTION_PER_MWH; // tons per year

    // Update DOM
    if (installationCostEl) installationCostEl.textContent = formatINR(installationCost);
    if (annualSavingsEl) annualSavingsEl.textContent = formatINR(annualSavings);
    if (lifetimeSavingsEl) lifetimeSavingsEl.textContent = formatINR(lifetimeSavings);
    if (roiPercentageEl) roiPercentageEl.textContent = formatPercent(roiPercentage);
    if (paybackPeriodEl) paybackPeriodEl.textContent = formatYears(paybackYears);
    if (investmentRecoveryEl) investmentRecoveryEl.textContent = formatYears(paybackYears);
    if (breakEvenDateEl) breakEvenDateEl.textContent = breakEvenDate;
    if (carbonReductionEl) carbonReductionEl.textContent = carbonReduction.toFixed(1) + " tons/year";

    // Render charts
    renderCharts(annualSavings, capacity, annualProjection);
  };

  // Chart rendering
  let annualChart = null;
  let lifetimeChart = null;

  const renderCharts = (annualSavings, capacity, annualProjection) => {
    renderAnnualSavingsChart(annualSavings);
    renderLifetimeSavingsChart(annualSavings);
  };

  const renderAnnualSavingsChart = (annualSavings) => {
    const ctx = document.getElementById("annualSavingsChart");
    if (!ctx || typeof Chart === "undefined") return;

    const years = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"];
    const data = [];
    let cumulative = 0;
    for (let i = 0; i < 5; i++) {
      cumulative += annualSavings * (1 - i * 0.005); // slight degradation
      data.push(Math.round(cumulative));
    }

    if (annualChart) {
      annualChart.destroy();
    }

    try {
      annualChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: years,
          datasets: [
            {
              label: "Cumulative Savings (₹)",
              data: data,
              borderColor: "#10b981",
              backgroundColor: "rgba(16, 185, 129, 0.1)",
              borderWidth: 2,
              fill: true,
              tension: 0.4,
              pointBackgroundColor: "#10b981",
              pointBorderColor: "#ffffff",
              pointBorderWidth: 2,
              pointRadius: 5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              labels: { color: "#d1d5db", font: { size: 12 } }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { color: "#9CA3AF", callback: (v) => "₹" + (v / 100000).toFixed(1) + "L" },
              grid: { color: "rgba(255, 255, 255, 0.05)" }
            },
            x: {
              ticks: { color: "#9CA3AF" },
              grid: { color: "rgba(255, 255, 255, 0.05)" }
            }
          }
        }
      });
    } catch (err) {
      console.warn("Could not render annual savings chart:", err);
    }
  };

  const renderLifetimeSavingsChart = (annualSavings) => {
    const ctx = document.getElementById("lifetimeSavingsChart");
    if (!ctx || typeof Chart === "undefined") return;

    const labels = ["0-5 Yrs", "5-10 Yrs", "10-15 Yrs", "15-20 Yrs", "20-25 Yrs"];
    const data = [];
    for (let i = 0; i < 5; i++) {
      let sum = 0;
      for (let j = 0; j < 5; j++) {
        const year = i * 5 + j;
        sum += annualSavings * Math.pow(0.995, year); // degradation
      }
      data.push(Math.round(sum));
    }

    if (lifetimeChart) {
      lifetimeChart.destroy();
    }

    try {
      lifetimeChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Savings by Period (₹)",
              data: data,
              backgroundColor: [
                "rgba(16, 185, 129, 0.8)",
                "rgba(16, 185, 129, 0.7)",
                "rgba(16, 185, 129, 0.6)",
                "rgba(16, 185, 129, 0.5)",
                "rgba(16, 185, 129, 0.4)"
              ],
              borderColor: "#10b981",
              borderWidth: 1,
              borderRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              labels: { color: "#d1d5db", font: { size: 12 } }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { color: "#9CA3AF", callback: (v) => "₹" + (v / 100000).toFixed(0) + "L" },
              grid: { color: "rgba(255, 255, 255, 0.05)" }
            },
            x: {
              ticks: { color: "#9CA3AF" },
              grid: { color: "rgba(255, 255, 255, 0.05)" }
            }
          }
        }
      });
    } catch (err) {
      console.warn("Could not render lifetime savings chart:", err);
    }
  };

  // Initialize ROI page
  const initROI = () => {
    // Check for prediction data
    const prediction = loadPredictionData();

    if (!isPredictionValid(prediction)) {
      // Show prediction-required message
      if (roiMessageEl) roiMessageEl.style.display = "block";
      if (roiContentEl) roiContentEl.style.display = "none";
    } else {
      // Show ROI content and calculate
      if (roiMessageEl) roiMessageEl.style.display = "none";
      if (roiContentEl) roiContentEl.style.display = "block";
      displayRoiValues(prediction);
    }
  };

  // Event listener for "Go To Prediction" button
  if (gotoPredictionBtn) {
    gotoPredictionBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.location.href = "/prediction";
    });
  }

  // Recalculate button (if present)
  const recalculateBtn = document.getElementById("recalculate-btn");
  if (recalculateBtn) {
    recalculateBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const prediction = loadPredictionData();
      if (isPredictionValid(prediction)) {
        displayRoiValues(prediction);
        showToast("ROI calculations updated.");
      }
    });
  }

  // Initialize on page load
  initROI();

  // Listen for storage changes (when prediction is updated on another tab/window)
  window.addEventListener("storage", (e) => {
    if (e.key === "solarPrediction") {
      console.log("Prediction data changed, updating ROI...");
      initROI();
    }
  });
});
