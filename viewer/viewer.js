import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { buildCar } from '../model/scene.js';

/* ================================================================== */
/*  renderer / scene                                                   */
/* ================================================================== */
const app = document.getElementById('app');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.18;
renderer.outputColorSpace = THREE.SRGBColorSpace;
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);

/* softbox studio environment: gives metal / plastic physically plausible reflections */
function studioEnv() {
  const g = new THREE.Scene();
  const room = new THREE.Mesh(
    new THREE.BoxGeometry(1400, 900, 1400),
    new THREE.MeshBasicMaterial({ color: 0x0a0d0f, side: THREE.BackSide })
  );
  room.position.y = 260;
  g.add(room);
  const soft = (w, h, x, y, z, color, power) => {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(w, h),
      new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide })
    );
    m.material.color.multiplyScalar(power);
    m.position.set(x, y, z);
    m.lookAt(0, 220, 0);
    g.add(m);
  };
  soft(620, 420, 0, 700, 60, 0xffffff, 5.2);      // overhead key softbox
  soft(360, 520, -620, 330, 240, 0xcfe4ff, 3.4);  // left cool box
  soft(300, 460, 540, 300, -380, 0xffe6c8, 2.8);  // right warm box
  soft(900, 200, 0, 20, -640, 0x8fd8ff, 1.1);     // low rim strip
  return g;
}
scene.environment = pmrem.fromScene(studioEnv(), 0.02).texture;
scene.environmentIntensity = 0.72;
scene.background = new THREE.Color(0x0a0e10);

const camera = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, 1, 6000);
camera.position.set(300, -260, 190);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.075;
controls.rotateSpeed = 0.85;
controls.zoomSpeed = 0.85;
controls.panSpeed = 0.7;
controls.minDistance = 90;
controls.maxDistance = 1200;
controls.maxPolarAngle = Math.PI * 0.86;
controls.target.set(0, 0, 42);
controls.autoRotateSpeed = 1.1;
controls.autoRotate = true;

/* ================================================================== */
/*  lights                                                             */
/* ================================================================== */
scene.add(new THREE.HemisphereLight(0xcfe2ff, 0x0e1214, 0.34));

const key = new THREE.DirectionalLight(0xfff2df, 3.05);
key.position.set(220, 330, 300);
key.castShadow = true;
key.shadow.mapSize.set(3072, 3072);
key.shadow.camera.near = 60;
key.shadow.camera.far = 1500;
key.shadow.camera.left = -220;
key.shadow.camera.right = 220;
key.shadow.camera.top = 220;
key.shadow.camera.bottom = -220;
key.shadow.bias = -0.0009;
key.shadow.normalBias = 2.6;
key.shadow.radius = 4.5;
scene.add(key);

const fill = new THREE.DirectionalLight(0xbcd8ff, 0.5);
fill.position.set(-330, 160, 190);
scene.add(fill);

const rim = new THREE.DirectionalLight(0xa9f2d8, 1.6);
rim.position.set(-180, 210, -330);
scene.add(rim);

const kick = new THREE.DirectionalLight(0xffd9b0, 0.55);
kick.position.set(300, 80, -300);
scene.add(kick);

const under = new THREE.DirectionalLight(0x86a8c4, 0.42);
under.position.set(60, -140, -180);
scene.add(under);

/* ================================================================== */
/*  floor                                                              */
/* ================================================================== */
function radialTexture(inner, outer, power = 2.2) {
  const s = 512;
  const c = document.createElement('canvas');
  c.width = c.height = s;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  for (let i = 0; i <= 10; i++) {
    const t = i / 10;
    const k = Math.pow(1 - t, power);
    grd.addColorStop(t, `rgba(${inner[0]},${inner[1]},${inner[2]},${(inner[3] * k + outer[3] * (1 - k)).toFixed(3)})`);
  }
  g.fillStyle = grd;
  g.fillRect(0, 0, s, s);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const floorGroup = new THREE.Group();
scene.add(floorGroup);

/* seamless studio backdrop: dark cyclorama gradient + soft light pool */
function backdropTexture() {
  const c = document.createElement('canvas');
  c.width = 8; c.height = 512;
  const g = c.getContext('2d');
  const grd = g.createLinearGradient(0, 0, 0, 512);
  grd.addColorStop(0.00, '#05080a');
  grd.addColorStop(0.34, '#0a0f12');
  grd.addColorStop(0.52, '#0d1418');
  grd.addColorStop(0.70, '#090d10');
  grd.addColorStop(1.00, '#040607');
  g.fillStyle = grd; g.fillRect(0, 0, 8, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const backdrop = new THREE.Mesh(
  new THREE.SphereGeometry(3000, 64, 48),
  new THREE.MeshBasicMaterial({ map: backdropTexture(), side: THREE.BackSide, depthWrite: false })
);
backdrop.position.y = 120;
scene.add(backdrop);

const floorAlpha = radialTexture([255, 255, 255, 1], [255, 255, 255, 0], 1.35);
const floor = new THREE.Mesh(
  new THREE.CircleGeometry(2400, 128),
  new THREE.MeshStandardMaterial({
    color: 0x0e1215,
    roughness: 0.97,
    metalness: 0.0,
    envMapIntensity: 0.10,
    alphaMap: floorAlpha,
    transparent: true,
    opacity: 1.0,
    depthWrite: true,
  })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.4;
floor.receiveShadow = true;
floorGroup.add(floor);

const contactShadow = new THREE.Mesh(
  new THREE.PlaneGeometry(300, 240),
  new THREE.MeshBasicMaterial({
    map: radialTexture([255, 255, 255, 0.85], [255, 255, 255, 0.0], 2.4),
    transparent: true,
    blending: THREE.NormalBlending,
    depthWrite: false,
    opacity: 0.5,
  })
);
contactShadow.rotation.x = -Math.PI / 2;
contactShadow.position.set(0, 0.15, 0);
floorGroup.add(contactShadow);



const grid = new THREE.GridHelper(600, 60, 0x2f4a3e, 0x24352c);
grid.position.y = 0.2;
grid.material.transparent = true;
grid.material.opacity = 0.5;
grid.visible = false;
floorGroup.add(grid);

/* ================================================================== */
/*  model                                                              */
/* ================================================================== */
const car = buildCar();
// model space is Z-up / millimetres; the viewer world is Y-up
const carRoot = new THREE.Group();
carRoot.name = 'CarRoot';
carRoot.rotation.x = -Math.PI / 2;
carRoot.add(car);
scene.add(carRoot);

/* ================================================================== */
/*  post processing: SSAO -> bloom -> filmic output -> SMAA            */
/* ================================================================== */
let composer = null;
function buildComposer() {
  const w = innerWidth, h = innerHeight;
  const c = new EffectComposer(renderer);
  c.setPixelRatio(Math.min(devicePixelRatio, 2));
  c.setSize(w, h);

  c.addPass(new RenderPass(scene, camera));

  const ssao = new SSAOPass(scene, camera, w, h);
  ssao.kernelRadius = 7;
  ssao.minDistance = 0.4;
  ssao.maxDistance = 16;
  ssao.output = SSAOPass.OUTPUT.Default;
  c.addPass(ssao);

  const bloom = new UnrealBloomPass(new THREE.Vector2(w, h), 0.22, 0.78, 0.7);
  c.addPass(bloom);

  c.addPass(new OutputPass());
  c.addPass(new SMAAPass());
  return c;
}
composer = buildComposer();
const draw = () => { if (composer) composer.render(); else renderer.render(scene, camera); };
window.__composer = composer;

/* ================================================================== */
/*  camera presets (azimuth from +X toward +Y, elevation above XY)      */
/* ================================================================== */
const VIEWS = {
  hero:   { az: 38, el: 23, dist: 405, target: [0, 0, 64] },
  front:  { az: 2, el: 9, dist: 330, target: [6, 0, 40] },
  left:   { az: 92, el: 7, dist: 345, target: [0, 0, 38] },
  right:  { az: -92, el: 7, dist: 345, target: [0, 0, 38] },
  top:    { az: 0, el: 89.4, dist: 380, target: [0, 0, 30] },
  pcb:    { az: 0, el: 89.4, dist: 210, target: [4, 0, 50] },
  pcbzoom:{ az: 0, el: 89.4, dist: 120, target: [14, 0, 50] },
  esp32:  { az: 32, el: 26, dist: 170, target: [18, 0, 52] },
  iso:    { az: 35, el: 26, dist: 420, target: [0, 0, 52] },
  p03:    { az: 34, el: 19, dist: 430, target: [2, 0, 40] },
  p02:    { az: 62, el: 16, dist: 360, target: [2, 0, 44] },
  p10:    { az: 178, el: 10, dist: 430, target: [0, 0, 40] },
  rear:   { az: 178, el: 12, dist: 345, target: [0, 0, 38] },
  bottom: { az: 18, el: -34, dist: 380, target: [0, 0, 34] },
  detail: { az: 26, el: 18, dist: 205, target: [26, 6, 50] },
};

const PARTS = {
  pcb:     { target: [4, 0, 46], dist: 300, name: '主控 PCB' },
  esp32:   { target: [14, 2, 58], dist: 200, name: 'ESP32-S3' },
  tb6612:  { target: [28, 34, 52], dist: 190, name: 'TB6612' },
  mpu:     { target: [-4, 40, 58], dist: 175, name: 'MPU6050' },
  tof:     { target: [54, 0, 70], dist: 190, name: 'VL53L0X' },
  oled:    { target: [-26, -30, 52], dist: 175, name: 'OLED' },
  battery: { target: [2, 0, 24], dist: 240, name: '18650 电池' },
  motor:   { target: [22, -62, 22], dist: 200, name: 'N20 电机' },
  wheel:   { target: [22, -70, 20], dist: 190, name: '橡胶轮' },
  caster:  { target: [38, 0, 6], dist: 190, name: '万向球轮' },
  wall:    { target: [50, 0, 55], dist: 280, name: '前置测距墙' },
};

/** world space is Y-up; model +X is the car front, model +Y is the car left.
 *  az = 0 looks at the front, az = 90 at the left flank, el = elevation. */
function sph(az, el, dist, t) {
  const a = THREE.MathUtils.degToRad(az);
  const e = THREE.MathUtils.degToRad(el);
  const m = new THREE.Vector3(
    t[0] + dist * Math.cos(e) * Math.cos(a),
    t[1] + dist * Math.sin(e),
    t[2] - dist * Math.cos(e) * Math.sin(a)
  );
  return m;
}

let tween = null;
function animateTo(pos, target, dur = 900) {
  tween = {
    p0: camera.position.clone(),
    p1: pos.clone(),
    t0: controls.target.clone(),
    t1: new THREE.Vector3(...target),
    start: performance.now(),
    dur,
  };
  floorGroup.visible = pos.z > -20;
}

const toWorld = (p) => new THREE.Vector3(p[0], p[2], -p[1]);

function setView(name, instant = false) {
  const v = VIEWS[name] || VIEWS.hero;
  const tgt = toWorld(v.target).toArray();
  const pos = sph(v.az, v.el, v.dist, tgt);
  if (instant) {
    camera.position.copy(pos);
    controls.target.set(...tgt);
    controls.update();
    floorGroup.visible = pos.y > -20;
    tween = null;
    return;
  }
  animateTo(pos, tgt);
}

function focusPart(key, instant = false) {
  const p = PARTS[key];
  if (!p) return;
  // keep the current viewing direction, just move the target & distance
  const dir = camera.position.clone().sub(controls.target).normalize();
  const tgt = toWorld(p.target);
  const pos = tgt.clone().addScaledVector(dir, p.dist);
  if (instant) {
    camera.position.copy(pos);
    controls.target.copy(tgt);
    controls.update();
    tween = null;
  } else {
    animateTo(pos, tgt.toArray(), 800);
  }
  setActivePart(key);
}

/* ================================================================== */
/*  UI                                                                 */
/* ================================================================== */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

let activePart = null;
function setActivePart(key) {
  activePart = key;
}

$$('.btn[data-view]').forEach((b) => {
  b.addEventListener('click', () => {
    $$('.btn[data-view]').forEach((x) => x.classList.toggle('on', x === b));
    setView(b.dataset.view);
    controls.autoRotate = false;
    $('#btnRotate').classList.remove('on');
  });
});

$$('.part').forEach((el) => el.addEventListener('click', () => focusPart(el.dataset.part)));

$('#btnRotate').addEventListener('click', (e) => {
  controls.autoRotate = !controls.autoRotate;
  e.currentTarget.classList.toggle('on', controls.autoRotate);
});

let wire = false;
$('#btnWire').addEventListener('click', (e) => {
  wire = !wire;
  e.currentTarget.classList.toggle('on', wire);
  car.traverse((o) => {
    if (!o.isMesh) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (m.userData.__origWire === undefined) m.userData.__origWire = m.wireframe;
      m.wireframe = wire;
    }
  });
});

$('#btnGrid').addEventListener('click', (e) => {
  grid.visible = !grid.visible;
  e.currentTarget.classList.toggle('on', grid.visible);
});

let shadowOn = true;
$('#btnShadow').addEventListener('click', (e) => {
  shadowOn = !shadowOn;
  renderer.shadowMap.enabled = shadowOn;
  key.castShadow = shadowOn;
  contactShadow.visible = shadowOn;
  floor.receiveShadow = shadowOn;
  car.traverse((o) => { if (o.isMesh) o.material.needsUpdate = true; });
  e.currentTarget.classList.toggle('on', shadowOn);
});

/* ================================================================== */
/*  stats                                                              */
/* ================================================================== */
let tri = 0, meshes = 0, materials = new Set(), textures = new Set();
car.traverse((o) => {
  if (!o.isMesh) return;
  meshes++;
  const g = o.geometry;
  tri += g.index ? g.index.count / 3 : g.getAttribute('position').count / 3;
  const mats = Array.isArray(o.material) ? o.material : [o.material];
  for (const m of mats) {
    materials.add(m);
    for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'alphaMap'])
      if (m[k]) textures.add(m[k]);
  }
});
$('#stats').textContent = `${meshes} meshes · ${Math.round(tri).toLocaleString()} tris · ${materials.size} materials · ${textures.size} textures · units: mm`;

/* ================================================================== */
/*  screenshots + exports                                              */
/* ================================================================== */
function download(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

function b64(bytes) {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let s = '';
  const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  return btoa(s);
}

async function exportModel(type) {
  if (type === 'glb') {
    const root = new THREE.Group();
    root.name = 'MazeCar_1_1';
    root.add(car.clone(true));
    root.rotation.x = -Math.PI / 2;   // Z-up (model) -> Y-up (glTF)
    root.scale.setScalar(0.001);      // mm -> m
    root.updateMatrixWorld(true);
    const buf = await new GLTFExporter().parseAsync(root, { binary: true, onlyVisible: true });
    return new Uint8Array(buf);
  }
  if (type === 'obj') {
    const txt = new OBJExporter().parse(car);
    return new TextEncoder().encode(txt);
  }
  if (type === 'stl') {
    const dv = new STLExporter().parse(car, { binary: true });
    return new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength);
  }
  throw new Error('unknown type ' + type);
}

window.__export = async (type) => b64(await exportModel(type));
window.__exportSize = async (type) => (await exportModel(type)).byteLength;

$('#btnGLB').addEventListener('click', async (e) => {
  e.currentTarget.textContent = '导出中…';
  try {
    const u8 = await exportModel('glb');
    download(new Blob([u8], { type: 'model/gltf-binary' }), 'maze-car.glb');
  } finally {
    e.currentTarget.textContent = 'GLB · 材质贴图';
  }
});
$('#btnOBJ').addEventListener('click', async () => {
  const u8 = await exportModel('obj');
  download(new Blob([u8], { type: 'text/plain' }), 'maze-car.obj');
});
$('#btnSTL').addEventListener('click', async () => {
  const u8 = await exportModel('stl');
  download(new Blob([u8], { type: 'model/stl' }), 'maze-car.stl');
});
$('#btnPNG').addEventListener('click', () => {
  draw();
  renderer.domElement.toBlob((b) => download(b, 'maze-car.png'), 'image/png');
});

/* reference photos */
const REFS = [
  ['01_topdown.jpg', '底面 / 底盘'],
  ['02_side.jpg', '左侧 3/4'],
  ['03_front.jpg', '前方 3/4'],
  ['04_top.jpg', '顶部'],
  ['05_side2.jpg', '右侧俯视'],
  ['06_rear.jpg', '顶板正面'],
  ['07_front2.jpg', '正前方'],
  ['08_side3.jpg', '右侧'],
  ['09_side4.jpg', '左侧'],
  ['10_rear2.jpg', '竖直板正面'],
];
for (const [f, cap] of REFS) {
  const fig = document.createElement('figure');
  fig.innerHTML = `<img src="../ref/${f}" loading="lazy" alt="${cap}"><figcaption>${cap}</figcaption>`;
  $('#shotGrid').appendChild(fig);
}
$('#btnRefs').addEventListener('click', () => $('#modal').classList.add('on'));
$('#modalClose').addEventListener('click', () => $('#modal').classList.remove('on'));
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') $('#modal').classList.remove('on'); });

/* ================================================================== */
/*  loop                                                               */
/* ================================================================== */
const clock = new THREE.Clock();
let frames = 0;
let paused = false;

function tick() {
  requestAnimationFrame(tick);
  const dt = clock.getDelta();

  if (tween) {
    const k = Math.min(1, (performance.now() - tween.start) / tween.dur);
    const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.t0, tween.t1, e);
    if (k >= 1) tween = null;
  }

  controls.update();
  if (!paused) draw();

  if (++frames === 3) {
    document.getElementById('loader').classList.add('off');
    setView('hero', false);
    window.__READY = true;
  }
}
tick();

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

/* ================================================================== */
/*  test hooks                                                         */
/* ================================================================== */
window.__setView = (name, instant = true) => {
  controls.autoRotate = false;
  setView(name, instant);
  draw();
};
window.__setCamera = (az, el, dist, target = [0, 0, 42]) => {
  controls.autoRotate = false;
  const tgt = toWorld(target).toArray();
  camera.position.copy(sph(az, el, dist, tgt));
  controls.target.set(...tgt);
  controls.update();
  draw();
};
window.__focus = (key) => { focusPart(key, true); draw(); };
window.__hideFloor = (v) => { floorGroup.visible = !v; draw(); };
window.__stats = () => ({ meshes, tris: Math.round(tri), materials: materials.size, textures: textures.size });
window.__bounds = () => {
  const b = new THREE.Box3().setFromObject(car);
  return { min: b.min.toArray(), max: b.max.toArray(), size: b.getSize(new THREE.Vector3()).toArray() };
};

window.__boxes = () => {
  const THREEBox = THREE.Box3;
  const out = {};
  for (const child of car.children) {
    const b = new THREEBox().setFromObject(child);
    out[child.name || child.type] = {
      min: b.min.toArray().map((v) => +v.toFixed(1)),
      max: b.max.toArray().map((v) => +v.toFixed(1)),
    };
  }
  return out;
};

window.__THREE = THREE;
window.__camera = camera;
window.__renderer = renderer;
window.__scene = scene;
window.__car = car;
window.__find = (name) => { let r = null; car.traverse((o) => { if (!r && o.name === name) r = o; }); return r; };
window.__childBoxes = (name) => {
  const p = window.__find(name);
  if (!p) return null;
  return p.children.map((c) => {
    const b = new THREE.Box3().setFromObject(c);
    return [c.type + (c.name ? ':' + c.name : ''), b.min.toArray().map((v) => +v.toFixed(1)), b.max.toArray().map((v) => +v.toFixed(1))];
  });
};

window.__ortho = (az, el, size = 105, target = [0, 0, 42]) => {
  const aspect = innerWidth / innerHeight;
  const dir = sph(az, el, 1, [0, 0, 0]);
  const cam = new THREE.OrthographicCamera(-size * aspect, size * aspect, size, -size, 1, 5000);
  const tgt = toWorld(target);
  cam.position.copy(tgt).addScaledVector(dir, 2000);
  cam.up.set(0, 1, 0);
  if (Math.abs(el) > 75) cam.up.set(1, 0, 0);
  cam.lookAt(tgt);
  cam.updateProjectionMatrix();
  floorGroup.visible = false;
  paused = true;
  renderer.render(scene, cam);
};
window.__resume = () => { paused = false; };
window.__hideFloor = (v) => { floorGroup.visible = !v; if (!paused) draw(); };
window.__hideUI = () => {
  for (const id of ['title', 'controls', 'parts', 'hint', 'export', 'stats']) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  }
};
