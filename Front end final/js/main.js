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
        setTimeout(function () {
          uploadBtn.innerHTML = orig;
          uploadBtn.disabled = false;
          fileName.textContent = fileInput.files[0].name + ' — Uploaded';
        }, 1200);
      });
    }
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', function () {
        var orig = analyzeBtn.innerHTML;
        analyzeBtn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Analyzing...';
        analyzeBtn.disabled = true;
        setTimeout(function () {
          analyzeBtn.innerHTML = orig;
          analyzeBtn.disabled = false;
          showEnergyOutput({
            capacity: '3 kW System',
            panels: '6 Panels',
            monthly: '360 kWh/month',
            annual: '4320 kWh/year',
            savings: '₹18,000/year'
          });
        }, 1800);
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

  async function queryHelia(question) {
    const prediction = JSON.parse(localStorage.getItem('solarPrediction') || 'null');
    const roi = JSON.parse(localStorage.getItem('solarROI') || 'null');
    logDebug('User Message:', question);
    logDebug('Prediction Data:', prediction);
    logDebug('ROI Data:', roi);

    const response = await fetch(CHAT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, prediction, roi })
    });

    if (!response.ok) {
      throw new Error('Chat API failed');
    }
    const payload = await response.json();
    logDebug('Retrieved Chunks:', payload.chunks || []);
    return payload.answer || 'I\'m sorry, I could not retrieve a response at the moment.';
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
        const answer = await queryHelia(question);
        messages.removeChild(typingIndicator);
        const aiMessage = { speaker: 'ai', text: answer };
        history.push(aiMessage);
        appendMessage(messages, aiMessage);
        saveChatHistory(history);
      } catch (error) {
        messages.removeChild(typingIndicator);
        const errorMessage = { speaker: 'ai', text: 'I\'m sorry, something went wrong while retrieving the answer. Please try again.' };
        history.push(errorMessage);
        appendMessage(messages, errorMessage);
        saveChatHistory(history);
        console.error('Chat query error:', error);
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
      updateDashboardCards(storedPrediction);
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

      // Detect permission state before requesting location
      if (navigator.permissions) {
        try {
          const permission = await navigator.permissions.query({ name: 'geolocation' });
          if (permission.state === 'denied') {
            alert(
              "❌ Location permission is blocked.\n\n" +
              "Please allow location access in your browser settings, then refresh the page.\n\n" +
              "If you prefer, use the manual search input instead."
            );
            locationBtn.disabled = false;
            locationBtn.textContent = "📍 Use Live Location";
            if (manualLocationContainer && manualLocationContainer.style.display === "none") {
              manualLocationContainer.style.display = "block";
              if (cityInput) cityInput.focus();
            }
            return;
          }
        } catch (permissionError) {
          console.warn("Permission API error:", permissionError);
        }
      }

      navigator.geolocation.getCurrentPosition(
        async function(position) {
          try {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;

            console.log("✓ Geolocation successful:", { lat, lon });

            // Fetch weather data for this location
            const weatherUrl = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${WEATHER_API_KEY}&units=metric`;
            const weatherResponse = await fetch(weatherUrl);

            if (!weatherResponse.ok) {
              throw new Error("Weather API failed: " + weatherResponse.status);
            }

            const weatherData = await weatherResponse.json();
            const cityName = weatherData.name || "Unknown Location";

            // Update UI
            if (cityInput) cityInput.value = cityName;
            if (selectedCityName) selectedCityName.textContent = cityName;
            if (selectedLocation) selectedLocation.style.display = "block";
            if (manualLocationContainer) manualLocationContainer.style.display = "none";
            if (predictBtn) predictBtn.style.display = "inline-flex";

            console.log("✓ Location selected:", cityName, `(${lat}, ${lon})`);
            alert(`✓ Location detected: ${cityName}`);
          } catch (error) {
            console.error("Error fetching weather:", error);
            alert("❌ Error fetching weather data. Please check internet and try again.");
          } finally {
            locationBtn.disabled = false;
            locationBtn.textContent = "📍 Use Live Location";
          }
        },
        function(error) {
          console.error("❌ Geolocation error:", error);
          
          let errorMsg = "Location access denied.";
          
          if (error.code === error.PERMISSION_DENIED) {
            errorMsg = "❌ PERMISSION DENIED\n\n" +
              "🔧 To Fix:\n" +
              "1. Click the 🔒 lock icon in address bar\n" +
              "2. Click 'Permissions'\n" +
              "3. Set 'Location' to 'Allow'\n" +
              "4. Refresh page (Ctrl+R)\n" +
              "5. Click 'Use Live Location' again\n\n" +
              "OR use 🔍 'Enter Location' instead (no permissions needed)";
          } else if (error.code === error.POSITION_UNAVAILABLE) {
            errorMsg = "❌ LOCATION UNAVAILABLE\n\n" +
              "🔧 To Fix:\n" +
              "1. Go to Windows Settings\n" +
              "2. Privacy & Security → Location\n" +
              "3. Turn ON 'Location services'\n" +
              "4. Turn ON 'Browser location'\n" +
              "5. Try again\n\n" +
              "OR use 🔍 'Enter Location' instead (no permissions needed)";
          } else if (error.code === error.TIMEOUT) {
            errorMsg = "❌ REQUEST TIMED OUT\n\n" +
              "Your location took too long. Please try again.\n\n" +
              "OR use 🔍 'Enter Location' instead (no permissions needed)";
          }
          
          alert(errorMsg);
          locationBtn.disabled = false;
          locationBtn.textContent = "📍 Use Live Location";
          
          // Auto-show manual location input as fallback
          if (manualLocationContainer && manualLocationContainer.style.display === "none") {
            manualLocationContainer.style.display = "block";
            if (cityInput) cityInput.focus();
          }
        }
      );
    });
  }

  // ─────────────────────────────────────────────────────────────────────────
  // City Input Change — Show selected location when user picks from list
  // ─────────────────────────────────────────────────────────────────────────
  if (cityInput) {
    cityInput.addEventListener("change", function() {
      const city = cityInput.value.trim();
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
  // BUTTON 3: "Analyze Solar Potential" — ONE consolidated listener
  // ─────────────────────────────────────────────────────────────────────────
  if (predictBtn) {
    predictBtn.addEventListener("click", async function() {
      const city = (cityInput && cityInput.value.trim()) || "";

      if (!city) {
        alert("Please select or enter a location first");
        return;
      }

      predictBtn.disabled = true;
      const originalText = predictBtn.textContent;
      predictBtn.innerHTML = '<span style="margin-right:8px;">⏳</span>Analyzing...';

      try {
        // Fetch weather data for the selected city
        const weatherUrl = `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${WEATHER_API_KEY}&units=metric`;
        const weatherResponse = await fetch(weatherUrl);

        if (!weatherResponse.ok) {
          throw new Error(`Weather API error: ${weatherResponse.status} - ${weatherResponse.statusText}`);
        }

        const weatherData = await weatherResponse.json();

        // Extract weather parameters
        const latitude = weatherData.coord.lat;
        const longitude = weatherData.coord.lon;
        const temperature = weatherData.main.temp;
        const humidity = weatherData.main.humidity;
        const wind_speed = weatherData.wind.speed || 0;

        console.log("Weather data fetched:", { city, latitude, longitude, temperature, humidity, wind_speed });

        // Send to backend prediction API
        const predictionResponse = await fetch(
          `${API_BASE_URL}/predict-solar`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              latitude,
              longitude,
              temperature,
              humidity,
              wind_speed
            })
          }
        );
        if (!predictionResponse.ok) {
          throw new Error(`Prediction API error: ${predictionResponse.status}`);
        }

        const result = await predictionResponse.json();
        console.log("Prediction result:", result);

        updateDashboardCards(result);

        try {
          localStorage.setItem("solarPrediction", JSON.stringify(result));
        } catch (storageError) {
          console.warn("Unable to save solar prediction to localStorage:", storageError);
        }

        alert(`✓ Solar analysis complete for ${city}!`);
      } catch (error) {
        console.error("Error during prediction:", error);
        alert(`Error: ${error.message}. Please try again.`);
      } finally {
        predictBtn.disabled = false;
        predictBtn.innerHTML = originalText;
      }
    });
  }

  loadStoredPrediction();
}

// ============================================================================
// Update Dashboard Cards with Backend Results
// ============================================================================
function updateDashboardCards(result) {
  // Map backend keys to DOM element IDs and format values
  const updates = {
    "potentialScore": {
      value: result.potential_score ? `${result.potential_score}` : "N/A",
      element: document.getElementById("potentialScore")
    },
    "peakSunHours": {
      value: result.peak_sun_hours ? `${result.peak_sun_hours} hrs/day` : "N/A",
      element: document.getElementById("peakSunHours")
    },
    "solarCapacity": {
      value: result.recommended_capacity ? `${result.recommended_capacity} kW` : "N/A",
      element: document.getElementById("solarCapacity")
    },
    "panelCount": {
      value: result.panel_count ? `${result.panel_count} Panels` : "N/A",
      element: document.getElementById("panelCount")
    },
    "energyCoverage": {
      value: result.energy_coverage ? `${result.energy_coverage}%` : "N/A",
      element: document.getElementById("energyCoverage")
    },
    "annualProjection": {
      value: result.annual_projection ? `${result.annual_projection} kWh/year` : "N/A",
      element: document.getElementById("annualProjection")
    }
  };

  // Update each element if it exists
  for (const [key, data] of Object.entries(updates)) {
    if (data.element) {
      data.element.textContent = data.value;
      console.log(`Updated ${key}:`, data.value);
    } else {
      console.warn(`DOM element not found for ${key}`);
    }
  }

  // Log full result for debugging
  const progressElement = document.getElementById("suitabilityProgress");
  if (progressElement && typeof result.potential_score === 'number') {
    progressElement.style.width = `${Math.min(100, Math.max(0, result.potential_score))}%`;
  }

  if (result.monthly_generation && typeof result.monthly_generation === 'object') {
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
    const barElements = document.querySelectorAll('.chart-bar');
    const values = months.map((m) => parseFloat(result.monthly_generation[m] || 0));
    const maxValue = Math.max(...values, 1);
    barElements.forEach(function (bar, index) {
      const height = Math.round((values[index] || 0) / maxValue * 100);
      bar.style.height = `${height}%`;
    });
  }

  const user = getSavedUser();
  if (user && user.name) {
    const userNameDisplay = document.getElementById('userNameDisplay');
    if (userNameDisplay) {
      userNameDisplay.textContent = user.name;
    }
  }

  // Log full result for debugging
  console.log("All prediction data:", result);
}