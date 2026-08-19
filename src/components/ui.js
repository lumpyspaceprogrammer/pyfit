export function updateCreditUI(credits) {
  const badge = document.getElementById('credit-count-badge');
  if (!badge) return;
  badge.textContent = `${credits} Credit${credits === 1 ? '' : 's'}`;
}

export function setUserStatus(value) {
  const userStatus = document.getElementById('user-status-text');
  if (userStatus) {
    userStatus.textContent = value;
  }
}

export function openModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.remove('hidden');
}

export function closeModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.add('hidden');
}

export function showTabView({ studioView, galleryView, studioTab, galleryTab, tab }) {
  if (tab === 'studio') {
    studioView.classList.remove('hidden');
    galleryView.classList.add('hidden');
    studioTab.className = 'px-3 py-1.5 rounded-xl b-brutal bg-fuchsia-300 font-extrabold text-xs shadow-brutal-sm';
    galleryTab.className = 'px-3 py-1.5 rounded-xl b-brutal bg-white hover:bg-cyan-100 font-extrabold text-xs';
    return;
  }

  studioView.classList.add('hidden');
  galleryView.classList.remove('hidden');
  studioTab.className = 'px-3 py-1.5 rounded-xl b-brutal bg-white hover:bg-cyan-100 font-extrabold text-xs';
  galleryTab.className = 'px-3 py-1.5 rounded-xl b-brutal bg-fuchsia-300 font-extrabold text-xs shadow-brutal-sm';
}

export function registerInstallPrompt(buttonEl) {
  if (!buttonEl) {
    return;
  }

  let deferredPrompt = null;

  const onBeforeInstallPrompt = (event) => {
    event.preventDefault();
    deferredPrompt = event;
    buttonEl.classList.remove('hidden');
  };

  const onAppInstalled = () => {
    buttonEl.classList.add('hidden');
    deferredPrompt = null;
  };

  window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
  window.addEventListener('appinstalled', onAppInstalled);

  buttonEl.addEventListener('click', async () => {
    if (!deferredPrompt) {
      return;
    }

    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    buttonEl.classList.add('hidden');
  });
}
