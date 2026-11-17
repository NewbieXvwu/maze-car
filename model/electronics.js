import * as THREE from 'three';
import { MAT, D, box, cyl, at, plane, header, pinRow, jst, screw, textPlane, orientX, orientY } from './helpers.js';
import { PCB, pcbTexture, perfTexture, perfBump, shieldTexture, labelTexture, moduleBottom, sensorCanTexture, makeCanvas, tex } from './textures.js';

/* transparent silkscreen text plane */
export function silk(text, { w = 20, h = 3, size = 64, color = '#f2f1ea', rotate = 0, font = '600' } = {}) {
  const c = makeCanvas(Math.round(w * 40), Math.round(h * 40));
  const g = c.getContext('2d');
  g.clearRect(0, 0, c.width, c.height);
  g.fillStyle = color;
  g.font = `${font} ${size * 0.6}px "Helvetica Neue", Arial, sans-serif`;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(text, c.width / 2, c.height / 2);
  const t = tex(c);
  t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
  const m = new THREE.MeshStandardMaterial({ map: t, transparent: true, roughness: 0.6, side: THREE.DoubleSide, depthWrite: false });
  const p = plane(w, h, m);
  p.rotation.z = rotate;
  return p;
}

/* ------------------------------------------------------------------ */
/*  ESP32-S3 DevKitC-1 board                                          */
/* ------------------------------------------------------------------ */
export function esp32Board() {
  const g = new THREE.Group();
  const W = 25.4, L = 63.5, T = 1.6;
  const pcbMat = new THREE.MeshStandardMaterial({ color: 0x191b1d, roughness: 0.45 });
  const b = box(W, L, T, pcbMat, { r: 0.3 });
  b.position.y = 0; b.position.z = T / 2; g.add(b);

  // silk top
  const c = makeCanvas(512, 1180), gg = c.getContext('2d');
  gg.fillStyle = '#191b1d'; gg.fillRect(0, 0, 512, 1180);
  gg.strokeStyle = '#e8e6da'; gg.fillStyle = '#e8e6da';
  gg.lineWidth = 3;
  gg.strokeRect(46, 40, 420, 1100);
  gg.font = '600 40px "Helvetica Neue", Arial'; gg.textAlign = 'center';
  gg.fillText('ESP32-S3-DevKitC-1', 256, 620);
  gg.font = '500 26px "Helvetica Neue", Arial';
  gg.fillText('Espressif', 256, 670);
  gg.fillText('ESP32-S3', 256, 712);
  gg.font = '500 22px "Helvetica Neue", Arial';
  for (let i = 0; i < 22; i++) {
    gg.fillText(String(i + 1), 86, 110 + i * 44);
    gg.fillText(String(44 - i), 440, 110 + i * 44);
  }
  const st = tex(c);
  st.wrapS = st.wrapT = THREE.ClampToEdgeWrapping;
  const silkMat = new THREE.MeshStandardMaterial({ map: st, transparent: true, roughness: 0.7, depthWrite: false });
  const top = plane(W, L, silkMat);
  top.rotation.x = -Math.PI / 2; top.rotation.z = -Math.PI / 2;
  top.position.z = T + 0.02; g.add(top);

  // shield
  const sh = box(18.2, 17.6, 2.9, MAT.shield, { r: 0.55 });
  sh.position.set(0, -13.8, T + 1.45); g.add(sh);
  const shTex = shieldTexture();
  const shDecal = plane(17.0, 16.4, new THREE.MeshStandardMaterial({ map: shTex, roughness: 0.35, metalness: 0.85 }));
  shDecal.rotation.x = -Math.PI / 2; shDecal.rotation.z = Math.PI / 2;
  shDecal.position.set(0, -13.8, T + 2.92); g.add(shDecal);
  // visible yellow pin headers standing on the board edges (DevKitC-1 look)
  for (const sy of [-(W / 2 - 1.27), (W / 2 - 1.27)]) {
    const hdr = box(2.5, L - 7.0, 8.6, MAT.yellow, { r: 0.3 });
    hdr.position.set(0, sy, T + 4.3); g.add(hdr);
    for (let i = 0; i < 20; i++) {
      const pin = box(1.9, 0.9, 0.35, MAT.gold);
      pin.position.set(0, -26 + i * 2.54, T + 8.75); g.add(pin);
    }
  }
  // exposed components beside the shield
  const chip = box(6.2, 6.2, 0.9, MAT.chip); chip.position.set(3.4, 3.0, T + 0.5); g.add(chip);
  const xtal = box(3.2, 2.4, 0.8, MAT.silver); xtal.position.set(-6.0, -1.0, T + 0.45); g.add(xtal);

  // PCB antenna (rear end)
  const ant = new THREE.Group();
  for (let i = 0; i < 6; i++) {
    const leg = box(1.1, 14, 0.35, MAT.gold);
    leg.position.set(-6.0 + i * 2.4, -27.6, T + 0.18);
    ant.add(leg);
  }
  ant.position.x = 0; g.add(ant);

  // USB-C ports at +Y end
  for (const sx of [-5.3, 5.3]) {
    const shell = box(9.2, 7.6, 3.3, MAT.silver, { r: 0.9 });
    shell.position.set(sx, L / 2 - 1.2, T + 1.55);
    g.add(shell);
    const slot = box(7.6, 5.8, 0.9, MAT.blackGloss, { r: 0.45 });
    slot.position.set(sx, L / 2 + 2.6, T + 1.55);
    g.add(slot);
    const inner = box(6.8, 3.2, 1.2, MAT.darkGrey);
    inner.position.set(sx, L / 2 + 2.2, T + 1.55); g.add(inner);
  }
  // buttons
  for (const [sx, sy] of [[-6.5, 20.0], [6.5, 20.0], [0, 14.0]]) {
    const base = box(6.2, 6.2, 3.6, MAT.black, { r: 0.5 });
    base.position.set(sx, sy, T + 1.8); g.add(base);
    const cap = box(4.0, 4.0, 0.9, MAT.silver, { r: 0.4 });
    cap.position.set(sx, sy, T + 3.9); g.add(cap);
  }
  // RGB LED
  const led = box(3.2, 2.6, 1.1, MAT.white, { r: 0.2 });
  led.position.set(-11.5, 8.0, T + 0.55); g.add(led);
  const led2 = box(2.2, 1.6, 0.35, new THREE.MeshStandardMaterial({ color: 0x223a30, roughness: 0.3 }), { r: 0.15 });
  led2.position.set(-11.5, 8.0, T + 1.15); g.add(led2);

  // yellow pin strips under the board
  for (const sy of [-W / 2 + 2.54, W / 2 - 2.54]) {
    const pr = pinRow(22, 2.54, 9.0);
    pr.position.set(0, sy, -0.2);
    pr.rotation.x = Math.PI; // pins down
    g.add(pr);
  }
  // side silk: board name
  const name = silk('ESP32-S3-WROOM-1', { w: 30, h: 3.4, size: 72 });
  name.rotation.x = -Math.PI / 2;
  name.position.set(0, 0.02, 0.0);
  // skip extra placard
  return g;
}

/* ------------------------------------------------------------------ */
/*  PCB assembly                                                      */
/* ------------------------------------------------------------------ */
export function pcbAssembly() {
  const g = new THREE.Group();
  g.name = 'MainPCB';
  const { w, h } = PCB;
  // substrate
  const body = box(w, h, 1.6, MAT.pcbEdge, { r: 0.35 });
  body.position.z = -0.8; g.add(body);
  // top artwork
  const t = pcbTexture();
  t.anisotropy = 16;
  const topMat = new THREE.MeshStandardMaterial({ map: t, roughness: 0.5, metalness: 0.12, bumpMap: perfBump(w, h, { seed: 33 }), bumpScale: 0.5 });

  // nylon standoffs from the chassis up to the PCB (hidden in the real car, but
  // they explain how the deck is carried and read correctly in renders)
  for (const [sx, sy] of [[-38, -34], [-38, 34], [34, -34], [34, 34]]) {
    const post = new THREE.Mesh(
      new THREE.CylinderGeometry(2.6, 2.6, D.pcb.top - D.plate.top, 14),
      new THREE.MeshStandardMaterial({ color: 0xdcdad2, roughness: 0.7 })
    );
    post.rotation.x = Math.PI / 2;
    post.position.set(sx, sy, -(D.pcb.top - D.plate.top) / 2);
    g.add(post);
    const nut = new THREE.Mesh(new THREE.CylinderGeometry(3.4, 3.4, 1.2, 6),
      new THREE.MeshStandardMaterial({ color: 0xc9ccd0, roughness: 0.35, metalness: 0.8 }));
    nut.rotation.x = Math.PI / 2;
    nut.position.set(sx, sy, -0.8); g.add(nut);
  }
  const top = plane(w, h, topMat);
  top.position.z = 0.012; g.add(top);
  // bottom artwork
  const botTex = perfTexture(w, h, { bottom: true, seed: 33 });
  botTex.repeat.set(1, 1);
  const botMat = new THREE.MeshStandardMaterial({ map: botTex, color: 0x7d9a86, roughness: 0.62, metalness: 0.10, bumpMap: perfBump(w, h, { seed: 33 }), bumpScale: 0.5 });
  const bot = plane(w, h, botMat);
  bot.rotation.x = Math.PI; bot.position.z = -1.612; g.add(bot);

  // every component lives in a mirrored child group so that the physical
  // left/right layout matches the real car (the board artwork uses the same
  // mirrored convention).
  const inner = new THREE.Group();
  inner.name = 'PCBParts';
  inner.scale.y = -1;
  g.add(inner);

  // ---- ESP32 ----
  const esp = esp32Board();
  esp.rotation.z = -Math.PI / 2;          // long axis along the car, USB-C toward the wall
  esp.position.set(10.25, 1.0, 8.6);
  inner.add(esp);
  // female headers under ESP32
  for (const sy of [1.0 - 10.16, 1.0 + 10.16]) {
    const hd = header(1, 22, 2.54, 8.5);
    hd.position.set(10.25, sy, 0);
    inner.add(hd);
  }

  // ---- TB6612 ----
  const tbHeader = header(2, 8, 2.54, 8.5);
  tbHeader.position.set(24, -26.2, 0); inner.add(tbHeader);
  const tb = box(20.5, 20.5, 1.6, MAT.red, { r: 0.3 });
  tb.position.set(24, -36.8, 9.3); inner.add(tb);
  const tbChip = box(7.6, 5.4, 1.0, MAT.chip, { r: 0.15 });
  tbChip.position.set(24, -35.0, 10.6); inner.add(tbChip);
  const tant = box(4.2, 2.6, 1.8, MAT.capTan, { r: 0.2 });
  tant.position.set(17.5, -42.5, 11.0); inner.add(tant);
  for (const [x, y] of [[30.5, -42.0], [30.5, -37.0]]) {
    const c1 = box(2.0, 1.2, 1.0, new THREE.MeshStandardMaterial({ color: 0xb8a06a, roughness: 0.6 }));
    c1.position.set(x, y, 10.6); inner.add(c1);
  }
  const tbSilk = silk('TB6612FNG', { w: 12, h: 2.4, size: 60 });
  tbSilk.rotation.x = -Math.PI / 2; tbSilk.position.set(24, -30.8, 10.15); inner.add(tbSilk);
  const tbLed = box(1.4, 1.0, 0.8, new THREE.MeshStandardMaterial({ color: 0xff3322, emissive: 0x881100, roughness: 0.3 }));
  tbLed.position.set(31.5, -27.0, 10.5); inner.add(tbLed);

  // ---- MPU6050 (vertical, at right edge, faces +X) ----
  const mpuHeader = header(1, 8, 2.54, 8.5);
  mpuHeader.rotation.z = Math.PI / 2;
  mpuHeader.position.set(-10, 38.5, 0); inner.add(mpuHeader);
  const mpu = new THREE.Group();
  const mpuBoard = box(1.6, 16, 21, MAT.bluePcb, { r: 0.25 });
  mpu.add(mpuBoard);
  const mpuChip = box(0.9, 3.2, 3.2, MAT.chip, { r: 0.1 });
  mpuChip.position.x = 1.1; mpuChip.position.z = 5.2; mpu.add(mpuChip);
  const mpuVr = box(0.8, 2.2, 2.2, MAT.chip, { r: 0.1 });
  mpuVr.position.set(1.05, -3.4, 5.2); mpu.add(mpuVr);
  const mpuSilk = silk('MPU6050', { w: 12, h: 2, size: 60 });
  mpuSilk.rotation.x = -Math.PI / 2; mpuSilk.rotation.z = -Math.PI / 2;
  mpuSilk.position.set(0.82, 0, -6.5); mpu.add(mpuSilk);
  mpu.position.set(-10, 38.5, 8.5 + 10.5);
  inner.add(mpu);

  // ---- OLED ----
  const oledHeader = header(1, 4, 2.54, 4.0);
  oledHeader.rotation.z = Math.PI / 2;
  oledHeader.position.set(-41.5, -30, 0); inner.add(oledHeader);
  const oled = new THREE.Group();
  const ob = box(27, 27, 1.6, MAT.bluePcb, { r: 0.4 });
  oled.add(ob);
  const glass = box(25.6, 14.4, 1.4, MAT.oled, { r: 0.3 });
  glass.position.set(0.6, 3.4, 1.45); oled.add(glass);
  const os = silk('0.96 OLED', { w: 16, h: 2.2, size: 54 });
  os.rotation.x = -Math.PI / 2; os.position.set(0, -10.6, 0.85); oled.add(os);
  for (const sy of [-13.6, 13.6]) { const hh = cyl(0.9, 0.9, 1.7, MAT.gold, 12); hh.rotation.x = Math.PI / 2; hh.position.set(sy > 0 ? -13.6 : 13.6, sy, 0.8); oled.add(hh); }
  oled.position.set(-28, -30, 5.6);
  inner.add(oled);

  // ---- Mini-360 buck ----
  const buckHeader = header(1, 4, 2.54, 8.0);
  buckHeader.rotation.z = Math.PI / 2;
  buckHeader.position.set(33.5, -30, 0); inner.add(buckHeader);
  const buck = new THREE.Group();
  const bb = box(17, 11, 1.6, MAT.bluePcb, { r: 0.3 });
  buck.add(bb);
  const ind = box(5.2, 5.2, 4.2, MAT.inductor, { r: 0.5 });
  ind.position.set(-3.0, 0, 2.6); buck.add(ind);
  const pot = box(3.4, 3.4, 2.0, MAT.bluePlastic, { r: 0.3 });
  pot.position.set(4.2, 0, 1.6); buck.add(pot);
  const bc = box(4.0, 4.0, 0.8, MAT.chip, { r: 0.1 }); bc.position.set(1.5, -0.5, 1.0); buck.add(bc);
  const bs = silk('MINI-360', { w: 13, h: 2.0, size: 54 });
  bs.rotation.x = -Math.PI / 2; bs.position.set(0, 0.0, 0.85); buck.add(bs);
  buck.position.set(34.5, -30, 9.4); inner.add(buck);

  // ---- DIP switch ----
  const dip = new THREE.Group();
  const db = box(10.5, 7.2, 4.0, MAT.bluePcb, { r: 0.3 });
  db.position.z = 2.0; dip.add(db);
  for (let i = 0; i < 4; i++) {
    const sw = box(1.5, 3.2, 1.6, MAT.white, { r: 0.2 });
    sw.position.set(-3.6 + i * 2.4, 0.4, 4.5); dip.add(sw);
  }
  dip.position.set(30, 30.5, 0); inner.add(dip);

  // ---- SMD passives: dense 0603 population along the unused board areas ----
  {
    let seed = 20261115;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    const blocks = [
      [3, -15, 18, 17],       // ESP32
      [12, -48, 36, -24],     // TB6612
      [-13, 29, -7, 48],      // MPU
      [-43, -45, -13, -15],   // OLED
      [25, -37, 44, -23],     // buck
      [23, 25, 37, 36],       // DIP
      [-41, -22, -26, 22],    // IDC area
    ];
    const free = (x, y, pad = 3) => {
      if (Math.abs(x) > 41 || Math.abs(y) > 40) return false;
      for (const [x0, y0, x1, y1] of blocks)
        if (x > x0 - pad && x < x1 + pad && y > y0 - pad && y < y1 + pad) return false;
      return true;
    };
    const bodyTan = new THREE.MeshStandardMaterial({ color: 0xc8a56a, roughness: 0.55 });
    const bodyDark = new THREE.MeshStandardMaterial({ color: 0x232528, roughness: 0.5 });
    const padMat = new THREE.MeshStandardMaterial({ color: 0xd8dde0, roughness: 0.28, metalness: 0.95 });
    let placed = 0, guard = 0;
    while (placed < 46 && guard++ < 3000) {
      const x = -40 + rnd() * 80, y = -38 + rnd() * 76;
      if (!free(x, y)) continue;
      const rot = rnd() > 0.5 ? Math.PI / 2 : 0;
      const big = rnd() > 0.86;
      const L = big ? 3.2 : 1.6, Wd = big ? 1.9 : 0.8;
      const body = box(L, Wd, 0.5, rnd() > 0.5 ? bodyTan : bodyDark, { r: 0.08 });
      body.rotation.z = rot; body.position.set(x, y, 0.26); inner.add(body);
      for (const s2 of [-1, 1]) {
        const pad = box(0.45, Wd + 0.16, 0.55, padMat, { r: 0.05 });
        const dx = Math.cos(rot) * s2 * (L / 2 + 0.28);
        const dy = Math.sin(rot) * s2 * (L / 2 + 0.28);
        pad.rotation.z = rot; pad.position.set(x + dx, y + dy, 0.24); inner.add(pad);
      }
      placed++;
    }
    // electrolytic caps in the rear-left free area
    for (const [cx, cy, r, hh] of [[-30, 30, 2.6, 5.4], [-24, 34, 2.4, 5.0], [-34, 12, 3.1, 6.0], [-20, -6, 2.5, 4.6], [-6, -20, 2.2, 4.2]]) {
      const c = cyl(r, r, hh, new THREE.MeshStandardMaterial({ color: 0x2c2f33, roughness: 0.45, metalness: 0.2 }), 24);
      c.position.set(cx, cy, hh / 2 + 0.05); inner.add(c);
      const top = cyl(r * 0.94, r * 0.94, 0.25, new THREE.MeshStandardMaterial({ color: 0x9aa0a4, roughness: 0.3, metalness: 0.85 }), 24);
      top.position.set(cx, cy, hh + 0.1); inner.add(top);
      const stripe = box(r * 1.5, 0.5, 0.3, new THREE.MeshStandardMaterial({ color: 0x1d1f22 }), { r: 0.05 });
      stripe.position.set(cx, cy, hh + 0.22); inner.add(stripe);
    }
    // vias / test pads sprinkled on traces
    for (let i = 0; i < 26; i++) {
      const x = -38 + rnd() * 76, y = -34 + rnd() * 68;
      if (!free(x, y, 1.5)) continue;
      const v = cyl(0.42, 0.42, 0.12, MAT.gold, 10);
      v.position.set(x, y, 0.08); inner.add(v);
    }
  }

  // ---- push button SW2 ----
  const btn = box(6.4, 6.4, 4.6, MAT.black, { r: 0.5 });
  btn.position.set(-24, 34.5, 2.3); inner.add(btn);
  const btnCap = cyl(2.2, 2.2, 1.2, MAT.white, 18);
  btnCap.position.set(-24, 34.5, 5.0); inner.add(btnCap);

  // ---- IDC connectors ----
  const idc1 = idcBox(8, 21.5, 0xc9c9c9);
  idc1.position.set(36, -3, 0); inner.add(idc1);
  const idc2 = idcBox(5, 14.5, 0xc9c9c9);
  idc2.position.set(35, 20, 0); inner.add(idc2);
  // white tape over idc1
  const tp = box(1.0, 20, 0.25, MAT.tape);
  tp.rotation.z = 0.0; tp.position.set(30.0, -3, 11.2); inner.add(tp);

  // ---- JST connectors ----
  const b1 = jst(2); b1.position.set(-40, 10, 0); inner.add(b1);
  const j1 = jst(2); j1.position.set(39.5, -40, 0); j1.rotation.z = -Math.PI / 2; inner.add(j1);
  const j2 = jst(2); j2.position.set(39.5, 39, 0); j2.rotation.z = Math.PI / 2; inner.add(j2);

  // ---- left 4-pin TOF (edge mounted, faces -Y) ----
  const tofL = tof4();
  tofL.position.set(34, -46.2, 9.2);
  orientY(tofL, -1);
  inner.add(tofL);
  const hL = header(1, 4, 2.54, 7.0);
  hL.position.set(34, -41.8, 0); inner.add(hL);
  const brL = box(10, 3.0, 9, MAT.white, { r: 0.6 });
  brL.position.set(34, -43.5, 4.5); inner.add(brL);

  // ---- right 6-pin TOF (edge mounted, faces +Y) ----
  const tofR = tof6();
  tofR.position.set(34, 46.4, 9.4);
  orientY(tofR, 1);
  inner.add(tofR);
  const hR = header(1, 6, 2.54, 7.0);
  hR.position.set(34, 41.6, 0); inner.add(hR);

  // ---- standoffs / brackets to wall ----
  for (const sy of [-34, 34]) {
    const br = box(7, 8, 8, MAT.white, { r: 0.8 });
    br.position.set(44, sy, 4); inner.add(br);
    const sc = screw(1.2, 0.8); sc.rotation.x = -Math.PI / 2; sc.position.set(44, sy, 8.3); inner.add(sc);
  }

  // small white sticker near IDC
  const lbl = labelTexture(['电机', '左/右'], { w: 320, h: 160, ink: '#2c2c2c' });
  const stk = new THREE.MeshStandardMaterial({ map: lbl, roughness: 0.8 });
  const pl = plane(9, 4.5, stk); pl.rotation.x = -Math.PI / 2; pl.position.set(29.5, -12.5, 10.55); inner.add(pl);

  inner.traverse((o) => {
    if (!o.isMesh) return;
    for (const m of (Array.isArray(o.material) ? o.material : [o.material])) {
      m.side = THREE.DoubleSide;
      m.needsUpdate = true;
    }
  });
  g.updateMatrixWorld(true);
  return g;
}

function idcBox(cols, wide, ribbonColor) {
  const g = new THREE.Group();
  const body = box(wide, 7.6, 10.0, MAT.black, { r: 0.4 });
  body.position.z = 5.0; g.add(body);
  const slot = box(wide - 3, 4.6, 1.6, MAT.darkGrey);
  slot.position.z = 10.2; g.add(slot);
  const latchL = box(2.0, 1.2, 3.0, MAT.black, { r: 0.2 });
  latchL.position.set(-wide / 2 + 1.4, -3.6, 8.4); g.add(latchL);
  const latchR = latchL.clone(); latchR.position.y = 3.6; g.add(latchR);
  return g;
}

/* ------------------------------------------------------------------ */
/*  VL53L0X modules                                                   */
/* ------------------------------------------------------------------ */
export function tofBoard(pins = 6, W = 25, H = 13) {
  const g = new THREE.Group();
  const b = box(W, H, 1.6, MAT.bluePcb, { r: 0.3 });
  g.add(b);
  // sensor window
  const win = box(5.2, 4.4, 0.9, MAT.blackGloss, { r: 0.2 });
  win.position.set(0, H / 2 - 4.6, 0.85); g.add(win);
  const frame = box(7.0, 6.0, 0.5, MAT.shield, { r: 0.25 });
  frame.position.set(0, H / 2 - 4.6, 0.55); g.add(frame);
  // pins along top edge (pointing -Z)
  const pitch = 2.54;
  for (let i = 0; i < pins; i++) {
    const p = box(0.62, 0.62, 5.6, MAT.gold);
    p.position.set((i - (pins - 1) / 2) * pitch, H / 2 + 1.0, -2.6);
    g.add(p);
  }
  // header plastic on the back
  const hp = box(pins * pitch + 0.5, 2.8, 6.2, MAT.black, { r: 0.2 });
  hp.position.set(0, H / 2 + 1.2, -0.9); g.add(hp);
  // mounting holes
  for (const sx of [-W / 2 + 2.4, W / 2 - 2.4]) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.5, 0.35, 6, 14), MAT.gold);
    ring.position.set(sx, H / 2 - 2.2, 0.85); g.add(ring);
  }
  // label
  const lbl = silk('VL53L0X', { w: 10, h: 1.8, size: 56 });
  lbl.rotation.x = -Math.PI / 2; lbl.rotation.z = -Math.PI / 2;
  lbl.position.set(W / 2 - 4.0, -H / 2 + 4.2, 1.0); g.add(lbl);
  // tiny chips on back
  const c1 = box(3.0, 3.0, 0.6, MAT.chip, { r: 0.1 });
  c1.position.set(-2, -1.5, -1.1); g.add(c1);
  return g;
}
export function tof6() { return tofBoard(6, 25, 13); }
export function tof4() { return tofBoard(4, 20, 12); }

/* ------------------------------------------------------------------ */
/*  front wall (perfboard with TOF)                                    */
/* ------------------------------------------------------------------ */
export function frontWall() {
  const g = new THREE.Group();
  const { x0, x1, w, h, z0 } = D.wall;
  const t = perfTexture(w, h, { seed: 91 });
  const faceMat = new THREE.MeshStandardMaterial({ map: t, roughness: 0.55, metalness: 0.1, bumpMap: perfBump(w, h, { seed: 91 }), bumpScale: 0.55 });
  const backMat = new THREE.MeshStandardMaterial({ map: perfTexture(w, h, { seed: 91, bottom: true }), roughness: 0.55, bumpMap: perfBump(w, h, { seed: 91 }), bumpScale: 0.55 });
  const wall = box(x1 - x0, w, h, MAT.pcbEdge, { r: 0.4 });
  wall.position.set((x0 + x1) / 2, 0, z0 + h / 2);
  g.add(wall);
  const front = plane(w, h, faceMat);
  orientX(front, 1);                                // +X normal, width along Y, height along Z
  front.position.set(x1 + 0.013, 0, z0 + h / 2); g.add(front);
  const back = plane(w, h, backMat);
  orientX(back, -1);                                 // -X normal
  back.position.set(x0 - 0.013, 0, z0 + h / 2); g.add(back);

  // front 6-pin TOF, at the top, facing +X
  const tof = tof6();
  orientX(tof, 1);                       // face +X, long axis horizontal
  tof.position.set(x1 + 2.2, 0, z0 + h - 6.4);
  g.add(tof);
  // black header on the rear side where the ribbon plugs in
  const hr = header(1, 6, 2.54, 6.5);
  hr.rotation.y = Math.PI / 2;
  hr.position.set(x0 - 1.2, 0, z0 + h - 9.5);
  g.add(hr);
  // white tape over it
  const tp = box(0.3, 18, 7, MAT.tape);
  tp.position.set(x0 - 2.2, 0, z0 + h - 9.0); g.add(tp);
  // screws into the printed brackets
  for (const sy of [-27, 27]) {
    const sc = screw(1.3, 1.0); sc.rotation.z = -Math.PI / 2; sc.position.set(x1 + 4.6, sy, z0 + 5.5); g.add(sc);
  }
  // white printed bracket feet along the bottom of the wall
  for (const sy of [-27, 27]) {
    const ft = box(4.5, 26, 9, MAT.white, { r: 0.9 });
    ft.position.set(x1 + 0.4, sy, z0 + 5.5); g.add(ft);
  }

  // ---- solder side of the perfboard: joint blobs + hand-routed jumpers ----
  {
    let sd = 4242;
    const R = () => (sd = (sd * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    const solderMat = new THREE.MeshStandardMaterial({ color: 0xb9bcc0, roughness: 0.32, metalness: 0.85 });
    for (let i = 0; i < 90; i++) {
      const y = -w / 2 + 2 + R() * (w - 4);
      const z = z0 + 3 + R() * (h - 8);
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.75, 8, 6), solderMat);
      b.scale.set(0.55, 1, 1);
      b.position.set(x0 - 0.45, y, z);
      g.add(b);
    }
    // (jumpers omitted: they read as floating wires in silhouette)
  }
  return g;
}
