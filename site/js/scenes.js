// The 3D scenes. Each factory returns { scene, camera, update(dt, t), labels, controlsTarget?, setState?(key, value), readout?(), pick?(ndc) }.
import * as THREE from 'three';

const COL = {
  accent: 0x6ee7d8, delta: 0xffb454, alpha: 0xb49bff, beta: 0xff7ab6, bad: 0xff5d5d, cz: 0x8f7bff, ink: 0xe9edf5, grey: 0x7b8396, good: 0x63e6a0,
};

function lights(scene) {
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 1.1);
  key.position.set(4, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x8f7bff, 0.6);
  rim.position.set(-5, 2, -4);
  scene.add(rim);
}
function camera(fov = 40) {
  return new THREE.PerspectiveCamera(fov, 1, 0.05, 200);
}
function label(text, cls = '') {
  const node = document.createElement('div');
  node.className = `label3d ${cls}`;
  node.textContent = text;
  return node;
}
const lerp = (a, b, k) => a + (b - a) * k;
function interp(xs, ys, x) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return lerp(ys[i - 1], ys[i], (x - xs[i - 1]) / (xs[i] - xs[i - 1]));
  return ys[ys.length - 1];
}

/** An arrow from the origin along a direction, made of a cylinder and a cone. */
function makeArrow(color, opacity = 1, radius = 0.025) {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, transparent: opacity < 1, opacity, roughness: 0.4 });
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 1, 16), mat);
  const head = new THREE.Mesh(new THREE.ConeGeometry(radius * 3.2, 0.16, 20), mat);
  group.add(shaft, head);
  group.userData = { shaft, head };
  group.setDir = (v) => {
    const len = Math.max(v.length(), 1e-4);
    const dir = v.clone().normalize();
    shaft.scale.y = Math.max(len - 0.14, 0.001);
    shaft.position.copy(dir.clone().multiplyScalar((len - 0.14) / 2));
    head.position.copy(dir.clone().multiplyScalar(len - 0.08));
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    shaft.quaternion.copy(q);
    head.quaternion.copy(q);
  };
  return group;
}

/** A Bloch sphere: translucent ball, equator, meridians, axes. Bloch z is three's y. */
function makeBloch(radius = 1) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 32), new THREE.MeshPhysicalMaterial({ color: 0x1b2540, transparent: true, opacity: 0.22, roughness: 0.2, metalness: 0.1, side: THREE.DoubleSide, depthWrite: false })));
  const ringMat = new THREE.LineBasicMaterial({ color: 0x9fb1d8, transparent: true, opacity: 0.35 });
  const circle = (rot) => {
    const pts = [];
    for (let i = 0; i <= 96; i++) { const a = (i / 96) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * radius, 0, Math.sin(a) * radius)); }
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), ringMat);
    line.rotation.set(...rot);
    return line;
  };
  g.add(circle([0, 0, 0]), circle([Math.PI / 2, 0, 0]), circle([Math.PI / 2, 0, Math.PI / 2]));
  const axMat = new THREE.LineBasicMaterial({ color: 0x9fb1d8, transparent: true, opacity: 0.25 });
  for (const v of [[1, 0, 0], [0, 1, 0], [0, 0, 1]]) {
    const a = new THREE.Vector3(...v).multiplyScalar(radius * 1.25);
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a.clone().negate(), a]), axMat));
  }
  return g;
}
/** Bloch vector on the equator at azimuth phi (radius r). */
const equator = (phi, r = 1) => new THREE.Vector3(Math.cos(phi) * r, 0, -Math.sin(phi) * r);

function arcLine(color, opacity = 1) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * 200), 3));
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
  line.setArc = (a0, a1, r = 1, y = 0) => {
    const pos = geo.attributes.position.array;
    const n = 200;
    for (let i = 0; i < n; i++) {
      const a = lerp(a0, a1, i / (n - 1));
      pos[i * 3] = Math.cos(a) * r; pos[i * 3 + 1] = y; pos[i * 3 + 2] = -Math.sin(a) * r;
    }
    geo.attributes.position.needsUpdate = true;
    geo.computeBoundingSphere();
  };
  return line;
}

/* ------------------------------------------------------------------ chip */
export function chipScene(variant) {
  const scene = new THREE.Scene();
  const cam = camera(38);
  cam.position.set(0, 9.5, 12.5);
  lights(scene);
  const chip = new THREE.Group();
  scene.add(chip);
  const slab = new THREE.Mesh(new THREE.BoxGeometry(11, 0.35, 8.6), new THREE.MeshStandardMaterial({ color: 0x0e1424, roughness: 0.6, metalness: 0.4 }));
  slab.position.y = -0.3;
  chip.add(slab);
  const edgeGlow = new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry), new THREE.LineBasicMaterial({ color: COL.accent, transparent: true, opacity: 0.35 }));
  edgeGlow.position.copy(slab.position);
  chip.add(edgeGlow);

  // Heavy-hex patch (illustration): hexagon corners plus a qubit on every hexagon edge.
  const s = 1.0, nodes = new Map(), edges = [];
  const key = (v) => `${v.x.toFixed(2)},${v.z.toFixed(2)}`;
  const add = (v) => { const k = key(v); if (!nodes.has(k)) nodes.set(k, v); return k; };
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 4; c++) {
      const cx = (c - 1.5) * s * Math.sqrt(3) * 1.0 + (r % 2 ? (s * Math.sqrt(3)) / 2 : 0) - 0.4;
      const cz = (r - 1) * s * 1.5;
      const corners = [];
      for (let k = 0; k < 6; k++) { const a = Math.PI / 6 + (k * Math.PI) / 3; corners.push(new THREE.Vector3(cx + s * Math.cos(a), 0, cz + s * Math.sin(a))); }
      for (let k = 0; k < 6; k++) {
        const a = corners[k], b = corners[(k + 1) % 6];
        const m = a.clone().add(b).multiplyScalar(0.5);
        const ka = add(a), kb = add(b), km = add(m);
        edges.push([ka, km], [km, kb]);
      }
    }
  }
  const uniq = new Map(edges.map(([a, b]) => [[a, b].sort().join('|'), [a, b]]));
  const qMat = new THREE.MeshStandardMaterial({ color: 0x2a3550, emissive: COL.accent, emissiveIntensity: 0.25, metalness: 0.3, roughness: 0.35 });
  const qGeo = new THREE.SphereGeometry(0.13, 20, 16);
  const qubits = new Map();
  for (const [k, v] of nodes) { const m = new THREE.Mesh(qGeo, qMat.clone()); m.position.copy(v).setY(0.05); chip.add(m); qubits.set(k, m); }
  const cMat = new THREE.MeshStandardMaterial({ color: 0x3b4a6b, emissive: 0x3b4a6b, emissiveIntensity: 0.4 });
  const couplers = [];
  for (const [a, b] of uniq.values()) {
    const pa = nodes.get(a), pb = nodes.get(b);
    const len = pa.distanceTo(pb);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, len, 8), cMat.clone());
    m.position.copy(pa.clone().add(pb).multiplyScalar(0.5)).setY(0.05);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pb.clone().sub(pa).normalize());
    chip.add(m);
    couplers.push({ m, a, b });
  }
  // Highlight a few couplers as measured pairs; one "bad" pair in red.
  const picks = [3, 17, 29, 41, 52, 66, 78, 90].filter((i) => i < couplers.length);
  picks.forEach((i, j) => {
    const c = couplers[i];
    const color = j === 1 ? COL.bad : COL.accent;
    c.m.material.color.setHex(color); c.m.material.emissive.setHex(color); c.m.material.emissiveIntensity = 0.9;
    c.m.scale.set(1.8, 1, 1.8);
    qubits.get(c.a).material.emissive.setHex(color); qubits.get(c.b).material.emissive.setHex(color);
    c.pulse = j;
  });
  const bad = couplers[picks[1]];
  const labels = [{ el: label('a pair whose error changes with θ'), pos: bad.m.position.clone().add(new THREE.Vector3(0, 0.6, 0)), obj: chip }];
  if (variant !== 'end') labels.push({ el: label('heavy-hex lattice (illustration)', 'dim'), pos: new THREE.Vector3(0, -0.6, 4.6), obj: chip });

  return {
    scene, camera: cam, labels, controlsTarget: new THREE.Vector3(0, 0, 0),
    update(dt, t) {
      chip.rotation.y += dt * 0.08;
      couplers.forEach((c) => { if (c.pulse !== undefined) c.m.material.emissiveIntensity = 0.6 + 0.5 * Math.sin(t * 2.4 + c.pulse); });
      for (const q of qubits.values()) q.position.y = 0.05 + 0.02 * Math.sin(t * 1.5 + q.position.x);
    },
  };
}

/* ------------------------------------------------------------------ bloch */
export function blochScene(D) {
  const scene = new THREE.Scene();
  const cam = camera(36);
  cam.position.set(-0.2, 4.4, 7.4);
  lights(scene);
  const cal = D.rounds.E4.cal;
  const gates = {
    ideal: { th: [0, 2], eff: [0, 2], beta: [0, 0] },
    typical: cal['(14, 15)'],
    bad: cal['(10, 11)'],
  };
  const state = { theta: 0.393, n: 1, ctrl: 0, gate: 'bad' };

  const target = makeBloch(1.25);
  target.position.set(0.8, 0, 0);
  scene.add(target);
  const control = makeBloch(0.6);
  control.position.set(-1.8, 0, 0);
  scene.add(control);
  const ctrlArrow = makeArrow(COL.ink, 0.9, 0.02);
  control.add(ctrlArrow);
  const link = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.4, 12), new THREE.MeshStandardMaterial({ color: COL.cz, emissive: COL.cz, emissiveIntensity: 0.6 }));
  link.rotation.z = Math.PI / 2; link.position.set(-0.65, 0, 0);
  scene.add(link);

  const ideal = makeArrow(0xffffff, 0.45, 0.022);
  const actual = makeArrow(COL.delta, 1, 0.03);
  target.add(ideal, actual);
  const idealArc = arcLine(0xffffff, 0.45), actualArc = arcLine(COL.delta, 0.9), errArc = arcLine(COL.bad, 1);
  target.add(idealArc, actualArc, errArc);
  errArc.scale.setScalar(1.06);
  let shownIdeal = 0, shownActual = 0;

  const labels = [
    { el: label('|0⟩', 'dim'), pos: new THREE.Vector3(0, 1.45, 0), obj: target },
    { el: label('|1⟩', 'dim'), pos: new THREE.Vector3(0, -1.45, 0), obj: target },
    { el: label('|+⟩', 'dim'), pos: new THREE.Vector3(1.5, 0, 0), obj: target },
    { el: label('control'), pos: new THREE.Vector3(0, -0.95, 0), obj: control },
    { el: label('target'), pos: new THREE.Vector3(0, -1.65, 0), obj: target },
    { el: label('RZZ(θ)'), pos: new THREE.Vector3(-0.65, 0.25, 0), obj: scene },
  ];

  const params = () => {
    const g = gates[state.gate];
    const delta = interp(g.th, g.eff, state.theta) - state.theta;
    const beta = interp(g.th, g.beta, state.theta);
    const sgn = state.ctrl === 0 ? 1 : -1;
    const phiIdeal = state.n * sgn * state.theta;
    const phiActual = state.n * (sgn * (state.theta + delta) + beta);
    return { delta, beta, sgn, phiIdeal, phiActual };
  };

  return {
    scene, camera: cam, labels, controlsTarget: new THREE.Vector3(-0.4, 0, 0),
    setState(k, v) { state[k] = k === 'gate' ? v : Number(v); },
    readout() {
      const p = params();
      const err = p.phiActual - p.phiIdeal;
      return [
        ['requested', `${state.theta.toFixed(3)} rad`],
        ['δ(θ)', `${p.delta >= 0 ? '+' : ''}${p.delta.toFixed(3)}`],
        ['β(θ)', `${p.beta >= 0 ? '+' : ''}${p.beta.toFixed(3)}`],
        [`phase error × ${state.n}`, `${err >= 0 ? '+' : ''}${err.toFixed(3)} rad`],
        ['overlap with ideal', `${(Math.cos(err / 2) ** 2 * 100).toFixed(1)}%`],
      ];
    },
    update(dt) {
      const p = params();
      const k = 1 - Math.exp(-dt * 6);
      shownIdeal = lerp(shownIdeal, p.phiIdeal, k);
      shownActual = lerp(shownActual, p.phiActual, k);
      ideal.setDir(equator(shownIdeal, 1.25));
      actual.setDir(equator(shownActual, 1.25));
      idealArc.setArc(0, shownIdeal, 0.55);
      actualArc.setArc(0, shownActual, 0.75);
      errArc.setArc(shownIdeal, shownActual, 1.25);
      ctrlArrow.setDir(new THREE.Vector3(0, state.ctrl === 0 ? 0.6 : -0.6, 0));
    },
  };
}

/* ------------------------------------------------------------------ mirror */
export function mirrorScene() {
  const scene = new THREE.Scene();
  const cam = camera(36);
  cam.position.set(2.6, 3.8, 5.6);
  lights(scene);
  const R = 1.4;
  const ball = makeBloch(R);
  scene.add(ball);
  const vec = makeArrow(COL.accent, 1, 0.035);
  const ghost = makeArrow(0xffffff, 0.35, 0.02);
  ball.add(vec, ghost);
  const MAXP = 2000;
  const trailGeo = new THREE.BufferGeometry();
  trailGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXP * 3), 3));
  trailGeo.setDrawRange(0, 0);
  const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ color: COL.delta, transparent: true, opacity: 0.85 }));
  ball.add(trail);
  const home = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 12), new THREE.MeshBasicMaterial({ color: COL.good }));
  home.position.copy(equator(0, R));
  ball.add(home);
  const state = { d: 8, eps: 0.012, delta: 1, theta: 0.42 };
  let t0 = 0, count = 0, lastStep = -1;
  const labels = [
    { el: label('start / home'), pos: equator(0, R + 0.35), obj: ball },
    { el: label('|0⟩', 'dim'), pos: new THREE.Vector3(0, R + 0.2, 0), obj: ball },
    { el: label('', ''), pos: new THREE.Vector3(0, -R - 0.35, 0), obj: ball, id: 'phase' },
  ];
  const p = () => 1 - (16 / 15) * state.eps;
  const reset = () => { t0 = performance.now() / 1000; count = 0; lastStep = -1; trailGeo.setDrawRange(0, 0); };
  reset();
  const push = (v) => {
    if (count >= MAXP) return;
    trailGeo.attributes.position.setXYZ(count++, v.x, v.y, v.z);
    trailGeo.setDrawRange(0, count);
    trailGeo.attributes.position.needsUpdate = true;
  };

  return {
    scene, camera: cam, labels, controlsTarget: new THREE.Vector3(0, 0, 0),
    setState(k, v) { state[k] = Number(v); reset(); },
    readout() {
      const S = Math.pow(p(), 2 * state.d);
      return [
        ['layers', `${state.d} out + ${state.d} back`],
        ['p per layer', p().toFixed(4)],
        ['survival p^(2d)', `${(S * 100).toFixed(1)}%`],
        ['angle error at home', '0 rad'],
      ];
    },
    update() {
      const steps = 2 * state.d;
      const stepDur = Math.min(0.35, 7 / steps);
      const now = performance.now() / 1000 - t0;
      const total = steps * stepDur;
      if (now > total + 1.6) { reset(); return; }
      const f = Math.min(now / stepDur, steps);
      const i = Math.floor(f), frac = f - i;
      const dTheta = state.theta + (state.delta ? 0.15 : 0);
      // Angle after f steps: out for the first d, back for the rest.
      const angleAt = (x, ang) => (x <= state.d ? x * ang : (2 * state.d - x) * ang);
      const phi = angleAt(Math.min(f, steps), dTheta);
      const phiIdeal = angleAt(Math.min(f, steps), state.theta);
      const r = R * Math.pow(p(), f);
      const v = equator(phi, r);
      vec.setDir(v);
      ghost.setDir(equator(phiIdeal, R));
      if (f < steps || i !== lastStep) { push(v); lastStep = i; }
      const phase = labels.find((l) => l.id === 'phase');
      phase.el.textContent = f < state.d ? `forward: layer ${Math.min(i + 1, state.d)} of ${state.d}` : f < steps ? `mirror: layer ${Math.min(i - state.d + 1, state.d)} of ${state.d}` : `home · length ${(Math.pow(p(), steps) * 100).toFixed(0)}%`;
      void frac;
    },
  };
}

/* ------------------------------------------------------------------ landscape */
export function landscapeScene(D, tipEl) {
  const scene = new THREE.Scene();
  const cam = camera(38);
  cam.position.set(12, 12.5, 17.5);
  lights(scene);
  const root = new THREE.Group();
  scene.add(root);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(16, 13), new THREE.MeshStandardMaterial({ color: 0x0c1220, roughness: 0.9 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -0.01;
  root.add(floor);
  root.add(new THREE.GridHelper(16, 16, 0x24304a, 0x161e30));
  const H = (e) => (Math.log10(Math.max(e, 1e-4)) + 4) * 1.7;
  const bars = [], labels = [];
  let hovered = null;
  const lowC = new THREE.Color(COL.accent), highC = new THREE.Color(COL.bad), midC = new THREE.Color(0xf5f1d0);
  const build = (key) => {
    while (root.children.length > 2) root.remove(root.children[2]);
    bars.length = 0;
    labels.splice(0).forEach((l) => l.el.remove());
    const sw = D.sweeps[key];
    const pairs = Object.entries(sw.pairs);
    pairs.forEach(([name, p], r) => {
      const z = (r - (pairs.length - 1) / 2) * 1.35;
      p.theta.forEach((t, c) => {
        const x = (c - 5.5) * 1.05;
        const e = p.eps[c];
        const h = Math.max(H(e), 0.04);
        const ratio = Math.log10(Math.max(e, 1e-5) / p.reported);
        const col = ratio < 0 ? lowC.clone().lerp(midC, Math.max(0, 1 + ratio * 2.5)) : midC.clone().lerp(highC, Math.min(1, ratio * 2));
        const m = new THREE.Mesh(new THREE.BoxGeometry(0.7, h, 0.7), new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.18, roughness: 0.45, transparent: e <= 0, opacity: e <= 0 ? 0.35 : 1 }));
        m.position.set(x, h / 2, z);
        m.userData = { name, t, e, lo: p.lo[c], hi: p.hi[c], rep: p.reported, holm: p.holm, backend: sw.backend };
        root.add(m);
        bars.push(m);
      });
      const rep = new THREE.Mesh(new THREE.BoxGeometry(12.6, 0.035, 0.05), new THREE.MeshBasicMaterial({ color: COL.bad }));
      rep.position.set(0, H(p.reported), z + 0.38);
      root.add(rep);
      const verdict = p.holm < 0.01 ? 'θ-dependent' : 'constant not rejected';
      labels.push({ el: label(`${name} · ${verdict}`, p.holm < 0.01 ? '' : 'dim'), pos: new THREE.Vector3(7.6, 0.2, z), obj: root });
    });
    [0, 3, 6, 9, 11].forEach((c) => labels.push({ el: label(['π/24', 'π/6', '7π/24', '5π/12', 'π/2'][[0, 3, 6, 9, 11].indexOf(c)], 'dim'), pos: new THREE.Vector3((c - 5.5) * 1.05, 0, 6.4), obj: root }));
    labels.push({ el: label('θ →'), pos: new THREE.Vector3(6.8, 0, 6.4), obj: root });
    labels.push({ el: label('bar height: ε on a log scale', 'dim'), pos: new THREE.Vector3(-7.4, 3.9, -6), obj: root });
    api.onLabels?.();
  };
  const ray = new THREE.Raycaster();
  const api = {
    scene, camera: cam, labels, controlsTarget: new THREE.Vector3(0, 1, 0),
    setState(k, v) { if (k === 'sweep') { build(v); hovered = null; } },
    pick(ndc) {
      ray.setFromCamera(ndc, cam);
      const hit = ray.intersectObjects(bars)[0]?.object;
      if (hovered && hovered !== hit) hovered.material.emissiveIntensity = 0.18;
      hovered = hit || null;
      if (hit) {
        hit.material.emissiveIntensity = 0.8;
        const u = hit.userData;
        const k = Math.round((u.t / Math.PI) * 24);
        tipEl.textContent = `${u.backend} ${u.name}\nθ = ${k}π/24 (${u.t.toFixed(3)} rad)\nε = ${u.e.toExponential(2)}  [${Math.max(u.lo, 0).toExponential(1)}, ${u.hi.toExponential(1)}]\nIBM-reported ${u.rep.toExponential(2)} · Holm p ${u.holm.toExponential(1)}`;
      }
    },
    update() {},
  };
  build('E2');
  return api;
}

/* ------------------------------------------------------------------ compiler */
export function compilerScene(R) {
  const scene = new THREE.Scene();
  const cam = camera(38);
  cam.position.set(8, 9.5, 12.5);
  lights(scene);
  const NQ = 8, LAYERS = 6, dx = 1.25, dz = 1.2;
  const BAD = new Set([1, 4]);
  const pairNames = ['(12, 13)', '(10, 11)', '(14, 15)', '(32, 33)', '(0, 1)', '(59, 75)', '(108, 109)'];
  const root = new THREE.Group();
  root.position.set(-((NQ - 1) * dx) / 2, 0, -((LAYERS - 1) * dz) / 2);
  scene.add(root);
  const wireMat = new THREE.MeshStandardMaterial({ color: 0x33415f, emissive: 0x33415f, emissiveIntensity: 0.3 });
  const qMat = new THREE.MeshStandardMaterial({ color: 0x223050, emissive: COL.accent, emissiveIntensity: 0.4, roughness: 0.3 });
  for (let q = 0; q < NQ; q++) {
    const wire = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, LAYERS * dz + 0.6, 8), wireMat);
    wire.rotation.x = Math.PI / 2; wire.position.set(q * dx, 0, ((LAYERS - 1) * dz) / 2);
    root.add(wire);
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.17, 20, 16), qMat);
    ball.position.set(q * dx, 0, -0.7);
    root.add(ball);
  }
  const gates = [];
  const fracMat = (bad) => new THREE.MeshStandardMaterial({ color: bad ? COL.bad : COL.accent, emissive: bad ? COL.bad : COL.accent, emissiveIntensity: 0.35, roughness: 0.35, transparent: true });
  const czMat = new THREE.MeshStandardMaterial({ color: COL.cz, emissive: COL.cz, emissiveIntensity: 0.4, transparent: true });
  const fixMat = new THREE.MeshStandardMaterial({ color: COL.beta, emissive: COL.beta, emissiveIntensity: 0.5, transparent: true });
  for (let l = 0; l < LAYERS; l++) {
    for (let e = l % 2; e < NQ - 1; e += 2) {
      const bad = BAD.has(e);
      const g = new THREE.Group();
      g.position.set(e * dx + dx / 2, 0, l * dz);
      const frac = new THREE.Mesh(new THREE.BoxGeometry(dx * 0.95, 0.32, 0.42), fracMat(bad));
      const cz1 = new THREE.Mesh(new THREE.BoxGeometry(dx * 0.95, 0.24, 0.16), czMat);
      const cz2 = cz1.clone(); cz1.position.z = -0.14; cz2.position.z = 0.14;
      const fixes = [-dx / 2, dx / 2].map((x) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.05, 20), fixMat); m.position.set(x, 0.0, 0.34); m.rotation.x = Math.PI / 2; return m; });
      g.add(frac, cz1, cz2, ...fixes);
      root.add(g);
      gates.push({ g, frac, cz: [cz1, cz2], fixes, bad, phase: Math.random() * 6 });
    }
  }
  const labels = pairNames.map((n, e) => ({ el: label(n, BAD.has(e) ? '' : 'dim'), pos: new THREE.Vector3(e * dx + dx / 2, 0.55, -0.7), obj: root }));
  labels.push({ el: label('circuit depth ↓', 'dim'), pos: new THREE.Vector3((NQ - 1) * dx + 0.9, 0.4, (LAYERS - 1) * dz), obj: root });
  const state = { mode: 'before', family: 'lr_qaoa' };
  let mix = 0;
  return {
    scene, camera: cam, labels, controlsTarget: new THREE.Vector3(0, 0, 0),
    setState(k, v) { state[k] = v; },
    readout() {
      const p = R.h2_projection.base[state.family];
      const after = state.mode === 'after';
      return [
        ['median success', after ? p.median_theta.toFixed(3) : p.median_raw.toFixed(3)],
        ['gain vs before', after ? `+${(p.median_rel_gain * 100).toFixed(1)}%` : '—'],
        ['95% CI', after ? `${(p.ci[0] * 100).toFixed(1)}–${(p.ci[1] * 100).toFixed(1)}%` : '—'],
        ['gates sent to 2-CZ', after ? `${(p.share_cz * 100).toFixed(0)}%` : '0%'],
        ['gain, no bad pair', after ? `+${(p.gain_no_bad * 100).toFixed(1)}%` : '—'],
      ];
    },
    update(dt, t) {
      mix = lerp(mix, state.mode === 'after' ? 1 : 0, 1 - Math.exp(-dt * 5));
      for (const g of gates) {
        const showCz = g.bad ? mix : 0;
        g.frac.scale.setScalar(Math.max(1 - showCz, 0.001));
        g.frac.material.opacity = 1 - showCz;
        g.cz.forEach((c) => { c.scale.setScalar(Math.max(showCz, 0.001)); c.material.opacity = showCz; });
        const fix = g.bad ? 0 : mix;
        g.fixes.forEach((f) => f.scale.setScalar(Math.max(fix, 0.001)));
        // Coherent error: a wobble on uncorrected gates, strong on bad pairs.
        const wob = (1 - mix) * (g.bad ? 0.22 : 0.05);
        g.frac.rotation.y = Math.sin(t * 2 + g.phase) * wob;
        g.frac.position.y = g.bad ? Math.sin(t * 3 + g.phase) * 0.05 * (1 - mix) : 0;
      }
    },
  };
}
