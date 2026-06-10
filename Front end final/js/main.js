/**
 * HelioSense AI — shared minimal JavaScript
 */
(function () {
  'use strict';

  function initHeaderScroll() {
    var header = document.querySelector('.site-header');
    if (!header) return;
    window.addEventListener('scroll', function () {
      header.classList.toggle('site-header--scrolled', window.scrollY > 50);
    });
  }

  // Simple toast for user-facing messages (non-blocking)
  function showToast(msg, timeout = 3000) {
    try {
      var t = document.createElement('div');
      t.className = 'toast';
      t.textContent = msg;
      document.body.appendChild(t);
      setTimeout(function () { try { t.remove(); } catch (e) {} }, timeout);
    } catch (e) { console.warn('Toast failed', e); }
  }
  // expose to window so other scripts can use it
  window.showToast = showToast;

  function initChartBars() {
    document.querySelectorAll('.chart-bar[data-height]').forEach(function (bar) {
      var target = bar.getAttribute('data-height');
      bar.style.height = '0%';
      setTimeout(function () {
        bar.style.height = target;
      }, 200);
    });
  }

  function initModal(modalId, openIds, closeId) {
    var modal = document.getElementById(modalId);
    if (!modal) return;

    openIds.forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.addEventListener('click', function () { modal.classList.add('is-open'); });
    });

    var closeBtn = document.getElementById(closeId);
    if (closeBtn) closeBtn.addEventListener('click', function () { modal.classList.remove('is-open'); });

    modal.addEventListener('click', function (e) {
      if (e.target === modal) modal.classList.remove('is-open');
    });
  }

  function initRangeLabels() {
    document.querySelectorAll('.form-range[data-output]').forEach(function (range) {
      var output = document.getElementById(range.getAttribute('data-output'));
      if (!output) return;
      var suffix = range.getAttribute('data-suffix') || '';
      function update() { output.textContent = range.value + suffix; }
      range.addEventListener('input', update);
      update();
    });
  }

  function initSmoothAnchors() {
    document.querySelectorAll('a[href^="#"]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        var target = document.querySelector(link.getAttribute('href'));
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });
  }

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

  function showEnergyOutput(data) {
    document.getElementById('val-capacity').textContent = data.capacity;
    document.getElementById('val-panels').textContent = data.panels;
    document.getElementById('val-monthly').textContent = data.monthly;
    document.getElementById('val-annual').textContent = data.annual;
    document.getElementById('val-savings').textContent = data.savings;
    document.querySelectorAll('.energy-output-card').forEach(function (card) {
      card.classList.remove('energy-output-card--hidden');
    });
  }

  function calculateFromConsumption(kwh, bill) {
    var capacityKw = Math.max(1, Math.ceil(kwh / 120));
    var panels = Math.ceil(capacityKw * 2);
    var monthlyGen = Math.round(capacityKw * 120);
    var annualGen = monthlyGen * 12;
    var savings = bill > 0 ? Math.round(bill * 12 * 0.6) : Math.round(annualGen * 4.2);
    return {
      capacity: capacityKw + ' kW System',
      panels: panels + ' Panels',
      monthly: monthlyGen + ' kWh/month',
      annual: annualGen + ' kWh/year',
      savings: '₹' + savings.toLocaleString('en-IN') + '/year'
    };
  }

  function initEnergyUsage() {
    var tabs = document.querySelectorAll('.energy-tab');
    if (!tabs.length) return;

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

    var fileInput = document.getElementById('bill-file-input');
    var fileName = document.getElementById('bill-file-name');
    var dropZone = document.getElementById('bill-drop-zone');
    var chooseBtn = document.getElementById('choose-bill-btn');
    var uploadBtn = document.getElementById('upload-bill-btn');
    var analyzeBtn = document.getElementById('analyze-bill-btn');
    var calculateBtn = document.getElementById('calculate-btn');
    var resetBtn = document.getElementById('reset-btn');
    var kwhInput = document.getElementById('monthly-kwh');
    var billInput = document.getElementById('monthly-bill');
    var _ocrData = null;

    function setFile(file) {
      if (file) fileName.textContent = file.name;
    }

    if (chooseBtn && fileInput) {
      chooseBtn.addEventListener('click', function () { fileInput.click(); });
    }
    if (fileInput) {
      fileInput.addEventListener('change', function (e) { setFile(e.target.files[0]); });
    }
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
        if (e.dataTransfer.files[0]) {
          fileInput.files = e.dataTransfer.files;
          setFile(e.dataTransfer.files[0]);
        }
      });
    }
    if (uploadBtn) {
      uploadBtn.addEventListener('click', function () {
        if (!fileInput || !fileInput.files[0]) {
          fileName.textContent = 'Please choose a bill file first';
          return;
        }
        var orig = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Uploading...';
        uploadBtn.disabled = true;
        _ocrData = null;

        var formData = new FormData();
        formData.append('bill', fileInput.files[0]);

        fetch(API_BASE_URL + '/upload-bill', { method: 'POST', body: formData })
          .then(function (resp) {
            if (!resp.ok) throw new Error('Server error ' + resp.status);
            return resp.json();
          })
          .then(function (data) {
            if (data.success) {
              _ocrData = data;
              fileName.textContent = fileInput.files[0].name + ' — Uploaded';
              showOcrResult(data);
              showToast('Bill uploaded. Click Analyze Bill for recommendations.');
            } else {
              fileName.textContent = 'Upload failed';
              showToast('OCR failed: ' + (data.error || 'Unknown error'), 5000);
            }
          })
          .catch(function (err) {
            fileName.textContent = 'Upload error';
            showToast('Upload error: ' + err.message, 5000);
          })
          .finally(function () {
            uploadBtn.innerHTML = orig;
            uploadBtn.disabled = false;
          });
      });
    }
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', function () {
        if (!_ocrData) {
          showToast('Please upload a bill first.', 4000);
          return;
        }
        var kwh = _ocrData.units_consumed || 0;
        var bill = _ocrData.bill_amount || 0;
        if (kwh <= 0) {
          showToast('Could not extract usage from bill. Try manual entry.', 5000);
          return;
        }
        showEnergyOutput(calculateFromConsumption(kwh, bill));
      });
    }
    if (calculateBtn) {
      calculateBtn.addEventListener('click', function () {
        var kwh = parseFloat(kwhInput.value) || 0;
        var bill = parseFloat(billInput.value) || 0;
        if (kwh <= 0) {
          kwhInput.focus();
          return;
        }
        showEnergyOutput(calculateFromConsumption(kwh, bill));
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        if (kwhInput) kwhInput.value = '';
        if (billInput) billInput.value = '';
        document.querySelectorAll('.energy-output-card').forEach(function (card) {
          card.classList.add('energy-output-card--hidden');
        });
      });
    }
  }

  const CHAT_HISTORY_KEY = 'heliaChatHistory';
  const HELIA_USER_KEY = 'heliaUser';
  const API_BASE_URL = window.HELIOSENSE_API_URL || '';
  const CHAT_ENDPOINT = `${API_BASE_URL}/chat-query`;

  function logDebug(label, value) {
    console.log(label, value);
  }

  function saveChatHistory(history) {
    try {
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history));
    } catch (error) {
      console.warn('Unable to save chat history:', error);
    }
  }

  function loadChatHistory() {
    try {
      const stored = localStorage.getItem(CHAT_HISTORY_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.warn('Unable to load chat history:', error);
      return [];
    }
  }

  function appendMessage(messages, message) {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-msg--' + message.speaker;
    if (message.speaker === 'ai') {
      div.innerHTML = '<span class="chat-msg__label">Helia AI</span>' + message.text;
    } else {
      div.textContent = message.text;
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function getSavedUser() {
    try {
      return JSON.parse(localStorage.getItem(HELIA_USER_KEY) || 'null');
    } catch (error) {
      console.warn('Unable to parse user from localStorage:', error);
      return null;
    }
  }

  function saveUser(user) {
    try {
      localStorage.setItem(HELIA_USER_KEY, JSON.stringify(user));
    } catch (error) {
      console.warn('Unable to save user to localStorage:', error);
    }
  }

  function clearUser() {
    localStorage.removeItem(HELIA_USER_KEY);
  }

  function initUserProfile() {
    const user = getSavedUser();
    const display = document.getElementById('userNameDisplay');
    if (display) {
      display.textContent = (user && user.name) ? user.name : 'Guest';
    }
  }

  function initAuthForms() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const logoutLinks = document.querySelectorAll('a[href="/login"]');

    if (logoutLinks.length) {
      logoutLinks.forEach(function (link) {
        link.addEventListener('click', function () {
          clearUser();
        });
      });
    }

    function validateEmail(email) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    if (loginForm) {
      loginForm.addEventListener('submit', function (event) {
        event.preventDefault();
        const email = (loginForm.email.value || '').trim();
        if (!validateEmail(email)) {
          alert('Please enter a valid email address.');
          loginForm.email.focus();
          return;
        }
        const name = email.split('@')[0].replace(/[._-]+/g, ' ').trim();
        const user = {
          name: name.split(' ').map(function (part) {
            return part.charAt(0).toUpperCase() + part.slice(1);
          }).join(' '),
          email: email
        };
        saveUser(user);
        window.location.href = '/dashboard';
      });
    }

    if (registerForm) {
      registerForm.addEventListener('submit', function (event) {
        event.preventDefault();
        const fullName = (registerForm.full_name.value || '').trim();
        const email = (registerForm.email.value || '').trim();
        const password = registerForm.password.value || '';
        const confirmPassword = registerForm.confirm_password.value || '';
        if (!fullName) {
          alert('Please enter your full name.');
          registerForm.full_name.focus();
          return;
        }
        if (!validateEmail(email)) {
          alert('Please enter a valid email address.');
          registerForm.email.focus();
          return;
        }
        if (password.length < 6) {
          alert('Please choose a password with at least 6 characters.');
          registerForm.password.focus();
          return;
        }
        if (password !== confirmPassword) {
          alert('Passwords do not match.');
          registerForm.confirm_password.focus();
          return;
        }
        const user = {
          name: fullName,
          email: email
        };
        saveUser(user);
        window.location.href = '/dashboard';
      });
    }
  }

  function getDemoResponse(question) {
    var q = question.toLowerCase();
    if (q.includes('prediction') || q.includes('forecast') || q.includes('analysis')) {
      return 'Based on the analysis, your rooftop has high solar potential. An 8 kW system is recommended.';
    }
    if (q.includes('roi') || q.includes('return') || q.includes('payback') || q.includes('savings')) {
      return 'Estimated payback period is approximately 4 to 5 years with annual savings of ₹72,000.';
    }
    if (q.includes('panel') || q.includes('solar panel') || q.includes('count')) {
      return 'Approximately 18 solar panels are recommended for the available rooftop area.';
    }
    if (q.includes('rooftop') || q.includes('roof') || q.includes('area') || q.includes('shade')) {
      return 'Usable rooftop area is estimated at 121 m² with low shading and good solar exposure.';
    }
    return 'I am Helia AI, your solar planning assistant. I can help with rooftop analysis, ROI, prediction, and solar system recommendations.';
  }

  async function queryHelia(question) {
    try {
      var prediction = null;
      var roi = null;
      try {
        prediction = JSON.parse(localStorage.getItem('solarPrediction') || 'null');
        roi = JSON.parse(localStorage.getItem('solarROI') || 'null');
      } catch (parseErr) {
        console.warn('Unable to parse stored data:', parseErr);
      }
      logDebug('User Message:', question);
      logDebug('Prediction Data:', prediction);
      logDebug('ROI Data:', roi);

      if (!CHAT_ENDPOINT) {
        console.warn('Chat endpoint not configured; using demo response');
        return getDemoResponse(question);
      }

      var response = await fetch(CHAT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question, prediction: prediction, roi: roi })
      });

      if (!response.ok) {
        console.error('Chat API error:', response.status, response.statusText);
        return getDemoResponse(question);
      }

      var payload = null;
      try {
        payload = await response.json();
      } catch (jsonErr) {
        console.error('Failed to parse chat response:', jsonErr);
        return getDemoResponse(question);
      }

      logDebug('Retrieved Chunks:', payload.chunks || []);

      if (payload && payload.answer && typeof payload.answer === 'string' && payload.answer.trim()) {
        return payload.answer;
      }

      console.warn('No valid answer in payload, using demo');
      return getDemoResponse(question);
    } catch (err) {
      console.error('Chat query error:', err);
      return getDemoResponse(question);
    }
  }

  function buildWelcomeMessage() {
    return {
      speaker: 'ai',
      text: 'Hello! I\'m Helia AI ☀️ Your friendly solar consultant. Ask me about solar predictions, ROI, rooftop suitability, or reports and I\'ll guide you through the next steps.'
    };
  }

  function displayChatHistory(messagesContainer, history) {
    messagesContainer.innerHTML = '';
    history.forEach((item) => appendMessage(messagesContainer, item));
  }

  function getTypingIndicator() {
    const typing = document.createElement('div');
    typing.className = 'chat-msg chat-msg--ai chat-msg--typing';
    typing.innerHTML = '<span class="chat-msg__label">Helia AI</span>Helia is typing...';
    return typing;
  }

  function initChatbot() {
    const messages = document.getElementById('chat-messages');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-chat-btn');
    const clearBtn = document.getElementById('clear-chat-btn');
    if (!messages || !input) return;

    let history = loadChatHistory();
    if (!history.length) {
      history = [buildWelcomeMessage()];
    }
    displayChatHistory(messages, history);
    saveChatHistory(history);

    async function sendMessage(text) {
      const question = (text || input.value).trim();
      if (!question) return;
      const userMessage = { speaker: 'user', text: question };
      history.push(userMessage);
      appendMessage(messages, userMessage);
      input.value = '';
      saveChatHistory(history);

      const typingIndicator = getTypingIndicator();
      messages.appendChild(typingIndicator);
      messages.scrollTop = messages.scrollHeight;

      try {
        var answer = await queryHelia(question);
        if (typingIndicator && typingIndicator.parentNode) {
          try { messages.removeChild(typingIndicator); } catch (e) {}
        }
        var aiMessage = { speaker: 'ai', text: answer };
        history.push(aiMessage);
        appendMessage(messages, aiMessage);
        saveChatHistory(history);
      } catch (error) {
        console.error('Chat query error:', error);
        if (typingIndicator && typingIndicator.parentNode) {
          try { messages.removeChild(typingIndicator); } catch (e) {}
        }
        var fallbackMessage = { speaker: 'ai', text: 'I am Helia AI, your solar planning assistant. I can help with rooftop analysis, ROI, prediction, and solar system recommendations.' };
        history.push(fallbackMessage);
        appendMessage(messages, fallbackMessage);
        saveChatHistory(history);
      }
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', function () {
        sendMessage();
      });
    }

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    document.querySelectorAll('.chat-suggestion').forEach(function (btn) {
      btn.addEventListener('click', function () {
        sendMessage(btn.getAttribute('data-question'));
      });
    });

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        history = [buildWelcomeMessage()];
        saveChatHistory(history);
        displayChatHistory(messages, history);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initHeaderScroll();
    initChartBars();
    initModal('report-modal', ['view-report-btn'], 'close-modal');
    initRangeLabels();
    initSmoothAnchors();
    initEnergyUsage();
    initChatbot();
    initSolarPrediction();
    initAnalysis();
    initAuthForms();
    initUserProfile();
  });
})();

// ============================================================================
// SOLAR PREDICTION MODULE — HelioSense AI
// ============================================================================

const WEATHER_API_KEY = "6c14532b577693c9411d57cc80e66422";

function initSolarPrediction() {
  // Get DOM elements
  const manualLocationBtn = document.getElementById("manualLocationBtn");
  const locationBtn = document.getElementById("locationBtn");
  const manualLocationContainer = document.getElementById("manualLocationContainer");
  const cityInput = document.getElementById("cityInput");
  const selectedLocation = document.getElementById("selectedLocation");
  const selectedCityName = document.getElementById("selectedCityName");
  const predictBtn = document.getElementById("predictBtn");

  // Verify all elements exist before adding listeners
  if (!manualLocationBtn) console.error("Missing: manualLocationBtn");
  if (!locationBtn) console.error("Missing: locationBtn");
  if (!manualLocationContainer) console.error("Missing: manualLocationContainer");
  if (!cityInput) console.error("Missing: cityInput");
  if (!selectedLocation) console.error("Missing: selectedLocation");
  if (!selectedCityName) console.error("Missing: selectedCityName");
  if (!predictBtn) console.error("Missing: predictBtn");

  var gpsCoords = null;

  const loadStoredPrediction = () => {
    let storedPrediction = null;
    try {
      storedPrediction = JSON.parse(localStorage.getItem("solarPrediction"));
    } catch (error) {
      console.warn("Unable to parse stored solar prediction:", error);
      storedPrediction = null;
    }

    if (storedPrediction && typeof storedPrediction === "object") {
      console.log("Stored solar prediction loaded:", storedPrediction);
      try {
        updateDashboardCards(storedPrediction);
      } catch (error) {
        console.error("Dashboard update failed:", error);
      }
    }

    return storedPrediction;
  };

  // ─────────────────────────────────────────────────────────────────────────
  // BUTTON 1: "Enter Location" — Toggle manual input
  // ─────────────────────────────────────────────────────────────────────────
  if (manualLocationBtn) {
    manualLocationBtn.addEventListener("click", function() {
      if (manualLocationContainer.style.display === "none") {
        manualLocationContainer.style.display = "block";
        if (cityInput) cityInput.focus();
      } else {
        manualLocationContainer.style.display = "none";
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUTTON 2: "Use Live Location" — Get geolocation + weather
  // ─────────────────────────────────────────────────────────────────────────
  if (locationBtn) {
    locationBtn.addEventListener("click", async function() {
      locationBtn.disabled = true;
      locationBtn.textContent = "📍 Getting Location...";

      // Check if geolocation is available
      if (!navigator.geolocation) {
        alert("⚠️ Geolocation is not supported by your browser.");
        locationBtn.disabled = false;
        locationBtn.textContent = "📍 Use Live Location";
        return;
      }

      // Detect permission state before requesting location (non-blocking)
      try {
        if (navigator.permissions) {
          const permission = await navigator.permissions.query({ name: 'geolocation' });
          if (permission.state === 'denied') {
            console.warn('Location permission is blocked');
            showToast('Location permission is blocked. Use manual entry.');
            locationBtn.disabled = false;
            locationBtn.textContent = '📍 Use Live Location';
            if (manualLocationContainer && manualLocationContainer.style.display === 'none') {
              manualLocationContainer.style.display = 'block';
              if (cityInput) cityInput.focus();
            }
            return;
          }
        }
      } catch (permissionError) {
        console.warn('Permission API error:', permissionError);
      }

      navigator.geolocation.getCurrentPosition(
        function(position) {
          try {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            gpsCoords = { lat: lat, lon: lon };
            console.log('Geolocation success', { lat, lon });

            var cityLabel = 'Current Location';
            if (cityInput) cityInput.value = cityLabel;
            if (selectedCityName) selectedCityName.textContent = cityLabel;
            if (selectedLocation) selectedLocation.style.display = 'block';
            if (manualLocationContainer) manualLocationContainer.style.display = 'none';
            if (predictBtn) predictBtn.style.display = 'inline-flex';
            showToast('Location detected. Ready to analyze.');
          } catch (err) {
            console.error('Geolocation processing error:', err);
            showToast('Unable to process location. Use manual entry.');
          } finally {
            locationBtn.disabled = false;
            locationBtn.textContent = '📍 Use Live Location';
          }
        },
        function(error) {
          console.error('Geolocation error:', error);
          showToast('Location unavailable. Use manual entry.');
          locationBtn.disabled = false;
          locationBtn.textContent = '📍 Use Live Location';
          if (manualLocationContainer && manualLocationContainer.style.display === 'none') {
            manualLocationContainer.style.display = 'block';
            if (cityInput) cityInput.focus();
          }
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // City Input Change — Show selected location when user picks from list
  // ─────────────────────────────────────────────────────────────────────────
  if (cityInput) {
    cityInput.addEventListener("change", function() {
      const city = cityInput.value.trim();
      gpsCoords = null;
      if (city) {
        if (selectedCityName) selectedCityName.textContent = city;
        if (selectedLocation) selectedLocation.style.display = "block";
        if (predictBtn) predictBtn.style.display = "inline-flex";
      }
    });

    // Also trigger on Enter key
    cityInput.addEventListener("keypress", function(e) {
      if (e.key === "Enter") {
        e.preventDefault();
        const city = cityInput.value.trim();
        if (city) {
          if (selectedCityName) selectedCityName.textContent = city;
          if (selectedLocation) selectedLocation.style.display = "block";
          if (predictBtn) predictBtn.style.display = "inline-flex";
        }
      }
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUTTON 3: "Analyze Solar Potential" — real backend, no demo fallback
  // ─────────────────────────────────────────────────────────────────────────
  if (predictBtn) {
    predictBtn.addEventListener('click', async function () {
      var city = (cityInput && cityInput.value.trim()) || '';
      if (!city) {
        showToast('Please select or enter a location first');
        return;
      }

      predictBtn.disabled = true;
      var originalHTML = predictBtn.innerHTML;
      predictBtn.innerHTML = '<span style="margin-right:8px;">⏳</span>Analyzing...';

      try {
        // Step 1: Fetch live weather for the selected location.
        // GPS mode uses coordinates; manual mode uses city name.
        var weatherUrl = gpsCoords
          ? `https://api.openweathermap.org/data/2.5/weather?lat=${gpsCoords.lat}&lon=${gpsCoords.lon}&appid=${WEATHER_API_KEY}&units=metric`
          : `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${WEATHER_API_KEY}&units=metric`;

        var weatherResponse;
        try {
          weatherResponse = await fetch(weatherUrl, { cache: 'no-store' });
        } catch (networkErr) {
          console.error('Weather fetch network error:', networkErr);
          showToast('Network error — could not reach weather service. Check your connection.', 5000);
          return;
        }

        if (!weatherResponse.ok) {
          var errMsg = weatherResponse.status === 404
            ? `Location "${city}" not found. Try a different city name.`
            : `Weather service error (${weatherResponse.status}). Please try again.`;
          showToast(errMsg, 5000);
          return;
        }

        var weatherData = await weatherResponse.json();
        console.log('Weather data fetched:', weatherData);

        // Step 2: POST all parameters to the real /predict-solar backend.
        var latitude  = gpsCoords ? gpsCoords.lat : weatherData.coord.lat;
        var longitude = gpsCoords ? gpsCoords.lon : weatherData.coord.lon;
        var temperature = weatherData.main.temp;
        var humidity    = weatherData.main.humidity;
        var wind_speed  = (weatherData.wind && weatherData.wind.speed) || 0;

        var predictionResp;
        try {
          predictionResp = await fetch(`${API_BASE_URL}/predict-solar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude, longitude, temperature, humidity, wind_speed })
          });
        } catch (networkErr) {
          console.error('Prediction fetch network error:', networkErr);
          showToast('Network error — could not reach prediction service. Check your connection.', 5000);
          return;
        }

        if (!predictionResp.ok) {
          var errData = {};
          try { errData = await predictionResp.json(); } catch (e) {}
          var hint = errData.hint ? ' ' + errData.hint : '';
          showToast((errData.error || `Prediction failed (${predictionResp.status}).`) + hint, 5000);
          return;
        }

        var result = await predictionResp.json();

        if (result.error) {
          showToast(result.error, 5000);
          return;
        }

        // Step 3: Update all dashboard cards and persist the result.
        updateDashboardCards(result);
        try { localStorage.setItem('solarPrediction', JSON.stringify(result)); } catch (e) { console.warn('Could not save prediction', e); }
        showToast('Prediction generated successfully.');

      } catch (err) {
        console.error('Unexpected prediction error:', err);
        showToast('An unexpected error occurred. Please try again.', 5000);
      } finally {
        predictBtn.disabled = false;
        predictBtn.innerHTML = originalHTML;
      }
    });
  }

  loadStoredPrediction();
}

// ============================================================================
// Update Dashboard Cards with Backend Results
// ============================================================================
function updateDashboardCards(result) {
  if (!result || typeof result !== 'object') {
    console.warn("No prediction result available");
    result = {};
  }

  var ELECTRICITY_TARIFF_INR = 7;
  var CO2_TONS_PER_MWH = 1.04;

  var annualKwh = result.annual_projection != null ? Number(result.annual_projection) : null;
  var estimatedSavingsValue = annualKwh != null
    ? '₹' + Math.round(annualKwh * ELECTRICITY_TARIFF_INR).toLocaleString('en-IN') + '/year'
    : 'N/A';
  var co2Value = annualKwh != null
    ? ((annualKwh / 1000) * CO2_TONS_PER_MWH).toFixed(1) + ' tons/year'
    : 'N/A';

  const updates = {
    "potentialScore": {
      value: result.potential_score != null ? `${result.potential_score}` : "N/A",
      element: document.getElementById("potentialScore")
    },
    "peakSunHours": {
      value: result.peak_sun_hours != null ? `${result.peak_sun_hours} hrs/day` : "N/A",
      element: document.getElementById("peakSunHours")
    },
    "solarCapacity": {
      value: result.recommended_capacity != null ? `${result.recommended_capacity} kW` : "N/A",
      element: document.getElementById("solarCapacity")
    },
    "panelCount": {
      value: result.panel_count != null ? `${result.panel_count} Panels` : "N/A",
      element: document.getElementById("panelCount")
    },
    "energyCoverage": {
      value: result.energy_coverage != null ? `${result.energy_coverage}%` : "N/A",
      element: document.getElementById("energyCoverage")
    },
    "annualProjection": {
      value: annualKwh != null ? `${annualKwh} kWh/year` : "N/A",
      element: document.getElementById("annualProjection")
    },
    "estimatedSavings": {
      value: estimatedSavingsValue,
      element: document.getElementById("estimatedSavings")
    },
    "co2Reduction": {
      value: co2Value,
      element: document.getElementById("co2Reduction")
    }
  };

  for (const [key, data] of Object.entries(updates)) {
    if (data.element) {
      data.element.textContent = data.value;
      console.log(`Updated ${key}:`, data.value);
    } else {
      console.warn(`DOM element not found for ${key}`);
    }
  }

  const progressElement = document.getElementById("suitabilityProgress");
  if (progressElement && typeof result.potential_score === 'number') {
    progressElement.style.width = `${Math.min(100, Math.max(0, result.potential_score))}%`;
  }

  if (result.monthly_generation && typeof result.monthly_generation === 'object') {
    // Dashboard bar chart — Jan through Jun
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
    const barElements = document.querySelectorAll('.chart-bar');
    const values = months.map((m) => parseFloat(result.monthly_generation[m] || 0));
    const maxValue = Math.max(...values, 1);
    barElements.forEach(function (bar, index) {
      if (bar) {
        const height = Math.round((values[index] || 0) / maxValue * 100);
        bar.style.height = `${height}%`;
      }
    });

    // Prediction page quarterly bar chart — Q1..Q4 from monthly_generation
    var quarters = [
      ['Jan', 'Feb', 'Mar'],
      ['Apr', 'May', 'Jun'],
      ['Jul', 'Aug', 'Sep'],
      ['Oct', 'Nov', 'Dec']
    ];
    var qLabels = ['Q1', 'Q2', 'Q3', 'Q4'];
    var qTotals = quarters.map(function (ms) {
      return ms.reduce(function (sum, m) { return sum + (parseFloat(result.monthly_generation[m]) || 0); }, 0);
    });
    var maxQ = Math.max.apply(null, qTotals.concat([1]));
    var predBars   = document.querySelectorAll('.prediction-chart-bar__col');
    var predLabels = document.querySelectorAll('.prediction-chart-bar .chart-label');
    predBars.forEach(function (bar, i) {
      if (i < qTotals.length) {
        bar.style.height = Math.round((qTotals[i] / maxQ) * 100) + '%';
      }
    });
    predLabels.forEach(function (label, i) {
      if (i < qLabels.length) {
        label.textContent = qLabels[i];
        label.className = 'chart-label' + (i === 3 ? ' text-accent text-bold' : '');
      }
    });
  }

  const user = getSavedUser();
  if (user && user.name) {
    const userNameDisplay = document.getElementById('userNameDisplay');
    if (userNameDisplay) {
      userNameDisplay.textContent = user.name;
    }
  }

  console.log("All prediction data:", result);
}