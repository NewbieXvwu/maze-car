import * as THREE from 'three';
import { MAT, D, box, cyl, at, plane, header, pinRow, jst, screw, wire, ribbon, flatRibbon, cableTie, tape, textPlane, orientY } from './helpers.js';
import { perfTexture, perfBump, batteryTexture, labelTexture, makeCanvas, tex, noiseTex } from './textures.js';

const PLATE = D.plate;
export const PCB_OFFSET_X = D.pcb.front - 45.72;   // 3.28

/* ------------------------------------------------------------------ */
/*  chassis plate                                                      */
/* ------------------------------------------------------------------ */
export function chassis() {
  const g = new THREE.Group();
  g.name = 'ChassisPlate';
  const t = perfTexture(PLATE.l, PLATE.w, { seed: 5 });
  const nz = noiseTex(256, 5); nz.repeat.set(PLATE.l / 18, PLATE.w / 18);
  const topMat = new THREE.MeshStandardMaterial({ map: t, roughness: 0.55, metalness: 0.08, roughnessMap: nz, bumpMap: perfBump(PLATE.l, PLATE.w, { seed: 5 }), bumpScale: 0.55 });
  const body = box(PLATE.l, PLATE.w, PLATE.t, MAT.pcbEdge, { r: 0.5 });
  body.position.z = PLATE.top - PLATE.t / 2;
  g.add(body);

  const top = plane(PLATE.l, PLATE.w, topMat);
  top.rotation.x = 0;
  top.position.z = PLATE.top + 0.012;
  g.add(top);

  const bt = perfTexture(PLATE.l, PLATE.w, { seed: 51, bottom: true, letters: false });
  const botMat = new THREE.MeshStandardMaterial({ map: bt, roughness: 0.6, metalness: 0.12, bumpMap: perfBump(PLATE.l, PLATE.w, { seed: 51 }), bumpScale: 0.55 });
  const bot = plane(PLATE.l, PLATE.w, botMat);
  bot.rotation.x = Math.PI;
  bot.position.z = PLATE.top - PLATE.t - 0.012;
  g.add(bot);

  // alphabet / row labels on the underside (as seen in the reference)
  const lblC = makeCanvas(2048, 256), lg = lblC.getContext('2d');
  lg.clearRect(0, 0, 2048, 256);
  lg.fillStyle = 'rgba(238,238,230,0.92)';
  lg.font = '600 54px "Helvetica Neue", Arial';
  lg.textAlign = 'center'; lg.textBaseline = 'middle';
  for (let i = 0; i < 40; i++) {
    const ch = String.fromCharCode(65 + (i % 26));
    lg.fillText(ch, 40 + i * 50, 128);
  }
  const lt = tex(lblC); lt.wrapS = lt.wrapT = THREE.ClampToEdgeWrapping;
  const lm = new THREE.MeshStandardMaterial({ map: lt, transparent: true, roughness: 0.7, depthWrite: false });
  const letters = plane(130, 16, lm);
  letters.rotation.set(Math.PI, 0, 0);
  letters.position.set(0, 24, PLATE.top - PLATE.t - 0.02);
  g.add(letters);

  // long gold pin rows on the underside
  for (const [px, py, n] of [[-6, -8, 4], [12, 12, 4], [30, -18, 3]]) {
    const pr = pinRow(n, 2.54, 8, MAT.gold);
    pr.rotation.x = Math.PI;                 // pins down
    pr.position.set(px, py, PLATE.top - PLATE.t - 0.1);
    g.add(pr);
  }
  // small blue module on the underside
  const mod = box(13, 10, 1.6, MAT.bluePcb, { r: 0.4 });
  mod.position.set(-34, -22, 9.3); g.add(mod);
  const modChip = box(4, 4, 0.7, MAT.chip);
  modChip.position.set(-34, -22, 8.3); g.add(modChip);

  // tape strips across the underside
  for (const px of [-8, 26]) {
    const tp = box(14, PLATE.w - 4, 0.18, MAT.tape, { r: 0.06 });
    tp.position.set(px, 0, PLATE.top - PLATE.t - 0.16);
    g.add(tp);
  }
  // silver wire jumpers on the underside
  const wr = wire([[-30, 20, 10.2], [-20, 26, 10.1], [-8, 24, 10.2], [2, 16, 10.1]], 0xd8dadd, 0.5, 0.4, 40);
  g.add(wr);
  const wr2 = wire([[-44, -6, 10.2], [-34, -2, 10.1], [-24, -6, 10.2]], 0xd8dadd, 0.45, 0.4, 30);
  g.add(wr2);

  // corner screws
  for (const [sx, sy] of [[-64, -40], [-64, 40], [62, -40], [62, 40]]) {
    const s = screw(1.5, 0.9);
    s.position.set(sx, sy, PLATE.top - PLATE.t - 0.9);
    s.rotation.x = Math.PI;
    g.add(s);
  }
  return g;
}

/* ------------------------------------------------------------------ */
/*  wheel                                                             */
/* ------------------------------------------------------------------ */
export function wheel() {
  const g = new THREE.Group();
  const R = D.wheel.r, W = D.wheel.w;
  // tire profile (radius, y)
  const pts = [
    [14.4, -W / 2], [17.4, -W / 2], [19.5, -W / 2 + 0.7], [20.7, -W / 2 + 1.9],
    [21.15, -W / 2 + 3.6], [21.15, W / 2 - 3.6], [20.7, W / 2 - 1.9],
    [19.5, W / 2 - 0.7], [17.4, W / 2], [14.4, W / 2], [14.4, -W / 2],
  ].map(([r, y]) => new THREE.Vector2(r, y));
  const tireGeo = new THREE.LatheGeometry(pts, 56);
  const tire = new THREE.Mesh(tireGeo, MAT.rubber);
  tire.castShadow = tire.receiveShadow = true;
  g.add(tire);

  // tread lugs, two staggered rows
  for (let row = 0; row < 2; row++) {
    const n = 34;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + (row ? Math.PI / n : 0);
      const lug = box(2.5, 0.40 * W, 0.85, MAT.rubber, { r: 0.22 });
      // local: x tangential, y axial, z radial
      const rad = R - 0.22;
      lug.position.set(Math.cos(a) * rad, (row ? 0.25 : -0.25) * W, Math.sin(a) * rad);
      lug.rotation.y = -a - Math.PI / 2;
      g.add(lug);
    }
  }
  // white hub body
  const hub = cyl(14.3, 14.3, W - 0.6, MAT.whiteGloss, 48);
  g.add(hub);
  // outer/inner face plates slightly inset
  for (const sy of [-1, 1]) {
    const cap = cyl(13.5, 14.2, 1.2, MAT.whiteGloss, 48);
    cap.position.y = sy * (W / 2 - 0.2);
    g.add(cap);
    // small offset hole with dark pin
    const hole = cyl(1.15, 1.15, 2.2, MAT.darkGrey, 16);
    hole.position.set(4.6, sy * (W / 2 + 0.2), 0);
    g.add(hole);
  }
  // recessed pockets + centre boss on both faces (3D-printed hub look)
  for (const sy of [-1, 1]) {
    const face = sy * (W / 2 - 0.55);
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
      const pocket = cyl(3.1, 3.1, 1.3, new THREE.MeshStandardMaterial({ color: 0xb9b5a8, roughness: 0.85 }), 20);
      pocket.position.set(Math.cos(a) * 8.6, face, Math.sin(a) * 8.6);
      pocket.rotation.x = Math.PI / 2;
      g.add(pocket);
      const inner = cyl(2.2, 2.2, 0.9, new THREE.MeshStandardMaterial({ color: 0x6e6a60, roughness: 0.9 }), 16);
      inner.position.set(Math.cos(a) * 8.6, face + sy * 0.25, Math.sin(a) * 8.6);
      inner.rotation.x = Math.PI / 2;
      g.add(inner);
    }
    const boss = cyl(4.9, 4.9, 1.6, MAT.whiteGloss, 28);
    boss.position.y = sy * (W / 2 - 0.3);
    g.add(boss);
    const sHead = cyl(2.1, 2.1, 0.9, MAT.silver, 6);
    sHead.position.y = sy * (W / 2 + 0.5);
    sHead.rotation.y = Math.PI / 6;
    g.add(sHead);
  }
  // brass axle bushing
  const bush = cyl(3.1, 3.1, W + 1.6, MAT.brass, 24);
  g.add(bush);
  const axle = cyl(1.45, 1.45, W + 5, MAT.brass, 16);
  g.add(axle);
  return g;
}

/* ------------------------------------------------------------------ */
/*  N20 motor + encoder + white bracket                                */
/* ------------------------------------------------------------------ */
export function motorAssembly(side = 1) {
  const g = new THREE.Group();
  const s = side;
  const ax = D.wheel.x;
  const gm = new THREE.Group();
  // gearbox body (axis along +Y = outboard on the right side)
  const gb = box(10, 20, 12, MAT.silver, { r: 0.7 });
  gb.position.set(ax, s * 37.5, 21);
  gm.add(gb);
  const can = box(10, 12, 12, MAT.silver, { r: 0.5 });
  can.position.set(ax, s * 21.5, 21);
  gm.add(can);
  const enc = box(10.4, 10, 12.4, MAT.white, { r: 0.8 });
  enc.position.set(ax, s * 11.5, 21);
  gm.add(enc);
  const j = jst(4);
  j.rotation.z = s * Math.PI / 2;
  j.position.set(ax, s * 7.0, 21);
  gm.add(j);
  const shaft = cyl(1.5, 1.5, 12, MAT.brass, 16);
  shaft.rotation.x = Math.PI / 2;
  shaft.position.set(ax, s * 53.5, 21);
  gm.add(shaft);
  // white printed bracket: vertical plate inboard of wheel + flange on chassis
  const vert = box(24, 2.6, 22, MAT.white, { r: 0.9 });
  vert.position.set(ax, s * 44.4, 20.5); gm.add(vert);
  const flange = box(24, 16, 2.6, MAT.white, { r: 0.8 });
  flange.position.set(ax, s * 36.5, 32.2); gm.add(flange);
  const brace = box(24, 2.2, 12, MAT.white, { r: 0.8 });
  brace.position.set(ax, s * 44.4, 30.5); gm.add(brace);
  const clamp = box(24, 9, 2.2, MAT.white, { r: 0.8 });
  clamp.position.set(ax, s * 39.5, 10.6); gm.add(clamp);
  for (const sx of [-6, 6]) {
    const sc = screw(1.4, 0.9);
    sc.position.set(ax + sx, s * 34, 33.6); gm.add(sc);
  }
  g.add(gm);
  return g;
}

/* ------------------------------------------------------------------ */
/*  caster (steel ball in 3d-printed holder)                           */
/* ------------------------------------------------------------------ */
export function caster(x, y = 0) {
  const g = new THREE.Group();
  const base = box(16, 16, 8, MAT.white, { r: 1.2 });
  base.position.set(x, y, 7.0); g.add(base);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(5.1, 1.5, 8, 24), MAT.white);
  ring.rotation.x = Math.PI / 2;
  ring.position.set(x, y, 3.6); g.add(ring);
  const ball = new THREE.Mesh(new THREE.SphereGeometry(5.0, 28, 20), new THREE.MeshStandardMaterial({ color: 0xd8dce0, roughness: 0.15, metalness: 1.0 }));
  ball.position.set(x, y, 5.0); ball.castShadow = true; g.add(ball);
  // spring wire loop over the ball
  const w = wire([[x - 6, y, 9.6], [x - 5, y + 6, 9.8], [x, y + 7, 9.9], [x + 5, y + 6, 9.8], [x + 6, y, 9.6]], 0xcfd3d6, 0.4, 0.4, 40);
  g.add(w);
  return g;
}

/* ------------------------------------------------------------------ */
/*  battery pack                                                       */
/* ------------------------------------------------------------------ */
export function battery() {
  const g = new THREE.Group();
  const { l, w, h } = D.battery;
  const bx = 2, bz = 13 + h / 2;
  const body = box(l, w, h, MAT.black, { r: 1.6 });
  body.position.set(bx, 0, bz); g.add(body);
  // labels on both sides + top
  const bt = batteryTexture();
  const lm = new THREE.MeshStandardMaterial({ map: bt, roughness: 0.6 });
  for (const sy of [-1, 1]) {
    const p = plane(l - 6, h - 3, lm);
    orientY(p, sy);
    p.position.set(bx, sy * (w / 2 + 0.02), bz);
    g.add(p);
  }
  const topP = plane(l - 8, w - 8, lm);
  topP.rotation.x = -Math.PI / 2;
  topP.position.set(bx, 0, bz + h / 2 + 0.02);
  g.add(topP);
  // white tape bands wrapping the pack
  for (const px of [-18, 18]) {
    const bw = 15;
    const tTop = box(bw, w + 1.4, 0.5, MAT.tape, { r: 0.2 });
    tTop.position.set(bx + px, 0, bz + h / 2 + 0.15); g.add(tTop);
    const tBot = box(bw, w + 1.4, 0.5, MAT.tape, { r: 0.2 });
    tBot.position.set(bx + px, 0, bz - h / 2 - 0.15); g.add(tBot);
    for (const sy of [-1, 1]) {
      const side = box(bw, 0.5, h + 1.4, MAT.tape, { r: 0.2 });
      side.position.set(bx + px, sy * (w / 2 + 0.15), bz); g.add(side);
    }
  }
  // XH connector + wires
  const plug = jst(2);
  plug.rotation.z = Math.PI / 2;
  plug.position.set(bx + l / 2 - 2, 6, bz + 4);
  g.add(plug);
  const power = ribbon([[bx + l / 2, 6, bz + 6], [bx + l / 2 + 8, 6, bz + 9], [bx + l / 2 + 18, 10, bz + 6], [bx + l / 2 + 26, 6, 34]], { colors: [0xd23b2f, 0x181818], r: 0.7, gap: 1.8, seg: 40 });
  g.add(power);
  return g;
}

/* ------------------------------------------------------------------ */
/*  misc: OLED standoff, cables on top                                 */
/* ------------------------------------------------------------------ */
export function cables() {
  const g = new THREE.Group();
  // thick rainbow ribbon: IDC1 -> tall loop over the car -> front wall header
  const r1 = flatRibbon([[-33, -12, 51.4], [-44, -22, 67.4], [-52, -34, 87.4], [-42, -44, 103.4],
                     [-22, -46, 111.4], [-2, -40, 113.4], [14, -28, 109.4], [26, -18, 97.4],
                     [34, -10, 81.4], [42, -4, 67.4], [49, 0, 59.4]],
                    { width: 8.2, thick: 0.9, twist: 0.4, twistEnd: -1.5 });
  g.add(r1);
  // second rainbow ribbon: IDC2 -> up the +Y side -> wall header
  const r2 = flatRibbon([[-33, 12, 51.4], [-42, 24, 69.4], [-48, 38, 89.4], [-36, 46, 103.4],
                     [-16, 46, 109.4], [4, 40, 111.4], [20, 30, 105.4], [32, 20, 93.4],
                     [40, 10, 77.4], [46, 4, 63.4], [49, 0, 57.4]],
                    { width: 8.0, thick: 0.9, twist: 1.1, twistEnd: -0.9 });
  g.add(r2);
  // sensor wire bundle hanging in front
  const s1 = ribbon([[38, -44, 47.4], [34, -54, 55.4], [24, -60, 65.4], [6, -58, 71.4],
                     [-12, -50, 67.4], [-24, -40, 57.4], [-26, -28, 49.4], [-24, -16, 44.4]],
                    { colors: [0x181818, 0xd23b2f, 0xf4f4f4, 0x8a8f94], gap: 0.9, r: 0.4 });
  g.add(s1);
  // motor leads: PCB edge down to each motor
  for (const sy of [-1, 1]) {
    const m0 = ribbon([[36, sy * 40, 49], [30, sy * 47, 42], [24, sy * 51, 34], [20, sy * 48, 28], [20, sy * 42, 24]],
      { colors: [0xd23b2f, 0x181818, 0xf4f4f4, 0x2aa84a], gap: 0.85, r: 0.4 });
    g.add(m0);
  }
  // battery feed, tucked under the PCB
  const p = ribbon([[30, 6, 13.4], [26, 8, 23.4], [20, 8, 33.4], [2, 8, 37.4], [-26, 8, 37.4], [-34, 8, 37.4]],
                   { colors: [0xd23b2f, 0x181818], gap: 1.6, r: 0.62 });
  g.add(p);
  g.add(cableTie([-40, -40, 99.4], 6, 0.35));
  g.add(cableTie([-34, 44, 97.4], 6, 2.2));
  return g;
}
