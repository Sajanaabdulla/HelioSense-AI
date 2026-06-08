// reports.js
// Generates a professional PDF report using jsPDF + AutoTable
// Reads `solarPrediction` and `solarROI` from localStorage and builds the report.

/*
  Expected localStorage objects:
  - solarPrediction: { potential_score, annual_projection, peak_sun_hours, recommended_capacity, panel_count, energy_coverage, monthly_generation, monthly_cloud_coverage, inputs }
  - solarROI: { installation_cost, annual_savings, payback_period, roi_percentage, lifetime_savings, break_even_date }
*/

(function () {
  // Helper: convert image (SVG/PNG) URL to base64 data URL for embedding in PDF
  async function imageUrlToDataUrl(url) {
    try {
      const resp = await fetch(url);
      const blob = await resp.blob();
      return await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (e) {
      console.warn('Unable to load image', url, e);
      return null;
    }
  }

  // Format helpers
  function formatINR(value) {
    if (!Number.isFinite(value)) return 'N/A';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(value);
  }

  function formatPdfCurrency(value) {
    const formatted = formatINR(value);
    // PDF viewers may not always render ₹ correctly with jsPDF standard fonts.
    // Use the INR symbol by default, and fallback to Rs. if needed.
    return formatted;
  }

  const fmt = {
    currencyINR: formatINR,
    number: (v, d = 1) => (Number.isFinite(v) ? Number(v).toFixed(d) : 'N/A'),
    percent: (v, d = 1) => (Number.isFinite(v) ? `${Number(v).toFixed(d)}%` : 'N/A')
  };

  const INSTALL_COST_PER_KW = 55000;
  const ELECTRICITY_TARIFF = 7;
  const SYSTEM_LIFETIME_YEARS = 25;

  const getBreakEvenDate = (years) => {
    if (!Number.isFinite(years) || years <= 0) return 'N/A';
    const now = new Date();
    const monthsToAdd = Math.round(years * 12);
    now.setMonth(now.getMonth() + monthsToAdd);
    return now.toLocaleString('en-IN', { month: 'long', year: 'numeric' });
  };

  const getRoiRating = (percentage) => {
    if (!Number.isFinite(percentage)) return 'Moderate';
    if (percentage > 20) return 'Excellent';
    if (percentage >= 10) return 'Good';
    return 'Moderate';
  };

  async function generateReport() {
    // read stored data
    let prediction = null;
    let roi = null;
    try { prediction = JSON.parse(localStorage.getItem('solarPrediction')); } catch (e) { prediction = null; }
    try { roi = JSON.parse(localStorage.getItem('solarROI')); } catch (e) { roi = null; }

    if (!prediction) {
      alert('Please complete a solar prediction before generating a report.');
      return;
    }

    // Use UMD global
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    doc.setFont('Helvetica', 'normal');

    // Load logo as data URL (falls back silently)
    const logoData = await imageUrlToDataUrl('assets/logo.svg');

    const margin = 40;
    let y = 40;

    // Header - Logo + Title
    if (logoData) {
      try {
        doc.addImage(logoData, 'SVG', margin, y, 60, 60);
      } catch (e) {
        // Some browsers/versions can't embed SVG via addImage; ignore
        try { doc.addImage(logoData, 'PNG', margin, y, 60, 60); } catch (e2) { }
      }
    }

    doc.setFontSize(18);
    doc.setTextColor(34, 34, 34);
    doc.text('HelioSense AI — Solar Analysis Report', margin + 80, y + 28);

    doc.setFontSize(10);
    const genDate = new Date();
    doc.text(`Generated: ${genDate.toLocaleString()}`, margin + 80, y + 44);

    y += 80;

    // Section: Location Details
    doc.setFontSize(12);
    doc.setTextColor(16, 24, 32);
    doc.text('Location Details', margin, y);
    y += 16;

    const inputs = prediction.inputs || {};
    const locationLines = [
      ['Selected Location', inputs.city || 'N/A'],
      ['Latitude', fmt.number(inputs.latitude ?? inputs.lat ?? '', 4)],
      ['Longitude', fmt.number(inputs.longitude ?? inputs.lon ?? '', 4)],
      ['Temperature (°C)', fmt.number(inputs.temperature, 1)],
      ['Humidity (%)', fmt.number(inputs.humidity, 0)],
      ['Wind Speed (m/s)', fmt.number(inputs.wind_speed, 1)]
    ];

    doc.setFontSize(10);
    locationLines.forEach((pair) => {
      doc.text(`${pair[0]}:`, margin, y);
      doc.text(String(pair[1]), margin + 180, y);
      y += 14;
    });

    y += 6;

    // Section: Solar Potential Analysis
    doc.setFontSize(12);
    doc.text('Solar Potential Analysis', margin, y);
    y += 16;

    const pot = [
      ['Potential Score', fmt.percent(prediction.potential_score)],
      ['Peak Sun Hours', fmt.number(prediction.peak_sun_hours, 2)],
      ['Annual Projection (kWh)', fmt.number(prediction.annual_projection, 1)],
      ['Recommended Capacity (kW)', fmt.number(prediction.recommended_capacity, 2)],
      ['Panel Count', prediction.panel_count ?? 'N/A'],
      ['Energy Coverage', fmt.percent(prediction.energy_coverage)]
    ];

    doc.setFontSize(10);
    pot.forEach((p) => {
      doc.text(`${p[0]}:`, margin, y);
      doc.text(String(p[1]), margin + 220, y);
      y += 14;
    });

    y += 8;

    // Section: ROI Analysis
    doc.setFontSize(12);
    doc.text('ROI Analysis', margin, y);
    y += 16;

    const capacity = Number(prediction.recommended_capacity);
    const annualProjection = Number(prediction.annual_projection);

    const validationMessage = 'Generate prediction first';
    const roiFromPrediction = (Number.isFinite(capacity) && Number.isFinite(annualProjection) && annualProjection > 0)
      ? {
          installation_cost: capacity * INSTALL_COST_PER_KW,
          annual_savings: annualProjection * ELECTRICITY_TARIFF,
          lifetime_savings: (annualProjection * ELECTRICITY_TARIFF) * SYSTEM_LIFETIME_YEARS,
          payback_period: (capacity * INSTALL_COST_PER_KW) / (annualProjection * ELECTRICITY_TARIFF),
          roi_percentage: (annualProjection * ELECTRICITY_TARIFF) / (capacity * INSTALL_COST_PER_KW) * 100,
          break_even_date: getBreakEvenDate((capacity * INSTALL_COST_PER_KW) / (annualProjection * ELECTRICITY_TARIFF))
        }
      : null;

    const roiData = {
      ...(roi || {}),
      ...(roiFromPrediction || {})
    };

    const hasRoi = roiFromPrediction !== null;
    const roiLines = [
      ['Installation Cost', hasRoi ? formatPdfCurrency(roiData.installation_cost) : validationMessage],
      ['Annual Savings', hasRoi ? formatPdfCurrency(roiData.annual_savings) : validationMessage],
      ['Payback Period', hasRoi ? `${Number(roiData.payback_period).toFixed(1)} Years` : validationMessage],
      ['ROI Percentage', hasRoi ? fmt.percent(roiData.roi_percentage, 0) : validationMessage],
      ['Lifetime Savings', hasRoi ? formatPdfCurrency(roiData.lifetime_savings) : validationMessage],
      ['Break-even Date', hasRoi ? roiData.break_even_date : validationMessage]
    ];

    doc.setFontSize(10);
    roiLines.forEach((p) => {
      doc.text(`${p[0]}:`, margin, y);
      doc.text(String(p[1]), margin + 220, y);
      y += 14;
    });

    y += 12;

    doc.setFontSize(12);
    doc.text('ROI Summary', margin, y);
    y += 16;

    const roiRating = hasRoi ? getRoiRating(roiData.roi_percentage) : 'N/A';
    const summaryLines = [
      ['- Investment Cost', hasRoi ? formatPdfCurrency(roiData.installation_cost) : validationMessage],
      ['- Expected Annual Savings', hasRoi ? formatPdfCurrency(roiData.annual_savings) : validationMessage],
      ['- Estimated Payback Period', hasRoi ? `${Number(roiData.payback_period).toFixed(1)} Years` : validationMessage],
      ['- Total Lifetime Savings', hasRoi ? formatPdfCurrency(roiData.lifetime_savings) : validationMessage],
      ['- ROI Rating', hasRoi ? roiRating : validationMessage]
    ];

    doc.setFontSize(10);
    summaryLines.forEach((p) => {
      doc.text(`${p[0]}:`, margin, y);
      doc.text(String(p[1]), margin + 240, y);
      y += 14;
    });

    y += 12;

    // Section: Monthly Production Table
    doc.setFontSize(12);
    doc.text('Monthly Production', margin, y);
    y += 14;

    // Prepare table rows
    const months = Object.keys(prediction.monthly_generation || {});
    const tableBody = months.map((m) => {
      const gen = prediction.monthly_generation[m];
      const cloud = (prediction.monthly_cloud_coverage || {})[m];
      return [m, gen != null ? String(gen) : 'N/A', cloud != null ? fmt.percent(cloud) : 'N/A'];
    });

    // If table would overflow page, use autoTable which handles pagination
    doc.autoTable({
      head: [['Month', 'Generation (kWh)', 'Cloud Coverage (%)']],
      body: tableBody,
      startY: y,
      styles: { fontSize: 9 },
      headStyles: { fillColor: [40, 130, 200] }
    });

    const afterTableY = doc.lastAutoTable ? doc.lastAutoTable.finalY + 10 : y + tableBody.length * 14 + 10;

    // Section: Recommendation Summary
    doc.setFontSize(12);
    doc.text('Recommendation Summary', margin, afterTableY);

    const recY = afterTableY + 14;
    const recommendation = (function () {
      const score = prediction.potential_score;
      const annual = prediction.annual_projection;
      const pay = roiData.payback_period || (roiData.payback_period === 0 ? 0 : null);
      const suitability = score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'moderate' : 'low';
      const years = pay ? `${Number(pay).toFixed(1)} years` : 'an estimated period';
      return `Based on the analyzed solar resource and weather conditions, this location has ${suitability} solar potential. The projected annual energy generation is ${annual != null ? fmt.number(annual,1) + ' kWh' : 'N/A'} with an estimated payback period of ${years}.`;
    })();

    doc.setFontSize(10);
    doc.text(recommendation, margin, recY, { maxWidth: 520 });

    // Footer
    const pageCount = doc.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(9);
      doc.setTextColor(120);
      doc.text('HelioSense AI — AI Powered Solar Planning Platform — Generated Automatically', margin, doc.internal.pageSize.getHeight() - 30);
      doc.text(`Page ${i} of ${pageCount}`, doc.internal.pageSize.getWidth() - margin - 80, doc.internal.pageSize.getHeight() - 30);
    }

    // Save the PDF
    doc.save('HelioSense_Solar_Report.pdf');
  }

  // Attach to button
  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('generate-pdf-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      btn.disabled = true;
      const original = btn.innerHTML;
      btn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Generating...';
      generateReport().finally(() => {
        btn.disabled = false;
        btn.innerHTML = original;
      });
    });
  });
})();
