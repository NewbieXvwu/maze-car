import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

/* ---------- palette ---------- */
export const MAT = {
  pcbGreen: new THREE.MeshStandardMaterial({ color: 0x0d6b3d, roughness: 0.52, metalness: 0.08 }),
  pcbEdge: new THREE.MeshStandardMaterial({ color: 0x0a5530, roughness: 0.6, metalness: 0.05 }),
  perfGreen: new THREE.MeshStandardMaterial({ color: 0x0e6f40, roughness: 0.55, metalness: 0.06 }),
  solder: new THREE.MeshStandardMaterial({ color: 0xd3d8dc, roughness: 0.32, metalness: 0.95 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xd8b25a, roughness: 0.3, metalness: 0.98 }),
  brass: new THREE.MeshStandardMaterial({ color: 0xb08a3e, roughness: 0.35, metalness: 0.95 }),
  black: new THREE.MeshStandardMaterial({ color: 0x151515, roughness: 0.62, metalness: 0.03 }),
  blackGloss: new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.28, metalness: 0.1 }),
  darkGrey: new THREE.MeshStandardMaterial({ color: 0x2a2b2d, roughness: 0.6 }),
  white: new THREE.MeshStandardMaterial({ color: 0xe7e4dc, roughness: 0.66, metalness: 0.02 }),
  whiteGloss: new THREE.MeshStandardMaterial({ color: 0xefece4, roughness: 0.34, metalness: 0.02 }),
  tape: new THREE.MeshStandardMaterial({ color: 0xf3f0e7, roughness: 0.82, metalness: 0.0 }),
  red: new THREE.MeshStandardMaterial({ color: 0xb01f1f, roughness: 0.5 }),
  bluePcb: new THREE.MeshStandardMaterial({ color: 0x1a4a9c, roughness: 0.48, metalness: 0.05 }),
  bluePlastic: new THREE.MeshStandardMaterial({ color: 0x1a5ad0, roughness: 0.45 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x131313, roughness: 0.95, metalness: 0.0 }),
  shield: new THREE.MeshStandardMaterial({ color: 0xc3c8cc, roughness: 0.3, metalness: 0.9 }),
  silver: new THREE.MeshStandardMaterial({ color: 0xa9aeb2, roughness: 0.38, metalness: 0.9 }),
  yellow: new THREE.MeshStandardMaterial({ color: 0xe0b62a, roughness: 0.4, metalness: 0.3 }),
  oled: new THREE.MeshPhysicalMaterial({ color: 0x05070a, roughness: 0.08, metalness: 0.2, clearcoat: 1, clearcoatRoughness: 0.05 }),
  glass: new THREE.MeshPhysicalMaterial({ color: 0x0b0e12, roughness: 0.1, metalness: 0.3, clearcoat: 1 }),
  chip: new THREE.MeshStandardMaterial({ color: 0x181a1c, roughness: 0.45 }),
  capTan: new THREE.MeshStandardMaterial({ color: 0xc8a54b, roughness: 0.5 }),
  inductor: new THREE.MeshStandardMaterial({ color: 0x6a6d70, roughness: 0.55, metalness: 0.25 }),
};

export const D = {
  plate: { w: 94, l: 140, t: 2.5, top: 13 },
  wall: { x0: 49, x1: 51.5, w: 94, h: 52, z0: 9.5, z1: 61.5 },
  pcb: { front: 49, back: -42.44, top: 40.0, t: 1.6, w: 88.9, l: 91.44 },
  wheel: { r: 21, w: 22, x: 22, y: 58.5 },
  battery: { l: 77, w: 42, h: 20 },
};

/* ---------- helpers ---------- */
export function box(w, h, d, mat, opts = {}) {
  const { r = 0, seg = 3 } = opts;
  const g = r > 0 ? new RoundedBoxGeometry(w, h, d, seg, Math.min(r, Math.min(w, h, d) / 2 - 0.001)) : new THREE.BoxGeometry(w, h, d);
  const m = new THREE.Mesh(g, mat);
  m.castShadow = m.receiveShadow = true;
  return m;
}
export function cyl(rt, rb, h, mat, seg = 24, open = false) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg, 1, open), mat);
  m.castShadow = m.receiveShadow = true;
  return m;
}
export function at(obj, x, y, z, rx = 0, ry = 0, rz = 0) {
  obj.position.set(x, y, z); obj.rotation.set(rx, ry, rz);
  return obj;
}
export function plane(w, h, mat) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  m.receiveShadow = true;
  return m;
}
export function textPlane(texture, w, h, matOpts = {}) {
  const mat = new THREE.MeshStandardMaterial({
    map: texture, transparent: true, roughness: 0.75, metalness: 0.05,
    side: THREE.DoubleSide, ...matOpts,
  });
  return plane(w, h, mat);
}

/* thin black female header strip: rows x cols, height along +Z */
export function header(rows, cols, pitch = 2.54, h = 8.5, mat = MAT.black) {
  const g = new THREE.Group();
  const w = cols * pitch + 0.6, d = rows * pitch + 0.6;
  const body = box(w, d, h, mat, { r: 0.25 });
  body.position.z = h / 2;
  g.add(body);
  const socketMat = new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.7 });
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const s = box(1.05, 1.05, 0.5, socketMat);
    s.position.set((c - (cols - 1) / 2) * pitch, (r - (rows - 1) / 2) * pitch, h + 0.05);
    g.add(s);
    const pin = cyl(0.32, 0.32, h, MAT.gold, 8);
    pin.rotation.x = Math.PI / 2;
    pin.position.set((c - (cols - 1) / 2) * pitch, (r - (rows - 1) / 2) * pitch, h / 2);
    g.add(pin);
  }
  return g;
}

/* male pin header strip along X, pins along +Z */
export function pinRow(cols, pitch = 2.54, len = 11, mat = MAT.gold) {
  const g = new THREE.Group();
  const bodyW = cols * pitch;
  const base = box(bodyW, 2.5, 2.5, MAT.black, { r: 0.15 });
  base.position.z = 1.25; g.add(base);
  for (let c = 0; c < cols; c++) {
    const p = box(0.64, 0.64, len, mat);
    p.position.set((c - (cols - 1) / 2) * pitch, 0, len / 2 - 2.5);
    g.add(p);
  }
  return g;
}

export function screw(r = 1.4, h = 1.2) {
  const g = new THREE.Group();
  const head = cyl(r, r, h, MAT.silver, 16);
  head.rotation.x = Math.PI / 2;
  head.position.z = h / 2; g.add(head);
  const slot = box(r * 1.5, 0.35, 0.25, MAT.darkGrey);
  slot.position.z = h + 0.02; g.add(slot);
  return g;
}

/* JST-XH connector sitting on a PCB, pins pointing down */
export function jst(n = 2, color = 0xf2efe6) {
  const g = new THREE.Group();
  const bodyMat = new THREE.MeshStandardMaterial({ color, roughness: 0.55 });
  const w = n * 1.5 + 1.2;
  const b = box(w, 5, 5, bodyMat, { r: 0.4 });
  b.position.z = 3.5; g.add(b);
  const latch = box(w * 0.7, 1.4, 1.2, bodyMat, { r: 0.2 });
  latch.position.set(0, -1.6, 6.0); g.add(latch);
  for (let i = 0; i < n; i++) {
    const p = box(0.5, 0.5, 3.5, MAT.gold);
    p.position.set((i - (n - 1) / 2) * 1.5, 0, -0.8);
    g.add(p);
  }
  return g;
}

export function wire(points, color = 0xd23b2f, r = 0.55, tension = 0.5, seg = 80) {
  const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)), false, 'catmullrom', tension);
  const geo = new THREE.TubeGeometry(curve, seg, r, 7, false);
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.02 });
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = m.receiveShadow = true;
  return m;
}

const RIBBON = [0xf2d024, 0x2aa84a, 0x2a6fd6, 0x6b3fb5, 0x9aa0a6, 0xf4f4f4];
export function ribbon(points, { colors = RIBBON, r = 0.42, gap = 0.95, seg = 90, twist = 0 } = {}) {
  const g = new THREE.Group();
  const cps = points.map(p => new THREE.Vector3(...p));
  const curve = new THREE.CatmullRomCurve3(cps, false, 'catmullrom', 0.5);
  const N = colors.length;
  for (let i = 0; i < N; i++) {
    const pts = [];
    for (let k = 0; k <= seg; k++) {
      const t = k / seg;
      const p = curve.getPointAt(t);
      const tan = curve.getTangentAt(t);
      let n = new THREE.Vector3(0, 0, 1).cross(tan);
      if (n.lengthSq() < 1e-6) n = new THREE.Vector3(0, 1, 0).cross(tan);
      n.normalize();
      const b = new THREE.Vector3().crossVectors(tan, n).normalize();
      const off = (i - (N - 1) / 2) * gap;
      const tw = twist * t;
      const dir = n.clone().multiplyScalar(Math.cos(tw)).add(b.clone().multiplyScalar(Math.sin(tw)));
      pts.push(p.clone().add(dir.multiplyScalar(off)));
    }
    const c2 = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.5);
    const geo = new THREE.TubeGeometry(c2, seg, r, 6, false);
    const mat = new THREE.MeshStandardMaterial({ color: colors[i], roughness: 0.42 });
    const m = new THREE.Mesh(geo, mat);
    m.castShadow = m.receiveShadow = true;
    g.add(m);
  }
  return g;
}

/* --- flat IDC ribbon: swept rectangular strip with rainbow stripe texture --- */
const ribbonTexCache = new Map();
function ribbonTexture(colors, repeat = 1) {
  const key = colors.join(',') + '|' + repeat;
  if (ribbonTexCache.has(key)) return ribbonTexCache.get(key);
  const n = colors.length, cw = 16, ch = 64;
  const c = document.createElement('canvas');
  c.width = n * cw; c.height = ch;
  const g = c.getContext('2d');
  colors.forEach((hex, i) => {
    g.fillStyle = '#' + hex.toString(16).padStart(6, '0');
    g.fillRect(i * cw, 0, cw, ch);
    // conductor shading: soft highlight down the middle of each strand
    const grd = g.createLinearGradient(i * cw, 0, (i + 1) * cw, 0);
    grd.addColorStop(0, 'rgba(0,0,0,0.28)');
    grd.addColorStop(0.18, 'rgba(255,255,255,0.30)');
    grd.addColorStop(0.5, 'rgba(255,255,255,0.10)');
    grd.addColorStop(0.82, 'rgba(255,255,255,0.22)');
    grd.addColorStop(1, 'rgba(0,0,0,0.30)');
    g.fillStyle = grd; g.fillRect(i * cw, 0, cw, ch);
    g.fillStyle = 'rgba(0,0,0,0.20)';
    g.fillRect(i * cw, 0, 1.4, ch);
  });
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  ribbonTexCache.set(key, t);
  return t;
}

export function flatRibbon(points, { colors = RIBBON, width = 7.6, thick = 0.85, seg = 120, twist = 0, twistEnd = 0, sag = 0 } = {}) {
  const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)), false, 'catmullrom', 0.5);
  const up = new THREE.Vector3(0, 0, 1);
  const rings = [];
  for (let k = 0; k <= seg; k++) {
    const t = k / seg;
    const p = curve.getPointAt(t);
    const tan = curve.getTangentAt(t).normalize();
    let n = up.clone().sub(tan.clone().multiplyScalar(up.dot(tan)));
    if (n.lengthSq() < 1e-6) n.set(0, 1, 0).sub(tan.clone().multiplyScalar(tan.y));
    n.normalize();
    const b = new THREE.Vector3().crossVectors(tan, n).normalize();
    const tw = twist + (twistEnd - twist) * t;
    const dir = n.clone().multiplyScalar(Math.cos(tw)).add(b.clone().multiplyScalar(Math.sin(tw))).normalize();
    const norm = b.clone().multiplyScalar(Math.cos(tw)).add(n.clone().multiplyScalar(-Math.sin(tw))).normalize();
    const sd = sag * Math.sin(Math.PI * t) * (1 - Math.abs(t - 0.5) * 2);
    rings.push({ c: p.clone().add(norm.clone().multiplyScalar(sd)), w: dir, h: norm });
  }
  const n = colors.length, hw = width / 2, ht = thick / 2, sw = width / n;
  const pos = [], nrm = [], col = [], idx = [];
  const c = new THREE.Color();
  const put = (v, nn, ci) => {
    pos.push(v.x, v.y, v.z); nrm.push(nn.x, nn.y, nn.z);
    c.setHex(colors[ci]); col.push(c.r, c.g, c.b);
    return pos.length / 3 - 1;
  };
  const quad = (a, b2, c2, d) => idx.push(a, b2, c2, a, c2, d);
  for (let k = 0; k < seg; k++) {
    const r0 = rings[k], r1 = rings[k + 1];
    for (let i = 0; i < n; i++) {
      const u0 = -hw + i * sw, u1 = u0 + sw;
      // top
      const t0 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u0)).add(r0.h.clone().multiplyScalar(ht)), r0.h.clone().negate(), i);
      const t1 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u1)).add(r0.h.clone().multiplyScalar(ht)), r0.h.clone().negate(), i);
      const t2 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u1)).add(r1.h.clone().multiplyScalar(ht)), r1.h.clone().negate(), i);
      const t3 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u0)).add(r1.h.clone().multiplyScalar(ht)), r1.h.clone().negate(), i);
      quad(t0, t1, t2, t3);
      // bottom
      const b0 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u0)).add(r0.h.clone().multiplyScalar(-ht)), r0.h.clone().negate(), i);
      const b1 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u0)).add(r1.h.clone().multiplyScalar(-ht)), r1.h.clone().negate(), i);
      const b2 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u1)).add(r1.h.clone().multiplyScalar(-ht)), r1.h.clone().negate(), i);
      const b3 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u1)).add(r0.h.clone().multiplyScalar(-ht)), r0.h.clone().negate(), i);
      quad(b0, b1, b2, b3);
    }
    // side walls (only the two outer strands)
    for (const [u, ci, sgn] of [[-hw, 0, -1], [hw, n - 1, 1]]) {
      const nn = r0.w.clone().multiplyScalar(sgn);
      const e0 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u)).add(r0.h.clone().multiplyScalar(-ht)), nn, ci);
      const e1 = put(r0.c.clone().add(r0.w.clone().multiplyScalar(u)).add(r0.h.clone().multiplyScalar(ht)), nn, ci);
      const e2 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u)).add(r1.h.clone().multiplyScalar(ht)), nn, ci);
      const e3 = put(r1.c.clone().add(r1.w.clone().multiplyScalar(u)).add(r1.h.clone().multiplyScalar(-ht)), nn, ci);
      if (sgn > 0) quad(e0, e1, e2, e3); else quad(e0, e3, e2, e1);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  geo.setIndex(idx);
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, metalness: 0.0, side: THREE.DoubleSide });
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = m.receiveShadow = true;
  return m;
}
export function cableTie(pos, r = 6, rot = 0) {
  const g = new THREE.Group();
  const torus = new THREE.Mesh(new THREE.TorusGeometry(r, 0.75, 6, 24, Math.PI * 1.6), MAT.white);
  torus.rotation.z = rot;
  g.add(torus);
  const head = box(3.4, 2.2, 2.6, MAT.white, { r: 0.3 });
  head.position.set(r * Math.cos(rot), r * Math.sin(rot), 0.4);
  g.add(head);
  g.position.set(...pos);
  return g;
}

export function tape(w, l, h = 0.18, rot = 0) {
  const m = box(w, h, l, MAT.tape, { r: 0.08 });
  m.rotation.y = rot;
  m.castShadow = false;
  return m;
}

/** Orient an object built in its local XY plane (normal +Z, width X, height Y)
 *  so that it faces +X (sign=1) or -X (sign=-1): width runs along Y, height along Z. */
export function orientX(obj, sign = 1) {
  const m = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(0, sign, 0),
    new THREE.Vector3(0, 0, 1),
    new THREE.Vector3(sign, 0, 0)
  );
  obj.quaternion.setFromRotationMatrix(m);
  return obj;
}

/** Face +Y (sign=1) or -Y (sign=-1): width along X, height along Z. */
export function orientY(obj, sign = 1) {
  const m = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(sign, 0, 0),
    new THREE.Vector3(0, 0, 1),
    new THREE.Vector3(0, sign, 0),
  );
  obj.quaternion.setFromRotationMatrix(m);
  return obj;
}
