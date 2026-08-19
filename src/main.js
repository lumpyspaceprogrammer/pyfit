import { authenticateUser, createPatternListing, fetchGallery, getGalleryItems, listPattern, subscribeUser } from './components/api.js';
import { buildGarmentMesh, createInstructionMarkup, createThreeScene, renderGalleryCards } from './components/renderer.js';
import { closeModal, openModal, registerInstallPrompt, setUserStatus, showTabView, updateCreditUI } from './components/ui.js';

const appState = {
  credits: 1,
  isLoggedIn: false,
  userEmail: '',
  demoMode: false,
  gallery: getGalleryItems(),
  meshParams: { flare: 0.35, waistRadius: 0.65, topHeight: 1.8 }
};

const els = {
  studioView: document.getElementById('view-studio'),
  galleryView: document.getElementById('view-gallery'),
  navStudio: document.getElementById('nav-studio'),
  navGallery: document.getElementById('nav-gallery'),
  creditCountBadge: document.getElementById('credit-count-badge'),
  modalPricing: document.getElementById('modal-pricing'),
  modalAuth: document.getElementById('modal-auth'),
  authEmail: document.getElementById('auth-email'),
  imagePreview: document.getElementById('image-preview'),
  uploadPlaceholder: document.getElementById('upload-placeholder'),
  promptInput: document.getElementById('prompt-input'),
  refinementInput: document.getElementById('refinement-input'),
  canvasContainer: document.getElementById('canvas-container'),
  installButton: document.getElementById('install-app-button'),
  instructionsContainer: document.getElementById('instructions-container'),
  galleryCardsGrid: document.getElementById('gallery-cards-grid'),
  btnGalleryOptIn: document.getElementById('btn-gallery-optin')
};

let sceneState = {
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  garmentMesh: null,
  animationId: null
};

let stateMeasurements = {};

function ensureThreeScene() {
  if (sceneState.renderer) {
    return;
  }

  const { scene, camera, renderer, controls } = createThreeScene(els.canvasContainer);
  sceneState = { ...sceneState, scene, camera, renderer, controls };
  sceneState.garmentMesh = buildGarmentMesh(sceneState.scene, appState.meshParams, sceneState.garmentMesh);

  const tick = () => {
    if (!sceneState.renderer || !sceneState.controls) return;
    sceneState.controls.update();
    if (sceneState.garmentMesh) {
      sceneState.garmentMesh.rotation.y += 0.005;
    }
    sceneState.renderer.render(sceneState.scene, sceneState.camera);
    sceneState.animationId = requestAnimationFrame(tick);
  };

  tick();
}

function showStep(stepNum) {
  [1, 2, 3, 4].forEach((i) => {
    const step = document.getElementById(`step-${i}`);
    const badge = document.getElementById(`step-${i}-badge`);
    if (!step || !badge) return;

    step.classList.add('hidden');
    if (i === stepNum) {
      badge.className = 'px-3 py-1 rounded-lg b-brutal bg-fuchsia-300 text-black shadow-brutal-sm font-bold';
    } else {
      badge.className = 'px-3 py-1 rounded-lg b-brutal bg-white text-black opacity-60 font-bold';
    }
  });

  const activeStep = document.getElementById(`step-${stepNum}`);
  if (activeStep) {
    activeStep.classList.remove('hidden');
  }

  if (stepNum === 2) {
    ensureThreeScene();
  }
}

async function refreshGallery() {
  const remoteGallery = await fetchGallery();
  appState.gallery = remoteGallery || getGalleryItems();
  els.galleryCardsGrid.innerHTML = renderGalleryCards(appState.gallery);

  document.querySelectorAll('.buy-pattern-button').forEach((button) => {
    button.addEventListener('click', () => {
      const patternId = Number(button.dataset.patternId);
      const pattern = appState.gallery.find((item) => item.id === patternId);
      if (!pattern) return;

      alert(`✦ Purchased pattern! Downloading tiled PDF layout. Creator rewarded with 1 free outfit credit.`);
      appState.credits += 1;
      updateCreditUI(appState.credits);
    });
  });
}

function updateCreditDisplay() {
  updateCreditUI(appState.credits);
}

function openPricingModal() {
  openModal(els.modalPricing);
}

function closePricingModal() {
  closeModal(els.modalPricing);
}

function openAuthModal() {
  openModal(els.modalAuth);
}

function closeAuthModal() {
  closeModal(els.modalAuth);
}

async function submitAuth() {
  const email = els.authEmail.value.trim();
  if (!email) {
    return;
  }

  try {
    const result = await authenticateUser(email);
    appState.isLoggedIn = true;
    appState.userEmail = email;
    appState.credits = result?.user?.credits || appState.credits;
    setUserStatus(email.split('@')[0]);
    updateCreditDisplay();
    closeAuthModal();
  } catch (error) {
    alert(error.message || 'Unable to sign in right now.');
  }
}

async function subscribeTier(tierName, creditsToAdd) {
  if (!appState.isLoggedIn) {
    closePricingModal();
    openAuthModal();
    return;
  }

  try {
    const result = await subscribeUser(appState.userEmail, creditsToAdd);
    appState.credits = result?.user?.credits || appState.credits + creditsToAdd;
    updateCreditDisplay();
    closePricingModal();
    alert(`✦ Subscribed to ${tierName}! Added ${creditsToAdd} outfit credits.`);
  } catch (error) {
    appState.credits += creditsToAdd;
    updateCreditDisplay();
    closePricingModal();
    alert(`✦ Subscribed to ${tierName}! Added ${creditsToAdd} outfit credits.`);
  }
}

function triggerInvestorDemo() {
  appState.demoMode = true;
  appState.credits = 999;
  updateCreditDisplay();
  els.promptInput.value = 'Y2K Structured Bustier Corset with Asymmetrical Peplum Hem and Cap Sleeves';
  els.imagePreview.src = 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500';
  els.imagePreview.classList.remove('hidden');
  els.uploadPlaceholder.classList.add('hidden');
  showStep(2);
  alert('⚡ YC Investor Demo Activated! Credits bypassed & sample inputs loaded.');
}

function handleImageSelection(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    els.imagePreview.src = String(reader.result);
    els.imagePreview.classList.remove('hidden');
    els.uploadPlaceholder.classList.add('hidden');
  };
  reader.readAsDataURL(file);
}

function handleStepTwoAdvance() {
  if (appState.credits <= 0 && !appState.demoMode) {
    openPricingModal();
    return;
  }

  showStep(2);
}

function handleRefineClick() {
  const loader = document.getElementById('threed-loader');
  if (loader) loader.classList.remove('hidden');

  setTimeout(() => {
    appState.meshParams.flare += 0.3;
    if (sceneState.scene) {
      sceneState.garmentMesh = buildGarmentMesh(sceneState.scene, appState.meshParams, sceneState.garmentMesh);
    }
    if (loader) loader.classList.add('hidden');
  }, 700);
}

function handleMeasurementsSubmit(event) {
  event.preventDefault();

  if (!appState.demoMode) {
    appState.credits = Math.max(0, appState.credits - 1);
    updateCreditDisplay();
  }

  stateMeasurements = {
    bust: Number(document.getElementById('m-bust').value),
    waist: Number(document.getElementById('m-waist').value),
    hip: Number(document.getElementById('m-hip').value),
    shoulder: Number(document.getElementById('m-shoulder').value),
    napeToWaist: Number(document.getElementById('m-nape').value),
    length: Number(document.getElementById('m-length').value)
  };

  els.instructionsContainer.innerHTML = createInstructionMarkup();
  showStep(4);
}

async function optInToCommunityGallery() {
  const title = els.promptInput.value.slice(0, 24) || 'Custom Y2K Creation';

  try {
    const result = await listPattern({ title, email: appState.userEmail || 'guest@pyfit.dev' });
    appState.gallery.unshift(result?.listing || createPatternListing({ title, userEmail: appState.userEmail }));
    els.btnGalleryOptIn.textContent = '✓ Listed on Gallery!';
    els.btnGalleryOptIn.disabled = true;
    await refreshGallery();
    alert('✦ Published to Community Gallery! You\'ll earn 1 free credit every time someone buys this pattern.');
  } catch (error) {
    appState.gallery.unshift(createPatternListing({ title, userEmail: appState.userEmail }));
    els.btnGalleryOptIn.textContent = '✓ Listed on Gallery!';
    els.btnGalleryOptIn.disabled = true;
    await refreshGallery();
    alert('✦ Published to Community Gallery! You\'ll earn 1 free credit every time someone buys this pattern.');
  }
}

function handleDownloadPdf() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  doc.setDrawColor(0, 0, 0);
  doc.rect(10, 10, 190, 277);
  doc.setFontSize(14);
  doc.text('PRINT YOUR FIT - Custom Tiled Pattern Grid A1', 15, 20);
  doc.rect(15, 30, 50, 50);
  doc.setFontSize(8);
  doc.text('50mm x 50mm SCALE CHECK', 17, 45);
  doc.setLineWidth(0.8);
  doc.setDrawColor(217, 70, 239);
  doc.line(30, 100, 150, 90);
  doc.line(150, 90, 170, 220);
  doc.line(170, 220, 30, 220);
  doc.line(30, 220, 30, 100);
  doc.save('PrintYourFit_CustomPattern.pdf');
}

function wireEvents() {
  document.getElementById('btn-to-step2').addEventListener('click', handleStepTwoAdvance);
  document.getElementById('btn-to-step3').addEventListener('click', () => showStep(3));
  document.getElementById('btn-refine').addEventListener('click', handleRefineClick);
  document.getElementById('measurements-form').addEventListener('submit', handleMeasurementsSubmit);
  document.getElementById('btn-download-pdf').addEventListener('click', handleDownloadPdf);
  document.getElementById('btn-gallery-optin').addEventListener('click', optInToCommunityGallery);
  document.getElementById('image-input').addEventListener('change', handleImageSelection);
  document.getElementById('modal-pricing').addEventListener('click', (event) => {
    if (event.target.id === 'modal-pricing') closePricingModal();
  });
  document.getElementById('modal-auth').addEventListener('click', (event) => {
    if (event.target.id === 'modal-auth') closeAuthModal();
  });
  document.getElementById('open-pricing-button').addEventListener('click', openPricingModal);
  document.getElementById('open-auth-button').addEventListener('click', openAuthModal);
  document.getElementById('submit-auth-button').addEventListener('click', submitAuth);
  document.getElementById('trigger-demo-button').addEventListener('click', triggerInvestorDemo);
  els.navStudio.addEventListener('click', () => showTabView({ studioView: els.studioView, galleryView: els.galleryView, studioTab: els.navStudio, galleryTab: els.navGallery, tab: 'studio' }));
  els.navGallery.addEventListener('click', () => {
    showTabView({ studioView: els.studioView, galleryView: els.galleryView, studioTab: els.navStudio, galleryTab: els.navGallery, tab: 'gallery' });
    refreshGallery();
  });

  registerInstallPrompt(els.installButton);
}

function init() {
  updateCreditDisplay();
  refreshGallery();
  wireEvents();
  showTabView({ studioView: els.studioView, galleryView: els.galleryView, studioTab: els.navStudio, galleryTab: els.navGallery, tab: 'studio' });
  showStep(1);
  setUserStatus('Sign In');
}

window.addEventListener('load', init);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./service-worker.js').catch((error) => {
      console.warn('Service worker registration failed:', error);
    });
  });
}
