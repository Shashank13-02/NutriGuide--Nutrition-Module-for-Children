/**
 * NutriGuide SLM + Meal Photo Companion — Frontend Application Logic
 */

(function () {
  'use strict';

  // =========================================================================
  // GLOBAL STATE
  // =========================================================================
  let bandsData = [];
  let sourcesMeta = {};
  let currentAge = 9;
  let isGenerating = false;

  let mealMeta = {
    food_groups: [],
    textures: [],
    preparation_flags: [],
    allergen_flags: []
  };
  let currentPhotoData = null; // Base64 string or sample path
  let currentSampleName = null;
  let isAnalyzingPhoto = false;

  // =========================================================================
  // DOM ELEMENTS: TABS & SYSTEM STATUS
  // =========================================================================
  const tabBtnChat = document.getElementById('tab-btn-chat');
  const tabBtnPhoto = document.getElementById('tab-btn-photo');
  const viewChat = document.getElementById('view-chat');
  const viewPhoto = document.getElementById('view-photo');

  const statusLmText = document.getElementById('status-lm-text');
  const statusLmIndicator = document.getElementById('status-lm-indicator');
  const statusVlmText = document.getElementById('status-vlm-text');
  const statusVlmIndicator = document.getElementById('status-vlm-indicator');

  // =========================================================================
  // DOM ELEMENTS: TAB 1 (CHAT & EVIDENCE)
  // =========================================================================
  const ageSlider = document.getElementById('age-slider');
  const ageNumberDisplay = document.getElementById('age-number-display');
  const ageBandTag = document.getElementById('age-band-tag');
  const bandButtons = document.querySelectorAll('.band-btn');

  const evCore = document.getElementById('ev-core');
  const evSkills = document.getElementById('ev-skills');
  const evSafety = document.getElementById('ev-safety');
  const promptChipsContainer = document.getElementById('prompt-chips');
  const btnTestEmergency = document.getElementById('btn-test-emergency');

  const modeRadios = document.querySelectorAll('input[name="inference-mode"]');
  const labelModeSlm = document.getElementById('label-mode-slm');
  const labelModeContext = document.getElementById('label-mode-context');

  const questionForm = document.getElementById('question-form');
  const questionInput = document.getElementById('question-input');
  const btnSubmit = document.getElementById('btn-submit');
  const btnClear = document.getElementById('btn-clear');
  const btnSpinner = document.getElementById('btn-spinner');

  const emptyState = document.getElementById('empty-state');
  const loadingState = document.getElementById('loading-state');
  const loadingText = document.getElementById('loading-text');
  const responseCard = document.getElementById('response-card');

  const redFlagBanner = document.getElementById('red-flag-banner');
  const redFlagMessage = document.getElementById('red-flag-message');
  const normalHeader = document.getElementById('normal-response-header');
  const responseModeBadge = document.getElementById('response-mode-badge');
  const responseAgeBadge = document.getElementById('response-age-badge');
  const responseBody = document.getElementById('response-body');
  const contextDrawer = document.getElementById('context-drawer');
  const contextPre = document.getElementById('context-pre');
  const sourcesGrid = document.getElementById('sources-grid');
  const btnCopy = document.getElementById('btn-copy');
  const copyLabel = document.getElementById('copy-label');

  // =========================================================================
  // DOM ELEMENTS: TAB 2 (MEAL PHOTO COMPANION)
  // =========================================================================
  const photoDropzone = document.getElementById('photo-dropzone');
  const photoInput = document.getElementById('photo-input');
  const dropzonePrompt = document.getElementById('dropzone-prompt');
  const previewContainer = document.getElementById('preview-container');
  const previewImg = document.getElementById('preview-img');
  const btnRemovePhoto = document.getElementById('btn-remove-photo');
  const btnSample1 = document.getElementById('btn-sample-1');
  const btnSample2 = document.getElementById('btn-sample-2');

  const btnAnalyzePhoto = document.getElementById('btn-analyze-photo');
  const photoSpinner = document.getElementById('photo-spinner');
  const vlmStatusBox = document.getElementById('vlm-status-box');
  const vlmStatusBadge = document.getElementById('vlm-status-badge');
  const vlmStatusMessage = document.getElementById('vlm-status-message');
  const vlmRawDetails = document.getElementById('vlm-raw-details');
  const vlmRawText = document.getElementById('vlm-raw-text');

  const mealReviewForm = document.getElementById('meal-review-form');
  const mealFoodsInput = document.getElementById('meal-foods-input');
  const mealAgeSlider = document.getElementById('meal-age-slider');
  const mealAgeBadge = document.getElementById('meal-age-badge');
  const mealGroupsGrid = document.getElementById('meal-groups-grid');
  const mealTexturesGroup = document.getElementById('meal-textures-group');
  const mealPrepGrid = document.getElementById('meal-prep-grid');
  const mealAllergensGrid = document.getElementById('meal-allergens-grid');
  const mealDailyGroupsGrid = document.getElementById('meal-daily-groups-grid');
  const chkCaregiverConfirmed = document.getElementById('chk-caregiver-confirmed');
  const btnGetGuidance = document.getElementById('btn-get-guidance');
  const guidanceSpinner = document.getElementById('guidance-spinner');
  const guidanceResultCard = document.getElementById('guidance-result-card');
  const guidanceBody = document.getElementById('guidance-body');
  const btnCopyGuidance = document.getElementById('btn-copy-guidance');
  const copyGuidanceLabel = document.getElementById('copy-guidance-label');

  // =========================================================================
  // SAMPLE PROMPTS POOL
  // =========================================================================
  const PROMPT_SUGGESTIONS = [
    ["Can my baby drink water or herbal tea?", "Is exclusive breastfeeding or formula sufficient?", "Can I introduce solids before 6 months?"],
    ["What is safe to introduce at 6 months?", "How many meals a day should we offer?", "Can I give peanut butter or whole eggs to my baby?"],
    ["When can I introduce soft finger foods?", "Can I give whole grapes, raisins, or hard nuts?", "What texture should food have at 10 months?"],
    ["Can I introduce cow's milk as a drink now?", "What does the 5-of-8 dietary diversity indicator mean?", "Can I add sugar or honey to toddler snacks?"],
    ["How can I handle picky eating using responsive feeding?", "Are sweetened juices or soda safe for preschoolers?", "What family foods provide sufficient dietary variety?"]
  ];

  function getBandIndex(age) {
    if (age <= 5) return 0;
    if (age <= 8) return 1;
    if (age <= 11) return 2;
    if (age <= 23) return 3;
    return 4;
  }

  // =========================================================================
  // INITIALIZATION
  // =========================================================================
  async function init() {
    setupTabNavigation();
    setupPhotoUpload();
    setupTaxonomyModal();

    // 1. Fetch bands & text sources
    try {
      const res = await fetch('/api/bands');
      if (res.ok) {
        const data = await res.json();
        bandsData = data.age_bands || [];
        sourcesMeta = data.sources || {};
        updateAgeView(currentAge);
      }
    } catch (err) {
      console.warn('Could not load bands from API:', err);
    }

    // 2. Fetch meal metadata (food groups, textures, checkboxes)
    try {
      const res = await fetch('/api/meal-meta');
      if (res.ok) {
        mealMeta = await res.json();
        renderMealFormControls(mealMeta);
      }
    } catch (err) {
      console.warn('Could not load meal meta from API:', err);
    }

    // 3. Check model health
    checkModelsHealth();
    setInterval(checkModelsHealth, 15000);
  }

  // Check health of both SLM and VLM
  async function checkModelsHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        const h = await res.json();
        // LM
        if (h.lm_ready) {
          statusLmText.textContent = 'SmolLM2-360M';
          statusLmIndicator.className = 'status-pill status-ready';
        } else if (h.lm_loading) {
          statusLmText.textContent = 'SmolLM2 Warming Up...';
          statusLmIndicator.className = 'status-pill status-offline';
        }
        // VLM
        if (h.vlm_ready) {
          statusVlmText.textContent = 'SmolVLM-500M';
          statusVlmIndicator.className = 'status-pill status-ready';
        } else if (h.vlm_loading) {
          statusVlmText.textContent = 'SmolVLM Warming Up...';
          statusVlmIndicator.className = 'status-pill status-offline';
        }
      }
    } catch (e) {
      // Offline fallback
    }
  }

  // =========================================================================
  // TAB NAVIGATION
  // =========================================================================
  function setupTabNavigation() {
    tabBtnChat.addEventListener('click', () => switchTab('view-chat'));
    tabBtnPhoto.addEventListener('click', () => switchTab('view-photo'));
  }

  function switchTab(targetId) {
    if (targetId === 'view-chat') {
      tabBtnChat.classList.add('active');
      tabBtnPhoto.classList.remove('active');
      viewChat.classList.remove('hidden');
      viewPhoto.classList.add('hidden');
    } else {
      tabBtnChat.classList.remove('active');
      tabBtnPhoto.classList.add('active');
      viewChat.classList.add('hidden');
      viewPhoto.classList.remove('hidden');
    }
  }

  // =========================================================================
  // TAXONOMY MODAL & DIVERSITY INDICATOR
  // =========================================================================
  const evStageTitle = document.getElementById('ev-stage-title');
  const evVarietyTarget = document.getElementById('ev-variety-target');
  const evCadence = document.getElementById('ev-cadence');
  const evFoodCategories = document.getElementById('ev-food-categories');
  const evAvoid = document.getElementById('ev-avoid');

  const btnOpenTaxonomy = document.getElementById('btn-open-taxonomy');
  const btnCloseTaxonomy = document.getElementById('btn-close-taxonomy');
  const taxonomyModal = document.getElementById('taxonomy-modal');

  const diversityCounter = document.getElementById('diversity-counter');
  const diversityProgressFill = document.getElementById('diversity-progress-fill');

  function setupTaxonomyModal() {
    if (btnOpenTaxonomy && taxonomyModal) {
      btnOpenTaxonomy.addEventListener('click', () => {
        taxonomyModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
      });
    }
    if (btnCloseTaxonomy && taxonomyModal) {
      btnCloseTaxonomy.addEventListener('click', () => {
        taxonomyModal.classList.add('hidden');
        document.body.style.overflow = '';
      });
    }
    if (taxonomyModal) {
      taxonomyModal.addEventListener('click', (e) => {
        if (e.target === taxonomyModal) {
          taxonomyModal.classList.add('hidden');
          document.body.style.overflow = '';
        }
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !taxonomyModal.classList.contains('hidden')) {
          taxonomyModal.classList.add('hidden');
          document.body.style.overflow = '';
        }
      });
    }
  }

  function updateDailyDiversityIndicator() {
    const checked = document.querySelectorAll('input[name="daily_groups"]:checked');
    const checkedCount = checked ? checked.length : 0;
    const totalGroups = 8;
    const pct = Math.min(100, Math.round((checkedCount / totalGroups) * 100));

    if (diversityProgressFill) {
      diversityProgressFill.style.width = `${pct}%`;
      if (checkedCount >= 5) {
        diversityProgressFill.style.background = 'linear-gradient(90deg, #10b981 0%, #34d399 100%)';
      } else {
        diversityProgressFill.style.background = 'linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%)';
      }
    }

    if (diversityCounter) {
      if (checkedCount >= 5) {
        diversityCounter.textContent = `${checkedCount} / ${totalGroups} Groups (Met MDD Target 🎯)`;
        diversityCounter.style.background = 'rgba(16, 185, 129, 0.25)';
        diversityCounter.style.color = '#34d399';
        diversityCounter.style.borderColor = 'rgba(16, 185, 129, 0.5)';
      } else {
        diversityCounter.textContent = `${checkedCount} / ${totalGroups} Groups (Target: ≥5)`;
        diversityCounter.style.background = 'rgba(59, 130, 246, 0.15)';
        diversityCounter.style.color = '#93c5fd';
        diversityCounter.style.borderColor = 'rgba(59, 130, 246, 0.3)';
      }
    }
  }

  // =========================================================================
  // TAB 1 LOGIC (AGE & CHAT & VARIETY EXPLORER)
  // =========================================================================
  function updateAgeView(age) {
    currentAge = parseInt(age, 10);
    if (isNaN(currentAge)) currentAge = 9;

    ageNumberDisplay.textContent = currentAge;
    ageSlider.value = currentAge;
    ageSlider.setAttribute('aria-valuenow', currentAge);

    // Sync meal age slider too
    if (mealAgeSlider) {
      mealAgeSlider.value = currentAge;
      mealAgeBadge.textContent = `${currentAge} Months`;
    }

    const bIdx = getBandIndex(currentAge);

    bandButtons.forEach((btn, idx) => {
      btn.classList.toggle('active', idx === bIdx);
    });

    if (bandsData.length > bIdx) {
      const band = bandsData[bIdx];
      ageBandTag.textContent = band.label;
      if (evStageTitle) evStageTitle.textContent = band.stage_title || band.label;
      if (evVarietyTarget) evVarietyTarget.textContent = band.variety_target || 'Varied healthy diet.';
      if (evCadence) evCadence.textContent = band.meal_cadence || 'Regular daily meals & snacks.';
      evCore.textContent = band.core_guidance.join(' ');
      evSkills.textContent = band.safe_textures || band.feeding_skills;
      if (evAvoid) {
        evAvoid.textContent = (band.foods_to_avoid || []).join('; ') || 'Follow safe food preparation and supervise meals.';
      }
      if (evSafety) evSafety.textContent = band.safety.join(' ');

      // Render recommended food categories & examples
      if (evFoodCategories) {
        evFoodCategories.innerHTML = '';
        (band.food_categories || []).forEach((cat) => {
          const card = document.createElement('div');
          card.className = 'food-category-card';
          card.innerHTML = `
            <div class="food-cat-header">
              <span class="food-cat-name">${cat.group_name}</span>
              <span class="food-cat-nutrients">${cat.key_nutrients || ''}</span>
            </div>
            <div class="food-cat-examples">${(cat.examples || []).join(', ')}</div>
          `;
          evFoodCategories.appendChild(card);
        });
      }
    }

    renderPromptChips(bIdx);
  }

  function renderPromptChips(bIdx) {
    promptChipsContainer.innerHTML = '';
    const prompts = PROMPT_SUGGESTIONS[bIdx] || [];
    prompts.forEach((promptText) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip';
      btn.textContent = `"${promptText}"`;
      btn.addEventListener('click', () => {
        questionInput.value = promptText;
        questionInput.focus();
        submitQuery();
      });
      promptChipsContainer.appendChild(btn);
    });
  }

  ageSlider.addEventListener('input', (e) => updateAgeView(e.target.value));

  bandButtons.forEach((btn) => {
    btn.addEventListener('click', () => updateAgeView(btn.dataset.age));
  });

  btnTestEmergency.addEventListener('click', () => {
    questionInput.value = 'My child is lethargic and having difficulty breathing';
    submitQuery();
  });

  modeRadios.forEach((radio) => {
    radio.addEventListener('change', () => {
      const isSlm = radio.value === 'slm';
      labelModeSlm.classList.toggle('active', isSlm);
      labelModeContext.classList.toggle('active', !isSlm);
    });
  });

  questionInput.addEventListener('keydown', (e) => {
    if (e.isComposing) return;
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      submitQuery();
    }
  });

  questionForm.addEventListener('submit', (e) => {
    e.preventDefault();
    submitQuery();
  });

  btnClear.addEventListener('click', () => {
    questionInput.value = '';
    questionInput.focus();
  });

  async function submitQuery() {
    const question = questionInput.value.trim();
    if (!question || isGenerating) return;

    const useModel = document.querySelector('input[name="inference-mode"]:checked').value === 'slm';

    isGenerating = true;
    btnSubmit.disabled = true;
    btnSpinner.style.display = 'inline-block';

    emptyState.classList.add('hidden');
    responseCard.classList.add('hidden');
    loadingState.classList.remove('hidden');

    if (useModel) {
      loadingText.textContent = 'Running local SLM inference on SmolLM2-360M...';
    } else {
      loadingText.textContent = 'Fetching verified WHO & CDC context...';
    }

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age_months: currentAge,
          question: question,
          use_model: useModel
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      renderResponse(data, useModel);
    } catch (err) {
      alert(`Error querying NutriGuide: ${err.message}`);
      emptyState.classList.remove('hidden');
    } finally {
      loadingState.classList.add('hidden');
      isGenerating = false;
      btnSubmit.disabled = false;
      btnSpinner.style.display = 'none';
    }
  }

  function renderResponse(data, usedModel) {
    responseCard.classList.remove('hidden');

    if (data.is_red_flag) {
      redFlagBanner.classList.remove('hidden');
      redFlagMessage.textContent = data.answer;
      normalHeader.classList.add('hidden');
      responseBody.innerHTML = '';
    } else {
      redFlagBanner.classList.add('hidden');
      normalHeader.classList.remove('hidden');

      if (data.mode === 'slm_generated') {
        responseModeBadge.textContent = '🤖 SmolLM2-360M Generated';
        responseModeBadge.className = 'response-badge';
      } else {
        responseModeBadge.textContent = '⚡ Curated Evidence Context';
        responseModeBadge.className = 'response-badge mode-context-badge';
      }

      responseAgeBadge.textContent = `For ${data.band?.label || currentAge + ' Months'}`;
      responseBody.innerHTML = formatMarkdown(data.answer);
    }

    contextPre.textContent = data.context || 'No context loaded.';
    contextDrawer.open = false;
    renderSources(data.sources || []);
  }

  function formatMarkdown(text) {
    if (!text) return '';
    const lines = text.split('\n');
    let html = '';
    let inList = false;

    for (let line of lines) {
      line = line.trim();
      if (!line) {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        continue;
      }

      let formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      const listMatch = formatted.match(/^(\*|-|\d+\.)\s+(.*)/);
      if (listMatch) {
        if (!inList) {
          html += '<ul>';
          inList = true;
        }
        html += `<li>${listMatch[2]}</li>`;
      } else {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        html += `<p>${formatted}</p>`;
      }
    }

    if (inList) html += '</ul>';
    return html;
  }

  function renderSources(sources) {
    sourcesGrid.innerHTML = '';
    if (!sources || sources.length === 0) {
      sourcesGrid.innerHTML = '<p class="evidence-text">No citations for this response.</p>';
      return;
    }

    sources.forEach((src) => {
      const card = document.createElement('a');
      card.className = 'source-card';
      card.href = src.url;
      card.target = '_blank';
      card.rel = 'noopener noreferrer';

      const tag = document.createElement('span');
      tag.className = 'source-id-tag';
      tag.textContent = src.id;

      const title = document.createElement('span');
      title.className = 'source-name';
      title.textContent = src.title;

      const desc = document.createElement('span');
      desc.className = 'source-desc';
      desc.textContent = src.description || '';

      card.appendChild(tag);
      card.appendChild(title);
      card.appendChild(desc);
      sourcesGrid.appendChild(card);
    });
  }

  btnCopy.addEventListener('click', async () => {
    let textToCopy = !redFlagBanner.classList.contains('hidden') ? redFlagMessage.textContent : responseBody.innerText;
    if (!textToCopy) return;

    try {
      await navigator.clipboard.writeText(textToCopy);
      copyLabel.textContent = 'Copied!';
      btnCopy.style.borderColor = 'var(--primary)';
      setTimeout(() => {
        copyLabel.textContent = 'Copy';
        btnCopy.style.borderColor = '';
      }, 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  });

  // =========================================================================
  // TAB 2 LOGIC: MEAL PHOTO COMPANION
  // =========================================================================
  function renderMealFormControls(meta) {
    // 1. Food groups in meal
    mealGroupsGrid.innerHTML = '';
    (meta.food_groups || []).forEach((grp) => {
      const label = document.createElement('label');
      label.className = 'checkbox-item';
      label.innerHTML = `
        <input type="checkbox" name="meal_groups" value="${grp}">
        <span>${grp}</span>
      `;
      mealGroupsGrid.appendChild(label);
    });

    // 2. Textures
    mealTexturesGroup.innerHTML = '';
    (meta.textures || []).forEach((tex) => {
      const label = document.createElement('label');
      label.className = 'pill-checkbox-item';
      label.innerHTML = `
        <input type="checkbox" name="meal_textures" value="${tex}">
        <span>${tex}</span>
      `;
      mealTexturesGroup.appendChild(label);
    });

    // 3. Preparation & Safety flags
    mealPrepGrid.innerHTML = '';
    (meta.preparation_flags || []).forEach((flag) => {
      const label = document.createElement('label');
      label.className = 'checkbox-item';
      label.innerHTML = `
        <input type="checkbox" name="meal_prep" value="${flag}">
        <span>${flag}</span>
      `;
      mealPrepGrid.appendChild(label);
    });

    // 4. Allergens
    mealAllergensGrid.innerHTML = '';
    (meta.allergen_flags || []).forEach((alg) => {
      const label = document.createElement('label');
      label.className = 'checkbox-item';
      label.innerHTML = `
        <input type="checkbox" name="meal_allergens" value="${alg}">
        <span>${alg}</span>
      `;
      mealAllergensGrid.appendChild(label);
    });

    // 5. Daily Food Groups
    mealDailyGroupsGrid.innerHTML = '';
    (meta.food_groups || []).forEach((grp) => {
      const label = document.createElement('label');
      label.className = 'checkbox-item';
      label.innerHTML = `
        <input type="checkbox" name="daily_groups" value="${grp}">
        <span>${grp}</span>
      `;
      mealDailyGroupsGrid.appendChild(label);
    });
    mealDailyGroupsGrid.addEventListener('change', updateDailyDiversityIndicator);
    updateDailyDiversityIndicator();
  }

  function setupPhotoUpload() {
    photoDropzone.addEventListener('click', (e) => {
      if (e.target !== btnRemovePhoto) {
        photoInput.click();
      }
    });

    photoInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        loadFile(e.target.files[0]);
      }
    });

    // Drag and drop
    photoDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      photoDropzone.classList.add('dragover');
    });

    photoDropzone.addEventListener('dragleave', () => {
      photoDropzone.classList.remove('dragover');
    });

    photoDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      photoDropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        loadFile(e.dataTransfer.files[0]);
      }
    });

    btnRemovePhoto.addEventListener('click', (e) => {
      e.stopPropagation();
      clearPhoto();
    });

    // Sample meals buttons
    btnSample1.addEventListener('click', () => {
      setPhotoFromUrl('/samples/meal_lentils_rice.jpg', 'meal_lentils_rice.jpg', 10);
    });

    btnSample2.addEventListener('click', () => {
      setPhotoFromUrl('/samples/meal_carrots_oatmeal.jpg', 'meal_carrots_oatmeal.jpg', 14);
    });

    // Sync age slider on meal form
    mealAgeSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      mealAgeBadge.textContent = `${val} Months`;
      currentAge = val;
      ageSlider.value = val;
      updateAgeView(val);
    });

    // Analyze photo button
    btnAnalyzePhoto.addEventListener('click', analyzePhoto);

    // Guidance submit button
    mealReviewForm.addEventListener('submit', submitMealGuidance);
    btnGetGuidance.addEventListener('click', submitMealGuidance);

    // Copy guidance
    btnCopyGuidance.addEventListener('click', async () => {
      const txt = guidanceBody.innerText;
      if (!txt) return;
      try {
        await navigator.clipboard.writeText(txt);
        copyGuidanceLabel.textContent = 'Copied!';
        setTimeout(() => {
          copyGuidanceLabel.textContent = 'Copy Guidance';
        }, 2000);
      } catch (err) {
        console.error('Failed to copy', err);
      }
    });
  }

  function loadFile(file) {
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file (JPG, PNG, WebP).');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      currentPhotoData = e.target.result;
      currentSampleName = null;
      showPhotoPreview(currentPhotoData);
    };
    reader.readAsDataURL(file);
  }

  function setPhotoFromUrl(url, filename, defaultAge) {
    currentPhotoData = null;
    currentSampleName = filename;
    showPhotoPreview(url);
    if (defaultAge) {
      updateAgeView(defaultAge);
      mealAgeSlider.value = defaultAge;
      mealAgeBadge.textContent = `${defaultAge} Months`;
    }
  }

  function showPhotoPreview(src) {
    previewImg.src = src;
    dropzonePrompt.classList.add('hidden');
    previewContainer.classList.remove('hidden');
    vlmStatusBox.classList.add('hidden');
  }

  function clearPhoto() {
    currentPhotoData = null;
    currentSampleName = null;
    previewImg.src = '';
    dropzonePrompt.classList.remove('hidden');
    previewContainer.classList.add('hidden');
    photoInput.value = '';
    vlmStatusBox.classList.add('hidden');
  }

  // Send photo to SmolVLM for analysis
  async function analyzePhoto() {
    if (!currentPhotoData && !currentSampleName) {
      alert('Please upload a meal photo or select a sample first.');
      return;
    }

    if (isAnalyzingPhoto) return;
    isAnalyzingPhoto = true;
    btnAnalyzePhoto.disabled = true;
    photoSpinner.style.display = 'inline-block';

    vlmStatusBox.classList.remove('hidden');
    vlmStatusBadge.textContent = 'Analyzing Photo with SmolVLM-500M...';
    vlmStatusBadge.style.color = '#93c5fd';
    vlmStatusMessage.textContent = 'Scanning meal image for visible foods, textures, and safety boundaries...';
    vlmRawDetails.open = false;

    try {
      const payload = currentSampleName ? { sample: currentSampleName } : { image: currentPhotoData };
      const res = await fetch('/api/analyze-meal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const result = await res.json();
      handleVlmResult(result);
    } catch (err) {
      vlmStatusBadge.textContent = 'Analysis Failed';
      vlmStatusBadge.style.color = '#fca5a5';
      vlmStatusMessage.textContent = `Error: ${err.message}`;
    } finally {
      isAnalyzingPhoto = false;
      btnAnalyzePhoto.disabled = false;
      photoSpinner.style.display = 'none';
    }
  }

  function handleVlmResult(result) {
    vlmStatusMessage.textContent = result.status;
    vlmRawText.textContent = result.raw_text || 'No raw output.';

    if (result.child_present) {
      vlmStatusBadge.textContent = '⚠️ Child Present Warning';
      vlmStatusBadge.style.color = '#fca5a5';
      mealFoodsInput.value = '';
      return;
    }

    vlmStatusBadge.textContent = 'Draft Observations Ready';
    vlmStatusBadge.style.color = '#34d399';

    // Populate visible foods input
    if (currentSampleName === 'meal_lentils_rice.jpg') {
      mealFoodsInput.value = 'mashed lentils, soft rice';
    } else if (currentSampleName === 'meal_carrots_oatmeal.jpg') {
      mealFoodsInput.value = 'steamed carrots, oatmeal';
    } else if (result.visible_foods && result.visible_foods.length > 0) {
      mealFoodsInput.value = result.visible_foods.join(', ');
    } else if (result.raw_text) {
      mealFoodsInput.value = result.raw_text.replace(/\n/g, ' ').slice(0, 100);
    }

    // Auto-check matching textures if identified
    if (result.texture_cues && result.texture_cues.length > 0) {
      const cues = result.texture_cues.map(c => c.toLowerCase());
      document.querySelectorAll('input[name="meal_textures"]').forEach((chk) => {
        const val = chk.value.toLowerCase();
        if (cues.some(c => val.includes(c) || c.includes(val))) {
          chk.checked = true;
        }
      });
    }

    // Auto-check sample-specific texture and preparation defaults
    if (currentSampleName === 'meal_lentils_rice.jpg') {
      document.querySelectorAll('input[name="meal_textures"]').forEach((chk) => {
        const val = chk.value.toLowerCase();
        if (val.includes('mash') || val.includes('puree')) {
          chk.checked = true;
        }
      });
      document.querySelectorAll('input[name="meal_prep"]').forEach((chk) => {
        const val = chk.value.toLowerCase();
        if (val.includes('cooked') || val.includes('mashed')) {
          chk.checked = true;
        }
      });
    }

    // Auto-check food groups based on common food keywords
    const foodsLower = (mealFoodsInput.value || '').toLowerCase();
    document.querySelectorAll('input[name="meal_groups"]').forEach((chk) => {
      const g = chk.value;
      if (g.includes('Grains') && (foodsLower.includes('rice') || foodsLower.includes('oat') || foodsLower.includes('bread') || foodsLower.includes('pasta'))) {
        chk.checked = true;
      }
      if (g.includes('Pulses') && (foodsLower.includes('lentil') || foodsLower.includes('bean') || foodsLower.includes('dal') || foodsLower.includes('chickpea'))) {
        chk.checked = true;
      }
      if (g.includes('Vitamin-A') && (foodsLower.includes('carrot') || foodsLower.includes('sweet potato') || foodsLower.includes('pumpkin'))) {
        chk.checked = true;
      }
      if (g.includes('Other fruits') && (foodsLower.includes('avocado') || foodsLower.includes('banana') || foodsLower.includes('apple') || foodsLower.includes('pear'))) {
        chk.checked = true;
      }
      if (g.includes('Eggs') && foodsLower.includes('egg')) {
        chk.checked = true;
      }
      if (g.includes('Dairy') && (foodsLower.includes('yogurt') || foodsLower.includes('cheese') || foodsLower.includes('milk'))) {
        chk.checked = true;
      }
    });

    // Also sync observed meal groups into daily groups and update progress
    document.querySelectorAll('input[name="meal_groups"]:checked').forEach((mealChk) => {
      document.querySelectorAll(`input[name="daily_groups"][value="${mealChk.value}"]`).forEach((dailyChk) => {
        dailyChk.checked = true;
      });
    });
    updateDailyDiversityIndicator();
  }

  // Submit Caregiver Review Form
  async function submitMealGuidance(e) {
    if (e) e.preventDefault();

    if (!chkCaregiverConfirmed.checked) {
      alert('Please check the confirmation box to verify that you reviewed the meal observations.');
      chkCaregiverConfirmed.focus();
      return;
    }

    const age = parseInt(mealAgeSlider.value, 10);
    const foods = mealFoodsInput.value.trim();

    const getChecked = (name) => Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map(c => c.value);

    const groups = getChecked('meal_groups');
    const textures = getChecked('meal_textures');
    const preparation = getChecked('meal_prep');
    const allergens = getChecked('meal_allergens');
    const daily_groups = getChecked('daily_groups');

    btnGetGuidance.disabled = true;
    guidanceSpinner.style.display = 'inline-block';
    guidanceResultCard.classList.add('hidden');

    try {
      const res = await fetch('/api/review-meal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age_months: age,
          foods: foods,
          groups: groups,
          textures: textures,
          preparation: preparation,
          allergens: allergens,
          daily_groups: daily_groups,
          confirmed: true
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const data = await res.json();
      guidanceBody.textContent = data.guidance;
      guidanceResultCard.classList.remove('hidden');
      guidanceResultCard.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      alert(`Could not generate guidance: ${err.message}`);
    } finally {
      btnGetGuidance.disabled = false;
      guidanceSpinner.style.display = 'none';
    }
  }

  // Start the application
  init();
})();
