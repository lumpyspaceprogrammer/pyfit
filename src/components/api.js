const API_BASE = '/api';

const gallerySeed = [
  {
    id: 1,
    title: 'Y2K Asymmetrical Corset',
    creator: '@skate_sews',
    price: 2.99,
    image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500',
    buys: 14
  },
  {
    id: 2,
    title: 'Cyber Punk Patchwork Top',
    creator: '@neo_threads',
    price: 2.99,
    image: 'https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=500',
    buys: 9
  },
  {
    id: 3,
    title: 'Dreamscape Flared Dress',
    creator: '@y2k_studio',
    price: 2.99,
    image: 'https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=500',
    buys: 22
  }
];

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || 'Request failed');
  }

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}

export function getGalleryItems() {
  return gallerySeed.map((item) => ({ ...item }));
}

export function createPatternListing({ title, userEmail }) {
  return {
    id: Date.now(),
    title: title || 'Custom Y2K Creation',
    creator: userEmail ? `@${userEmail.split('@')[0]}` : '@guest_designer',
    price: 2.99,
    image: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500',
    buys: 0
  };
}

export function getPatternInstructions() {
  return `
    <ol class="list-decimal list-inside space-y-2">
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Print Check:</b> Ensure 100% actual print size. Measure the 50mm square on Page A1.</li>
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Assembly:</b> Align crosshairs (A1 -> A2, B1 -> B2) and tape pages.</li>
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Cutting:</b> Pre-included seam allowance = 1.5cm. Cut fabric along grainlines.</li>
    </ol>
  `;
}

export async function fetchGallery() {
  try {
    return await apiRequest('/gallery');
  } catch (error) {
    return getGalleryItems();
  }
}

export async function authenticateUser(email) {
  return apiRequest('/auth', {
    method: 'POST',
    body: JSON.stringify({ email })
  });
}

export async function subscribeUser(email, creditsToAdd) {
  return apiRequest('/subscribe', {
    method: 'POST',
    body: JSON.stringify({ email, creditsToAdd })
  });
}

export async function listPattern({ title, email }) {
  return apiRequest('/gallery/list', {
    method: 'POST',
    body: JSON.stringify({ title, email })
  });
}
