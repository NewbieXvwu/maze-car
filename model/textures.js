import * as THREE from 'three';

const TAU = Math.PI * 2;

export function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

export function tex(canvas, { repeat = [1, 1], aniso = 8, srgb = true } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = aniso;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  return t;
}

function rnd(seed) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

/* ------------------------------------------------------------------ */
/*  perforated prototyping board (洞洞板)                              */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  surface weathering: fine dust / scuffs / edge darkening            */
/* ------------------------------------------------------------------ */
export function weather(g, W, H, seed = 1, amount = 1) {
  const R = rnd(seed);
  // soft dust patches
  for (let i = 0; i < 26; i++) {
    const x = R() * W, y = R() * H, r = (12 + R() * 70) * amount;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    const a = 0.030 + R() * 0.045;
    grd.addColorStop(0, `rgba(150,168,150,${a.toFixed(3)})`);
    grd.addColorStop(1, 'rgba(150,168,150,0)');
    g.fillStyle = grd; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill();
  }
  // micro speckle
  for (let i = 0; i < 4200; i++) {
    const x = R() * W, y = R() * H;
    const s = R() < 0.85 ? 0.8 : 1.7;
    g.fillStyle = R() > 0.55 ? `rgba(210,225,205,${(0.02 + R() * 0.05).toFixed(3)})`
                             : `rgba(0,12,6,${(0.03 + R() * 0.07).toFixed(3)})`;
    g.fillRect(x, y, s, s);
  }
  // edge darkening on all four sides
  const e = Math.min(W, H) * 0.035;
  const sides = [
    [0, 0, W, e, 'top'], [0, H - e, W, e, 'bottom'],
    [0, 0, e, H, 'left'], [W - e, 0, e, H, 'right'],
  ];
  for (const [x, y, w2, h2, side] of sides) {
    let grd;
    if (side === 'top') grd = g.createLinearGradient(0, y, 0, y + h2);
    else if (side === 'bottom') grd = g.createLinearGradient(0, y + h2, 0, y);
    else if (side === 'left') grd = g.createLinearGradient(x, 0, x + w2, 0);
    else grd = g.createLinearGradient(x + w2, 0, x, 0);
    grd.addColorStop(0, 'rgba(0,10,5,0.30)');
    grd.addColorStop(1, 'rgba(0,10,5,0)');
    g.fillStyle = grd; g.fillRect(x, y, w2, h2);
  }
}

export function noiseTex(size = 256, seed = 3) {
  const c = makeCanvas(size, size), g = c.getContext('2d');
  const R = rnd(seed);
  g.fillStyle = '#b4b4b4'; g.fillRect(0, 0, size, size);
  for (let i = 0; i < size * size * 0.10; i++) {
    const v = 150 + Math.floor(R() * 105);
    g.fillStyle = `rgb(${v},${v},${v})`;
    g.fillRect(R() * size, R() * size, 1 + R() * 2.2, 1 + R() * 2.2);
  }
  for (let i = 0; i < 40; i++) {
    const x = R() * size, y = R() * size, r = 6 + R() * 26;
    const grd = g.createRadialGradient(x, y, 0, x, y, r);
    grd.addColorStop(0, `rgba(255,255,255,${(0.05 + R() * 0.10).toFixed(3)})`);
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill();
  }
  return tex(c, { repeat: [1, 1], srgb: false });
}

export function perfTexture(wmm, hmm, { bottom = false, letters = false, seed = 7, holes = true } = {}) {
  const ppm = 18;
  const W = Math.round(wmm * ppm), H = Math.round(hmm * ppm);
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const R = rnd(seed);
  // substrate
  const grad = g.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, '#062f1c');
  grad.addColorStop(0.5, '#083a22');
  grad.addColorStop(1, '#052a18');
  g.fillStyle = grad; g.fillRect(0, 0, W, H);
  // subtle mottling
  for (let i = 0; i < 220; i++) {
    g.fillStyle = `rgba(${R() < 0.5 ? '0,0,0' : '255,255,255'},${0.012 + R() * 0.02})`;
    const rr = 8 + R() * 40;
    g.beginPath(); g.arc(R() * W, R() * H, rr, 0, TAU); g.fill();
  }
  const pitch = 2.54 * ppm;
  const nx = Math.round(wmm / 2.54), ny = Math.round(hmm / 2.54);
  const ox = (W - (nx - 1) * pitch) / 2, oy = (H - (ny - 1) * pitch) / 2;
  if (holes) {
    for (let iy = 0; iy < ny; iy++) {
      for (let ix = 0; ix < nx; ix++) {
        const x = ox + ix * pitch, y = oy + iy * pitch;
        // copper annular ring
        const rg = g.createRadialGradient(x - 1.4, y - 1.4, 1, x, y, pitch * 0.38);
        rg.addColorStop(0, '#8f8054');
        rg.addColorStop(0.55, '#5f5738');
        rg.addColorStop(1, '#3b3626');
        g.fillStyle = rg;
        g.beginPath(); g.arc(x, y, pitch * 0.335, 0, TAU); g.fill();
        // drilled hole (bigger, reads as a real perfboard at render distance)
        const hg = g.createRadialGradient(x - pitch * 0.07, y - pitch * 0.07, 0.2, x, y, pitch * 0.29);
        hg.addColorStop(0, '#050505');
        hg.addColorStop(0.55, '#101010');
        hg.addColorStop(1, '#2a2a2a');
        g.fillStyle = hg;
        g.beginPath(); g.arc(x, y, pitch * 0.29, 0, TAU); g.fill();
        // tiny highlight
        g.strokeStyle = 'rgba(255,255,255,0.10)'; g.lineWidth = 0.7;
        g.beginPath(); g.arc(x, y, pitch * 0.41, Math.PI * 0.9, Math.PI * 1.6); g.stroke();
      }
    }
  }
  if (bottom) {
    // solder blobs on many pads + wire jumpers
    for (let i = 0; i < 900; i++) {
      const x = R() * W, y = R() * H;
      g.fillStyle = `rgba(205,210,214,${0.35 + R() * 0.5})`;
      g.beginPath(); g.arc(x, y, 1 + R() * 3.2, 0, TAU); g.fill();
    }
    for (let i = 0; i < 26; i++) {
      g.strokeStyle = `rgba(212,216,220,${0.5 + R() * 0.45})`;
      g.lineWidth = 1.2 + R() * 2;
      const x0 = R() * W, y0 = R() * H;
      g.beginPath(); g.moveTo(x0, y0);
      let x = x0, y = y0;
      for (let k = 0; k < 3; k++) { x += (R() - 0.5) * 90; y += (R() - 0.5) * 90; g.lineTo(x, y); }
      g.stroke();
    }
  }
  if (letters) {
    g.save();
    g.fillStyle = 'rgba(240,240,235,0.88)';
    g.font = `600 ${Math.round(pitch * 0.62)}px "Helvetica Neue", Arial, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let i = 0; i < nx; i++) {
      const x = ox + i * pitch;
      const ch = String.fromCharCode(65 + (i % 26));
      g.fillText(ch, x, oy - pitch * 0.95);
      g.fillText(ch, x, oy + (ny - 1) * pitch + pitch * 0.95);
    }
    g.font = `600 ${Math.round(pitch * 0.5)}px "Helvetica Neue", Arial, sans-serif`;
    for (let j = 0; j < ny; j++) {
      const y = oy + j * pitch;
      g.fillText(String(j + 1), ox - pitch * 0.95, y);
      g.fillText(String(j + 1), ox + (nx - 1) * pitch + pitch * 0.95, y);
    }
    g.restore();
  }
  // edge bevel highlight
  g.strokeStyle = 'rgba(180,255,205,0.22)'; g.lineWidth = 3;
  g.strokeRect(1.5, 1.5, W - 3, H - 3);
  weather(g, W, H, seed * 7 + 13, 1);
  return tex(c);
}


/* ------------------------------------------------------------------ */
/*  grayscale bump map for the perfboards (holes read as recesses)     */
/* ------------------------------------------------------------------ */
export function perfBump(wmm, hmm, { seed = 7 } = {}) {
  const ppm = 18;
  const W = Math.round(wmm * ppm), H = Math.round(hmm * ppm);
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const R = rnd(seed + 991);
  g.fillStyle = '#8c8c8c'; g.fillRect(0, 0, W, H);
  for (let i = 0; i < 160; i++) {               // faint surface waviness
    g.fillStyle = `rgba(${R() < 0.5 ? '0,0,0' : '255,255,255'},0.03)`;
    g.beginPath(); g.arc(R() * W, R() * H, 10 + R() * 50, 0, TAU); g.fill();
  }
  const pitch = 2.54 * ppm;
  const nx = Math.round(wmm / 2.54), ny = Math.round(hmm / 2.54);
  const ox = (W - (nx - 1) * pitch) / 2, oy = (H - (ny - 1) * pitch) / 2;
  for (let iy = 0; iy < ny; iy++) {
    for (let ix = 0; ix < nx; ix++) {
      const x = ox + ix * pitch, y = oy + iy * pitch;
      const rg = g.createRadialGradient(x, y, pitch * 0.22, x, y, pitch * 0.36);
      rg.addColorStop(0, 'rgba(140,140,140,0.30)');   // raised pad lip
      rg.addColorStop(0.6, 'rgba(140,140,140,0.0)');
      rg.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = rg;
      g.beginPath(); g.arc(x, y, pitch * 0.36, 0, TAU); g.fill();
      const hg = g.createRadialGradient(x, y, 0, x, y, pitch * 0.22);
      hg.addColorStop(0, '#000000');                    // drilled hole
      hg.addColorStop(0.75, '#141414');
      hg.addColorStop(1, '#787878');
      g.fillStyle = hg;
      g.beginPath(); g.arc(x, y, pitch * 0.22, 0, TAU); g.fill();
    }
  }
  const t = tex(c);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  return t;
}

/* ------------------------------------------------------------------ */
/*  main PCB top silk + traces                                        */
/* ------------------------------------------------------------------ */
export const PCB = { w: 91.44, h: 88.9 };

export function pcbTexture() {
  const ppm = 20;
  const W = Math.round(PCB.w * ppm), H = Math.round(PCB.h * ppm);
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const R = rnd(202611);
  const px = (x) => (x / PCB.w + 0.5) * W;
  const py = (y) => (0.5 + y / PCB.h) * H;   // +y = board left -> canvas bottom
  // mask
  const grad = g.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, '#0a3c24');
  grad.addColorStop(0.45, '#08351f');
  grad.addColorStop(1, '#062c1a');
  g.fillStyle = grad; g.fillRect(0, 0, W, H);
  for (let i = 0; i < 120; i++) {
    g.fillStyle = `rgba(255,255,255,${0.012 + R() * 0.02})`;
    g.beginPath(); g.arc(R() * W, R() * H, 10 + R() * 90, 0, TAU); g.fill();
  }

  const pitch = 2.54 * ppm;
  const nx = 36, ny = 35;
  const ox = W / 2 - (nx - 1) * pitch / 2, oy = H / 2 - (ny - 1) * pitch / 2;

  // traces (under the holes)
  g.lineCap = 'round'; g.lineJoin = 'round';
  for (let i = 0; i < 120; i++) {
    const x0 = ox + Math.floor(R() * nx) * pitch, y0 = oy + Math.floor(R() * ny) * pitch;
    const horiz = R() < 0.5;
    const x1 = horiz ? x0 + (Math.floor(R() * 8) - 4) * pitch : x0;
    const y1 = horiz ? y0 : y0 + (Math.floor(R() * 8) - 4) * pitch;
    const x2 = horiz ? x1 : x1 + (Math.floor(R() * 3) - 1) * pitch;
    const y2 = horiz ? y1 + (Math.floor(R() * 3) - 1) * pitch : y1;
    g.strokeStyle = 'rgba(4,52,29,0.85)'; g.lineWidth = pitch * 0.44;
    g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.lineTo(x2, y2); g.stroke();
    g.strokeStyle = 'rgba(38,150,92,0.55)'; g.lineWidth = pitch * 0.26;
    g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.lineTo(x2, y2); g.stroke();
  }

  // plated holes
  for (let iy = 0; iy < ny; iy++) {
    for (let ix = 0; ix < nx; ix++) {
      const x = ox + ix * pitch, y = oy + iy * pitch;
      const rg = g.createRadialGradient(x - 1, y - 1, 0.4, x, y, pitch * 0.31);
      rg.addColorStop(0, '#b7a26a'); rg.addColorStop(0.62, '#8a7a4a'); rg.addColorStop(1, '#4a4226');
      g.fillStyle = rg;
      g.beginPath(); g.arc(x, y, pitch * 0.31, 0, TAU); g.fill();
      g.fillStyle = '#0a0a0a';
      g.beginPath(); g.arc(x, y, pitch * 0.20, 0, TAU); g.fill();
    }
  }

  // component pads (rectangular, tinned)
  function pads(x0, y0, x1, y1, cols, rows) {
    const w = Math.abs(px(x1) - px(x0)), h = Math.abs(py(y1) - py(y0));
    const left = Math.min(px(x0), px(x1)), top = Math.min(py(y0), py(y1));
    for (let r = 0; r < rows; r++) for (let c2 = 0; c2 < cols; c2++) {
      const cx = left + (c2 + 0.5) * w / cols, cy = top + (r + 0.5) * h / rows;
      g.fillStyle = '#c2b076';
      g.fillRect(cx - pitch * 0.3, cy - pitch * 0.3, pitch * 0.6, pitch * 0.6);
      g.fillStyle = '#0b0b0b';
      g.beginPath(); g.arc(cx, cy, pitch * 0.17, 0, TAU); g.fill();
    }
  }
  // ESP32 dual row 2x22
  pads(-21.5, 1.0 + 10.16, 41.0, 1.0 + 10.16, 22, 1);
  pads(-21.5, 1.0 - 10.16, 41.0, 1.0 - 10.16, 22, 1);
  // TB6612 2x8
  pads(15.5, -25.2, 33.3, -25.2, 8, 1);
  pads(15.5, -30.2, 33.3, -30.2, 8, 1);
  // MPU 1x8 vertical
  pads(-22, 40.5, 6.8, 40.5, 8, 1);
  // OLED 1x4
  pads(-42, -16.5, -27, -16.5, 4, 1);
  // buck 1x4
  pads(28, -25, 39, -25, 4, 1);
  // DIP 2x4
  pads(26, 26, 34, 30, 4, 2);
  // TOF L 1x4 / TOF R 1x6
  pads(30.5, -41.5, 38.5, -41.5, 4, 1);
  pads(30.5, 41.5, 43.2, 41.5, 6, 1);
  // IDC headers
  pads(30, -9, 44, -9, 8, 2);
  pads(30, 16, 40, 16, 5, 2);
  // motor / battery JST
  pads(34, -38, 39, -38, 2, 1);
  pads(34, 35.5, 39, 35.5, 2, 1);
  pads(-38, 10, -33, 10, 2, 1);

  // silk
  g.strokeStyle = 'rgba(252,252,248,0.96)'; g.lineWidth = 3.4;
  g.fillStyle = 'rgba(248,248,242,0.95)';
  const F = (s) => `${s}px "Helvetica Neue", Arial, sans-serif`;
  g.textBaseline = 'middle';
  // module outlines
  g.strokeRect(px(-24), py(23), 66 * ppm, 44 * ppm);            // ESP32 zone
  g.strokeRect(px(13), py(-22), 24 * ppm, 46 * ppm);            // TB6612 zone
  g.strokeRect(px(-44), py(-16.5), 28 * ppm, 20 * ppm);         // OLED zone
  g.strokeRect(px(26), py(-27), 15 * ppm, 14 * ppm);            // buck
  g.strokeRect(px(24.5), py(34), 11 * ppm, 10 * ppm);           // DIP
  // labels
  g.font = `800 ${Math.round(2.05 * ppm)}px "Helvetica Neue", Arial, sans-serif`;
  g.save(); g.translate(px(-17), py(15)); g.rotate(-Math.PI / 2); g.fillText('U1  ESP32-S3', 0, 0); g.restore();
  g.save(); g.translate(px(21.5), py(-17.5)); g.fillText('U2  TB6612', 0, 0); g.restore();
  g.save(); g.translate(px(3), py(36)); g.fillText('U3  MPU6050', 0, 0); g.restore();
  g.font = `700 ${Math.round(1.55 * ppm)}px "Helvetica Neue", Arial, sans-serif`;
  g.fillText('OLED 0.96"', px(-42.5), py(-23.5));
  g.fillText('5V REG', px(28.5), py(-30.5));
  g.fillText('SW1 DIP', px(24.5), py(24.5));
  g.fillText('SW2 START', px(-25), py(35.5));
  g.fillText('BT1', px(-40), py(6.2));
  g.fillText('J1 MOTOR L', px(19.5), py(-42.2));
  g.fillText('J2 MOTOR R', px(19.5), py(39.0));
  g.fillText('TOF L', px(30), py(-44.0));
  g.fillText('TOF R', px(30), py(37.3));
  g.fillText('IDC1', px(26.5), py(-13.5));
  g.fillText('IDC2', px(26.5), py(11.5));
  // corner / edge text
  g.font = `600 ${Math.round(1.15 * ppm)}px "Helvetica Neue", Arial, sans-serif`;
  g.fillText('maze-car PCB', px(-40), py(-33));
  g.fillText('2L  1.0mm hole   2026-11', px(-14), py(-37.5));
  g.fillText('maze-car PCB', px(16), py(33.4));
  g.fillText('2026-11', px(33), py(-18));
  // small test points
  for (let i = 0; i < 14; i++) {
    g.beginPath(); g.arc(px(-38 + i * 5.4), py(28), 3.4, 0, TAU); g.fill();
  }
  // edge highlight
  g.strokeStyle = 'rgba(255,255,255,0.25)'; g.lineWidth = 3;
  g.strokeRect(1.5, 1.5, W - 3, H - 3);
  weather(g, W, H, 4242, 1.2);
  return tex(c);
}

/* ------------------------------------------------------------------ */
/*  metal shield etch                                                 */
/* ------------------------------------------------------------------ */
export function shieldTexture() {
  const W = 1024, H = 420;
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, '#b9bec3'); grad.addColorStop(0.35, '#d8dcdf');
  grad.addColorStop(0.55, '#a8adb2'); grad.addColorStop(1, '#c9ced2');
  g.fillStyle = grad; g.fillRect(0, 0, W, H);
  // brushed
  for (let i = 0; i < 520; i++) {
    g.strokeStyle = `rgba(${Math.random() < 0.5 ? '80,86,90' : '255,255,255'},${0.02 + Math.random() * 0.04})`;
    g.lineWidth = 0.6 + Math.random() * 1.2;
    const y = Math.random() * H;
    g.beginPath(); g.moveTo(0, y); g.lineTo(W, y + (Math.random() - 0.5) * 3); g.stroke();
  }
  // etched text
  g.fillStyle = 'rgba(52,58,62,0.82)';
  g.font = '600 64px "Helvetica Neue", Arial, sans-serif';
  g.textAlign = 'center';
  g.fillText('ESP32-S3-WROOM-1', W / 2, 196);
  g.font = '600 46px "Helvetica Neue", Arial, sans-serif';
  g.fillText('N8R2', W / 2 - 40, 272);
  g.font = '400 30px "Helvetica Neue", Arial, sans-serif';
  g.fillText('FCC ID · 2AC7Z-ESPS3WROOM1', W / 2, 330);
  // embossed borders
  g.strokeStyle = 'rgba(255,255,255,0.35)'; g.lineWidth = 4;
  g.strokeRect(10, 10, W - 20, H - 20);
  return tex(c);
}

/* ------------------------------------------------------------------ */
/*  white marker labels / tape                                        */
/* ------------------------------------------------------------------ */
export function labelTexture(lines, { w = 512, h = 256, bg = '#f4f2ea', ink = '#303030' } = {}) {
  const c = makeCanvas(w, h), g = c.getContext('2d');
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  // paper grain
  for (let i = 0; i < 1600; i++) {
    g.fillStyle = `rgba(0,0,0,${Math.random() * 0.03})`;
    g.fillRect(Math.random() * w, Math.random() * h, 1.5, 1.5);
  }
  g.fillStyle = ink;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  const n = lines.length;
  lines.forEach((ln, i) => {
    g.font = `600 ${Math.round(h * (n > 1 ? 0.2 : 0.3))}px "Helvetica Neue", Arial, sans-serif`;
    g.fillText(ln, w / 2, h * (i + 0.5) / n);
  });
  return tex(c);
}

/* battery wrap label */
export function batteryTexture() {
  const W = 1024, H = 512;
  const c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#111214'; g.fillRect(0, 0, W, H);
  g.fillStyle = '#1a1c1f';
  g.fillRect(0, 0, W, 60); g.fillRect(0, H - 60, W, 60);
  g.fillStyle = '#e8e4da';
  g.font = '700 66px "Helvetica Neue", Arial, sans-serif'; g.textAlign = 'center';
  g.fillText('18650  ×2', W / 2, 150);
  g.font = '400 34px "Helvetica Neue", Arial, sans-serif';
  g.fillStyle = '#bfc3c6';
  g.fillText('7.4V  2600mAh  19.24Wh', W / 2, 220);
  g.fillStyle = '#c9a94a';
  g.fillRect(90, 280, 844, 6);
  g.font = '400 26px "Helvetica Neue", Arial, sans-serif'; g.fillStyle = '#8d9297';
  g.fillText('LITHIUM ION BATTERY PACK', W / 2, 340);
  g.fillText('CAUTION: DO NOT SHORT CIRCUIT', W / 2, 384);
  return tex(c);
}

/* generic dark PCB bottom for modules */
export function moduleBottom(color = '#123a6b') {
  const W = 256, H = 256;
  const c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = color; g.fillRect(0, 0, W, H);
  g.strokeStyle = 'rgba(220,200,120,0.75)'; g.lineWidth = 2;
  for (let i = 0; i < 20; i++) {
    g.beginPath(); g.moveTo(0, i * 14); g.lineTo(W, i * 14 + (i % 2 ? 18 : -10)); g.stroke();
  }
  for (let i = 0; i < 12; i++) {
    g.fillStyle = 'rgba(225,205,125,0.85)';
    g.beginPath(); g.arc(20 + i * 19, 30 + (i % 3) * 40, 5, 0, TAU); g.fill();
  }
  return tex(c);
}

/* metal can (TOF sensor) */
export function sensorCanTexture() {
  const W = 128, H = 128;
  const c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#15181b'; g.fillRect(0, 0, W, H);
  g.strokeStyle = 'rgba(200,206,210,0.35)'; g.lineWidth = 2;
  g.strokeRect(12, 12, W - 24, H - 24);
  g.fillStyle = 'rgba(90,160,255,0.10)';
  g.fillRect(20, 20, W - 40, H - 40);
  return tex(c);
}
