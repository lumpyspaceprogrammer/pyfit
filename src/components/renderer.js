export function renderGalleryCards(gallery) {
  return gallery
    .map(
      (item) => `
        <div class="bg-white b-brutal rounded-2xl overflow-hidden shadow-brutal flex flex-col justify-between space-y-3 p-4">
          <img src="${item.image}" alt="${item.title}" class="h-48 w-full object-cover b-brutal rounded-xl">
          <div>
            <span class="text-[10px] font-black bg-cyan-200 b-brutal px-2 py-0.5 rounded">${item.creator}</span>
            <h4 class="font-black text-black text-sm uppercase mt-1 y2k-font">${item.title}</h4>
            <p class="text-[11px] font-bold text-slate-500">${item.buys} seamstresses printed this</p>
          </div>
          <button data-pattern-id="${item.id}" class="buy-pattern-button w-full py-2 bg-lime-300 hover:bg-lime-400 b-brutal rounded-xl font-black text-xs uppercase shadow-brutal-sm">
            Buy Pattern ($${item.price})
          </button>
        </div>
      `
    )
    .join('');
}

export function createInstructionMarkup() {
  return `
    <ol class="list-decimal list-inside space-y-2">
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Print Check:</b> Ensure 100% actual print size. Measure the 50mm square on Page A1.</li>
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Assembly:</b> Align crosshairs (A1 -> A2, B1 -> B2) and tape pages.</li>
      <li class="bg-indigo-50 p-2.5 b-brutal rounded-xl"><b>Cutting:</b> Pre-included seam allowance = 1.5cm. Cut fabric along grainlines.</li>
    </ol>
  `;
}

export function buildGarmentMesh(scene, meshParams, existingMesh) {
  if (existingMesh) {
    scene.remove(existingMesh);
  }

  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({
    color: 0xe879f9,
    roughness: 0.2,
    metalness: 0.7,
    side: THREE.DoubleSide
  });

  const topGeo = new THREE.CylinderGeometry(0.75, meshParams.waistRadius, meshParams.topHeight, 32, 1, true);
  const topMesh = new THREE.Mesh(topGeo, material);
  topMesh.position.y = 0.4;
  group.add(topMesh);

  const skirtGeo = new THREE.CylinderGeometry(meshParams.waistRadius, meshParams.waistRadius + meshParams.flare, 1.8, 32, 1, true);
  const skirtMesh = new THREE.Mesh(skirtGeo, material);
  skirtMesh.position.y = -1.0;
  group.add(skirtMesh);

  scene.add(group);
  return group;
}

export function createThreeScene(container) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x09090b);

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(0, 0.8, 4);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
  scene.add(ambientLight);

  const light1 = new THREE.PointLight(0x22d3ee, 2);
  light1.position.set(5, 5, 5);
  scene.add(light1);

  const light2 = new THREE.PointLight(0xe879f9, 2);
  light2.position.set(-5, -2, 5);
  scene.add(light2);

  return { scene, camera, renderer, controls };
}
