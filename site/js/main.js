import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { drawChart } from './charts.js';
import { blochScene, chipScene, compilerScene, landscapeScene, mirrorScene } from './scenes.js';

const slides = [...document.querySelectorAll('.slide')];
const dotsEl = document.getElementById('dots');
const counter = document.getElementById('counter');
const bar = document.getElementById('progress-bar');
const notesPanel = document.getElementById('notes-panel');
const mobile = () => window.matchMedia('(max-width: 900px)').matches;

const [D, R, K] = await Promise.all(['data/site_data.json', 'data/paper_results.json', 'data/compiler_summary.json'].map((u) => fetch(u).then((r) => r.json())));
R.compiler = K;

// Charts: drawn once, they are SVG and scale by themselves.
for (const s of slides) if (s.dataset.chart) drawChart(s.dataset.chart, s.querySelector('.stage'), D, R);

// One WebGL renderer, moved into whichever slide is shown.
let renderer = null;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
} catch (error) {
  console.warn('WebGL unavailable', error);
}
const factories = {
  chip: (s) => chipScene(s.dataset.variant),
  bloch: () => blochScene(D),
  mirror: () => mirrorScene(),
  landscape: () => landscapeScene(D, document.getElementById('landscape-tip')),
  compiler: () => compilerScene(R),
};
const built = new Map();
let active = null; // { slide, api, controls, stage }

function sceneFor(slide) {
  if (built.has(slide)) return built.get(slide);
  const api = factories[slide.dataset.scene](slide);
  const entry = { slide, api, stage: slide.querySelector('.stage') };
  for (const l of api.labels) entry.stage.appendChild(l.el);
  api.onLabels = () => { for (const l of api.labels) if (!l.el.parentNode) entry.stage.appendChild(l.el); };
  bindControls(slide, api);
  built.set(slide, entry);
  return entry;
}

function bindControls(slide, api) {
  const box = slide.querySelector('.controls');
  const readout = slide.querySelector('.readout');
  const refresh = () => {
    if (!readout || !api.readout) return;
    readout.replaceChildren(...api.readout().map(([k, v]) => {
      const d = document.createElement('div');
      const dt = document.createElement('dt'); dt.textContent = k;
      const dd = document.createElement('dd'); dd.textContent = v;
      d.append(dt, dd);
      return d;
    }));
  };
  if (box) {
    box.querySelectorAll('input[type=range]').forEach((input) => {
      const out = box.querySelector(`output[name="${input.name}-out"]`);
      const fmt = () => {
        const v = Number(input.value);
        if (out) out.textContent = input.name === 'theta' ? `${(v / Math.PI).toFixed(3)}π` : input.step < 1 ? v.toFixed(3) : String(v);
      };
      input.addEventListener('input', () => { api.setState?.(input.name, input.value); fmt(); refresh(); });
      api.setState?.(input.name, input.value);
      fmt();
    });
    box.querySelectorAll('.seg button').forEach((b) => {
      b.addEventListener('click', () => {
        b.parentElement.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
        api.setState?.(b.dataset.k, b.dataset.v);
        refresh();
      });
      if (b.classList.contains('on')) api.setState?.(b.dataset.k, b.dataset.v);
    });
  }
  refresh();
}

function attach(slide) {
  if (active?.slide === slide) return;
  if (active) { active.controls?.dispose(); active = null; }
  if (!renderer || !slide.dataset.scene) return;
  const entry = sceneFor(slide);
  entry.stage.prepend(renderer.domElement);
  const controls = new OrbitControls(entry.api.camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = 2.5;
  controls.maxDistance = 30;
  controls.target.copy(entry.api.controlsTarget ?? new THREE.Vector3());
  entry.controls = controls;
  active = entry;
  resize();
}

function resize() {
  if (!active || !renderer) return;
  const r = active.stage.getBoundingClientRect();
  const w = Math.max(r.width, 10), h = Math.max(r.height, 10);
  renderer.setSize(w, h, false);
  active.api.camera.aspect = w / h;
  active.api.camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);

// Hover / tap picking (landscape).
const ndc = new THREE.Vector2();
renderer?.domElement.addEventListener('pointermove', (e) => {
  if (!active?.api.pick) return;
  const r = renderer.domElement.getBoundingClientRect();
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  active.api.pick(ndc);
});

// Labels follow their 3D points.
const v = new THREE.Vector3();
function placeLabels() {
  const { api, stage } = active;
  const w = stage.clientWidth, h = stage.clientHeight;
  for (const l of api.labels) {
    v.copy(l.pos);
    if (l.obj) l.obj.localToWorld(v);
    v.project(api.camera);
    const hidden = v.z > 1;
    l.el.style.display = hidden ? 'none' : '';
    l.el.style.left = `${((v.x + 1) / 2) * w}px`;
    l.el.style.top = `${((1 - v.y) / 2) * h}px`;
  }
}

const clock = new THREE.Clock();
function loop() {
  requestAnimationFrame(loop);
  if (!active || document.hidden) return;
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  active.controls.update();
  active.api.update(dt, t);
  renderer.render(active.api.scene, active.api.camera);
  placeLabels();
  if (active.api.readout && t % 0.25 < dt) refreshReadout(active.slide, active.api);
}
function refreshReadout(slide, api) {
  const readout = slide.querySelector('.readout');
  if (!readout || slide.dataset.scene !== 'mirror') return;
  const vals = api.readout();
  readout.querySelectorAll('dd').forEach((dd, i) => { if (vals[i]) dd.textContent = vals[i][1]; });
}
loop();

// Deck navigation.
let index = 0;
slides.forEach((s, i) => {
  const b = document.createElement('button');
  b.setAttribute('aria-label', `Slide ${i + 1}`);
  b.addEventListener('click', () => go(i));
  dotsEl.appendChild(b);
});
function go(i) {
  index = Math.max(0, Math.min(slides.length - 1, i));
  slides.forEach((s, k) => s.classList.toggle('active', k === index));
  [...dotsEl.children].forEach((b, k) => b.classList.toggle('on', k === index));
  counter.textContent = `${index + 1} / ${slides.length}`;
  bar.style.width = `${((index + 1) / slides.length) * 100}%`;
  if (!notesPanel.hidden) notesPanel.textContent = slides[index].querySelector('.notes')?.textContent ?? '';
  history.replaceState(null, '', `#${index + 1}`);
  if (!mobile()) attach(slides[index]);
}
const fromHash = () => Math.max(0, (parseInt(location.hash.slice(1), 10) || 1) - 1);

window.addEventListener('keydown', (e) => {
  if (e.target.closest('input, button') && !['ArrowRight', 'ArrowLeft', 'PageDown', 'PageUp'].includes(e.key)) return;
  if (e.target.matches('input[type=range]') && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) return;
  if (mobile()) return;
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); go(index + 1); }
  else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); go(index - 1); }
  else if (e.key === 'Home') go(0);
  else if (e.key === 'End') go(slides.length - 1);
  else if (e.key === 'f' || e.key === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }
  else if (e.key === 'n' || e.key === 'N') { notesPanel.hidden = !notesPanel.hidden; go(index); }
});

// Swipe between slides, outside the 3D stage and the controls.
let touchX = null;
window.addEventListener('touchstart', (e) => { touchX = e.target.closest('.stage, .controls') ? null : e.touches[0].clientX; }, { passive: true });
window.addEventListener('touchend', (e) => {
  if (touchX == null || mobile()) return;
  const dx = e.changedTouches[0].clientX - touchX;
  if (Math.abs(dx) > 60) go(index + (dx < 0 ? 1 : -1));
  touchX = null;
});

// Narrow screens: slides stack and scroll; the scene follows the slide in view.
const io = new IntersectionObserver((entries) => {
  if (!mobile()) return;
  const best = entries.filter((e) => e.isIntersecting && e.target.dataset.scene).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
  if (best) attach(best.target);
}, { threshold: [0.35, 0.6] });
slides.forEach((s) => io.observe(s));

go(fromHash());
