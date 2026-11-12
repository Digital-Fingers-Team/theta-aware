// 2D charts drawn as SVG from the measured data (data/*.json). No libraries.
const NS = 'http://www.w3.org/2000/svg';
const C = {
  eps: '#6ee7d8', delta: '#ffb454', alpha: '#b49bff', beta: '#ff7ab6', bad: '#ff5d5d', cz: '#8f7bff',
  grey: '#7b8396', ink: '#e9edf5', good: '#63e6a0', proj: '#ffb454',
};

function el(tag, attrs = {}, parent) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}
function text(parent, x, y, str, cls, extra = {}) {
  const { fill, ...rest } = extra;
  const t = el('text', { x, y, class: cls, ...rest }, parent);
  if (fill) t.style.fill = fill;
  t.textContent = str;
  return t;
}
const piLabel = (t) => {
  const k = Math.round((t / Math.PI) * 24);
  const g = (a, b) => (b ? g(b, a % b) : a);
  const d = g(k, 24);
  const num = k / d, den = 24 / d;
  return den === 1 ? `${num === 1 ? '' : num}π` : `${num === 1 ? '' : num}π/${den}`;
};

/** A plot frame with linear x and linear or log y. */
function frame(svg, box, { x: [x0, x1], y: [y0, y1], log = false, xticks, yticks, xlabel, ylabel, title, xfmt = (v) => v, yfmt = (v) => v }) {
  const { left, top, width, height } = box;
  const ly = (v) => (log ? Math.log10(v) : v);
  const sx = (v) => left + ((v - x0) / (x1 - x0)) * width;
  const sy = (v) => top + height - ((ly(Math.max(v, log ? y0 : -Infinity)) - ly(y0)) / (ly(y1) - ly(y0))) * height;
  const g = el('g', {}, svg);
  for (const t of yticks) {
    if (log && t <= 0) continue;
    el('line', { x1: left, x2: left + width, y1: sy(t), y2: sy(t), class: 'grid' }, g);
    text(g, left - 8, sy(t) + 4, yfmt(t), 'tick', { 'text-anchor': 'end' });
  }
  for (const t of xticks) text(g, sx(t), top + height + 18, xfmt(t), 'tick', { 'text-anchor': 'middle' });
  el('line', { x1: left, x2: left + width, y1: top + height, y2: top + height, class: 'ax' }, g);
  el('line', { x1: left, x2: left, y1: top, y2: top + height, class: 'ax' }, g);
  if (xlabel) text(g, left + width / 2, top + height + 38, xlabel, 'axlabel', { 'text-anchor': 'middle' });
  if (ylabel) text(g, left - 50, top + height / 2, ylabel, 'axlabel', { 'text-anchor': 'middle', transform: `rotate(-90 ${left - 50} ${top + height / 2})` });
  if (title) text(g, left, top - 12, title, 'ctitle');
  return { sx, sy, g };
}
const path = (pts) => pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('');
const THETA_TICKS = [Math.PI / 24 * 3, Math.PI / 24 * 6, Math.PI / 24 * 9, Math.PI / 24 * 12];

function newSvg(stage, w = 680, h = 440) {
  stage.innerHTML = '';
  return el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img' }, stage);
}

/** ε(θ) of two pairs against IBM's reported value. */
function problem(stage, D) {
  const svg = newSvg(stage);
  const series = [
    { p: D.sweeps.E2.pairs['(10, 11)'], color: C.bad, name: 'marrakesh (10, 11)' },
    { p: D.sweeps.E7.pairs['(16, 23)'], color: C.eps, name: 'kingston (16, 23)' },
  ];
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 310 }, {
    x: [0.1, 1.6], y: [1e-4, 2e-2], log: true, xticks: THETA_TICKS, yticks: [1e-4, 1e-3, 1e-2],
    xfmt: piLabel, yfmt: (v) => String(v),
    xlabel: 'requested angle θ (rad)', ylabel: 'incoherent error ε(θ)', title: 'Measured ε(θ) vs the one reported number',
  });
  series.forEach(({ p, color, name }, k) => {
    const ry = f.sy(p.reported);
    el('line', { x1: f.sx(0.1), x2: f.sx(1.6), y1: ry, y2: ry, stroke: color, 'stroke-dasharray': '6 5', 'stroke-width': 1.5, opacity: 0.8 }, f.g);
    const pts = p.theta.map((t, i) => [f.sx(t), f.sy(Math.max(p.eps[i], 1e-4))]);
    p.theta.forEach((t, i) => {
      el('line', { x1: f.sx(t), x2: f.sx(t), y1: f.sy(Math.max(p.lo[i], 1e-4)), y2: f.sy(Math.max(p.hi[i], 1e-4)), stroke: color, 'stroke-width': 1, opacity: 0.5 }, f.g);
    });
    el('path', { d: path(pts), fill: 'none', stroke: color, 'stroke-width': 2 }, f.g);
    pts.forEach(([x, y]) => el('circle', { cx: x, cy: y, r: 3.6, fill: color }, f.g));
    text(f.g, 470, 76 + k * 20, `● ${name}`, 'tick', { fill: color });
  });
  text(f.g, 470, 116, '- - IBM-reported, one value', 'tick');
  text(svg, 84, 425, 'E2 / E7 mirror sweeps, 14 Oct 2026. Bars: 95% bootstrap intervals.', 'cnote');
}

/** Delivered angle vs requested angle on (10, 11) and a typical pair. */
function model(stage, D) {
  const svg = newSvg(stage);
  const cal = D.rounds.E4.cal;
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 310 }, {
    x: [0, 1.65], y: [0, 1.65], xticks: THETA_TICKS, yticks: [0, 0.4, 0.8, 1.2, 1.6], xfmt: piLabel, yfmt: (v) => v.toFixed(1),
    xlabel: 'requested angle θ (rad)', ylabel: 'delivered angle θ + δ (rad)', title: 'What the gate actually does',
  });
  el('path', { d: path([[f.sx(0), f.sy(0)], [f.sx(1.65), f.sy(1.65)]]), stroke: '#ffffff', 'stroke-opacity': 0.4, 'stroke-dasharray': '4 4', fill: 'none' }, f.g);
  text(f.g, f.sx(1.25), f.sy(1.36), 'ideal', 'tick', { fill: '#ffffff' });
  for (const [pr, color] of [['(14, 15)', C.eps], ['(10, 11)', C.bad]]) {
    const c = cal[pr];
    const pts = c.th.map((t, i) => [f.sx(t), f.sy(c.eff[i])]);
    el('path', { d: path(pts), fill: 'none', stroke: color, 'stroke-width': 2.2 }, f.g);
    pts.forEach(([x, y]) => el('circle', { cx: x, cy: y, r: 4, fill: color }, f.g));
  }
  const c = cal['(10, 11)'];
  el('line', { x1: f.sx(c.th[0]), x2: f.sx(c.th[0]), y1: f.sy(c.th[0]), y2: f.sy(c.eff[0]), stroke: C.delta, 'stroke-width': 2 }, f.g);
  text(f.g, f.sx(c.th[0]) + 8, f.sy((c.th[0] + c.eff[0]) / 2), `δ ≈ +${(c.eff[0] - c.th[0]).toFixed(2)} rad`, 'tick', { fill: C.delta });
  text(f.g, 420, 80, '● (10, 11) worst pair', 'tick', { fill: C.bad });
  text(f.g, 420, 100, '● (14, 15) typical pair', 'tick', { fill: C.eps });
  text(svg, 84, 425, 'E4 phase-amplification calibration, ibm_marrakesh.', 'cnote');
}

/** β(θ) and δ(θ) on marrakesh: (10, 11) against the rest. */
function coherent(stage, D) {
  const svg = newSvg(stage, 720, 440);
  const cal = D.rounds.E4.cal;
  const a = frame(svg, { left: 70, top: 50, width: 270, height: 310 }, {
    x: [0.1, 1.6], y: [-0.3, 0.3], xticks: [Math.PI / 8, Math.PI / 4, Math.PI / 2], yticks: [-0.3, -0.15, 0, 0.15, 0.3], xfmt: piLabel, yfmt: (v) => v.toFixed(2),
    xlabel: 'θ (rad)', ylabel: 'local phase β (rad / gate)', title: 'Local phase β(θ)',
  });
  const b = frame(svg, { left: 430, top: 50, width: 270, height: 310 }, {
    x: [0.1, 1.6], y: [-0.3, 0.3], xticks: [Math.PI / 8, Math.PI / 4, Math.PI / 2], yticks: [-0.3, -0.15, 0, 0.15, 0.3], xfmt: piLabel, yfmt: (v) => v.toFixed(2),
    xlabel: 'θ (rad)', ylabel: 'over-rotation δ (rad)', title: 'Over-rotation δ(θ)',
  });
  const draw = (f, xs, ys, bad) => {
    const pts = xs.map((t, i) => [f.sx(t), f.sy(ys[i])]);
    el('path', { d: path(pts), fill: 'none', stroke: bad ? C.bad : C.grey, 'stroke-width': bad ? 2.4 : 1.1, opacity: bad ? 1 : 0.65 }, f.g);
    pts.forEach(([x, y]) => el('circle', { cx: x, cy: y, r: bad ? 3.4 : 2, fill: bad ? C.bad : C.grey, opacity: bad ? 1 : 0.7 }, f.g));
  };
  for (const [pr, c] of Object.entries(cal)) if (pr !== '(10, 11)') draw(a, c.th, c.beta, false);
  draw(a, cal['(10, 11)'].th, cal['(10, 11)'].beta, true);
  const sweep = D.sweeps.E2.pairs;
  for (const [pr, p] of Object.entries(sweep)) if (pr !== '(10, 11)' && pr !== '(93, 94)') draw(b, p.phase_theta, p.delta, false);
  draw(b, sweep['(10, 11)'].phase_theta, sweep['(10, 11)'].delta, true);
  for (const f of [a, b]) el('line', { x1: f.sx(0.1), x2: f.sx(1.6), y1: f.sy(0), y2: f.sy(0), stroke: '#ffffff', 'stroke-opacity': 0.25 }, f.g);
  text(svg, 70, 425, 'E4 calibration (β) and E2 sweep (δ), ibm_marrakesh. Pair (93, 94) gave no usable δ.', 'cnote');
}

/** Raw vs corrected success for all 196 test cases. */
function correction(stage, D) {
  const svg = newSvg(stage);
  const f = frame(svg, { left: 84, top: 50, width: 400, height: 330 }, {
    x: [0, 1], y: [0, 1], xticks: [0, 0.25, 0.5, 0.75, 1], yticks: [0, 0.25, 0.5, 0.75, 1], yfmt: (v) => v.toFixed(2), xfmt: (v) => v.toFixed(2),
    xlabel: 'success, raw gate', ylabel: 'success, with virtual RZ', title: 'Each dot is one test case',
  });
  el('path', { d: path([[f.sx(0), f.sy(0)], [f.sx(1), f.sy(1)]]), stroke: '#ffffff', 'stroke-opacity': 0.35, 'stroke-dasharray': '4 4' }, f.g);
  const cases = [...D.rounds.E4.cases.map((c) => ({ ...c, dev: 'M' })), ...D.rounds.E6.cases.map((c) => ({ ...c, dev: 'K' }))];
  const colorOf = (c) => (c.pair === '(10, 11)' ? C.bad : c.pair === '(0, 1)' && c.dev === 'K' ? C.cz : c.dev === 'M' ? C.eps : C.good);
  for (const c of cases) el('circle', { cx: f.sx(c.raw), cy: f.sy(c.local), r: c.pair === '(10, 11)' ? 4.2 : 3, fill: colorOf(c), opacity: 0.8 }, f.g);
  const lx = 510;
  [['marrakesh pairs', C.eps], ['kingston pairs', C.good], ['(10, 11) worst', C.bad], ['(0, 1) erratic', C.cz]].forEach(([n, col], i) => text(svg, lx, 80 + i * 22, `● ${n}`, 'tick', { fill: col }));
  text(svg, lx, 190, 'above the line:', 'tick');
  text(svg, lx, 206, 'the correction helped', 'tick');
  text(svg, 84, 436, 'E4 (marrakesh) and E6 (kingston), 98 cases each. Kθ = π or 2π from |++⟩.', 'cnote');
}

/** E10: raw, +RZ and 2-CZ on (10, 11). */
function e10(stage, R) {
  const svg = newSvg(stage);
  const cases = Object.entries(R.e10);
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 310 }, {
    x: [0, cases.length], y: [0, 1], xticks: [], yticks: [0, 0.25, 0.5, 0.75, 1], yfmt: (v) => v.toFixed(2), ylabel: 'success probability', title: 'Pair (10, 11), ibm_marrakesh',
  });
  const variants = [['raw', 'fractional, raw', C.eps], ['local', 'fractional + RZ', C.beta], ['cz', '2 × CZ', C.cz]];
  const bw = 0.22;
  cases.forEach(([name, v], i) => {
    variants.forEach(([k, , col], j) => {
      const x = f.sx(i + 0.17 + j * (bw + 0.02));
      const y = f.sy(v[k]);
      el('rect', { x, y, width: f.sx(bw) - f.sx(0), height: f.sy(0) - y, fill: col, rx: 3 }, f.g);
      text(f.g, x + (f.sx(bw) - f.sx(0)) / 2, y - 6, v[k].toFixed(2), 'tick', { 'text-anchor': 'middle', fill: '#e9edf5' });
    });
    text(f.g, f.sx(i + 0.5), f.sy(0) + 20, name.replace('2π/24', 'π/12').replace('3π/24', 'π/8'), 'tick', { 'text-anchor': 'middle' });
  });
  variants.forEach(([, n, col], j) => text(svg, 120 + j * 170, 405, `■ ${n}`, 'tick', { fill: col }));
  text(svg, 84, 430, 'E10, 2,000 shots each. Both implementations carry the same IBM-reported error.', 'cnote');
}

/** H2 projection: gain by layers and family; with bad pairs avoided. */
function h2(stage, R) {
  const svg = newSvg(stage);
  const fams = [['lr_qaoa', 'LR-QAOA'], ['ising', 'Trotter Ising'], ['random', 'Random RZZ']];
  const layers = ['2', '4', '6'];
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 300 }, {
    x: [0, 3], y: [0, 0.6], xticks: [], yticks: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6], yfmt: (v) => `${Math.round(v * 100)}%`,
    ylabel: 'median relative gain', title: 'Projected gain of the θ-aware rule (simulation)',
  });
  const shades = ['#ffd59a', '#ffb454', '#e8892a'];
  fams.forEach(([k, n], i) => {
    layers.forEach((L, j) => {
      const v = R.h2_projection.base[k].by_layers[L];
      const x = f.sx(i + 0.14 + j * 0.25), w = f.sx(0.22) - f.sx(0), y = f.sy(v);
      el('rect', { x, y, width: w, height: f.sy(0) - y, fill: shades[j], rx: 3 }, f.g);
      text(f.g, x + w / 2, y - 6, `${(v * 100).toFixed(0)}%`, 'tick', { 'text-anchor': 'middle', fill: '#e9edf5' });
      const av = R.h2_projection.avoid_bad[k].by_layers[L];
      el('line', { x1: x, x2: x + w, y1: f.sy(av), y2: f.sy(av), stroke: '#ffffff', 'stroke-width': 2 }, f.g);
    });
    text(f.g, f.sx(i + 0.5), f.sy(0) + 20, n, 'tick', { 'text-anchor': 'middle' });
  });
  el('line', { x1: f.sx(0), x2: f.sx(3), y1: f.sy(0.1), y2: f.sy(0.1), stroke: C.bad, 'stroke-dasharray': '6 5', 'stroke-width': 1.5 }, f.g);
  text(f.g, f.sx(0) + 6, f.sy(0.1) - 8, 'H2 target 10%', 'tick', { fill: C.bad });
  layers.forEach((L, j) => text(svg, 110 + j * 110, 395, `■ ${L} layers`, 'tick', { fill: shades[j] }));
  text(svg, 450, 395, '— bad pairs avoided', 'tick', { fill: '#ffffff' });
  text(svg, 84, 425, 'Projection, not data: 8-qubit lines from the 14 calibrated pairs; fidelity × gate survival.', 'cnote', { fill: C.proj });
}

/** Compiler replay: the compiler run on past jobs' circuits, scored by what the hardware measured. */
function replay(stage, R) {
  const K = R.compiler;
  const svg = newSvg(stage, 680, 480);
  const groups = [['E4 · marrakesh', K.e4], ['E6 · kingston *', K.e6], ['E10 · pair (10, 11) *', K.e10]];
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 300 }, {
    x: [0, groups.length], y: [0, 1], xticks: [], yticks: [0, 0.25, 0.5, 0.75, 1], yfmt: (v) => v.toFixed(2),
    ylabel: 'mean measured success', title: 'The compiler on real jobs, using only earlier calibrations',
  });
  const bars = [['qiskit', 'Qiskit (fractional)', C.grey], ['theta', 'θ-Aware', C.eps], ['oracle', 'best possible', C.good]];
  const bw = 0.24;
  groups.forEach(([name, g], i) => {
    bars.forEach(([k, , col], j) => {
      const x = f.sx(i + 0.14 + j * (bw + 0.01)), y = f.sy(g[k]), w = f.sx(bw) - f.sx(0);
      el('rect', { x, y, width: w, height: f.sy(0) - y, fill: col, rx: 3 }, f.g);
      text(f.g, x + w / 2, y - 6, g[k].toFixed(2), 'tick', { 'text-anchor': 'middle', fill: '#e9edf5' });
    });
    text(f.g, f.sx(i + 0.5), f.sy(0) + 20, name, 'tick', { 'text-anchor': 'middle' });
    text(f.g, f.sx(i + 0.5), f.sy(0) + 38, `n = ${g.n} · best choice ${g.best}/${g.n}`, 'tick', { 'text-anchor': 'middle', fill: C.grey });
  });
  bars.forEach(([, n, col], j) => text(svg, 120 + j * 170, 425, `■ ${n}`, 'tick', { fill: col }));
  text(svg, 84, 450, '* held out. Measured outcomes of past jobs (14 Oct 2026).', 'cnote');
  text(svg, 84, 466, '"Best choice": within 2 standard errors of the best measured option.', 'cnote');
}

/** Compiler benchmark: errors and two-qubit gates (simulation). */
function bench(stage, R) {
  const S = R.compiler.sim;
  const svg = newSvg(stage, 680, 480);
  const pols = [['frac', 'Qiskit, fractional', C.grey], ['cz', 'Qiskit, CZ only', C.cz], ['theta', 'θ-Aware', C.eps], ['theta+layout', 'θ-Aware + layout', C.good]];
  const vals = pols.map(([k]) => S.err[k]);
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...vals) * 0.8))), hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...vals) * 1.2)));
  const ticks = []; for (let t = lo; t <= hi * 1.001; t *= 10) ticks.push(t);
  const f = frame(svg, { left: 84, top: 50, width: 560, height: 290 }, {
    x: [0, pols.length], y: [lo, hi], log: true, xticks: [], yticks: ticks, yfmt: (v) => String(Number(v.toPrecision(1))),
    ylabel: 'state infidelity (log)', title: `Simulated algorithm circuits (${S.n}, 6 qubits)`,
  });
  pols.forEach(([k, n, col], i) => {
    const x = f.sx(i + 0.2), w = f.sx(0.6) - f.sx(0), y = f.sy(S.err[k]);
    el('rect', { x, y, width: w, height: f.sy(lo) - y, fill: col, rx: 3 }, f.g);
    text(f.g, x + w / 2, y - 6, S.err[k].toExponential(1), 'tick', { 'text-anchor': 'middle', fill: '#e9edf5' });
    text(f.g, f.sx(i + 0.5), f.sy(lo) + 20, n, 'tick', { 'text-anchor': 'middle' });
    text(f.g, f.sx(i + 0.5), f.sy(lo) + 38, `${S.g2[k].toFixed(1)} two-qubit gates`, 'tick', { 'text-anchor': 'middle', fill: C.grey });
  });
  text(svg, 84, 430, 'Projection, not data: measured gate parameters plus measured-size drift;', 'cnote', { fill: C.proj });
  text(svg, 84, 446, 'single-qubit gates and readout ideal. Lower is better.', 'cnote', { fill: C.proj });
}

export function drawChart(name, stage, D, R) {
  const fns = { problem: () => problem(stage, D), model: () => model(stage, D), coherent: () => coherent(stage, D), correction: () => correction(stage, D), e10: () => e10(stage, R), h2: () => h2(stage, R), replay: () => replay(stage, R), bench: () => bench(stage, R) };
  fns[name]?.();
}
export { piLabel };
