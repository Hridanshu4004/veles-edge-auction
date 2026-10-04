/**
 * EdgeTruth V3 — Shared JS Module
 * api.js  — All API calls, SSE stream, formatting helpers, node-graph renderer.
 * One import per page. No page may define its own fetch logic.
 */

const BASE = '';  // same origin

// ── Formatting ─────────────────────────────────────────────────────────────
export function fmt$  (v) { return '$' + Number(v).toLocaleString(undefined, {maximumFractionDigits: 0}); }
export function fmtPct(v) { return (v * 100).toFixed(1) + '%'; }
export function fmtMs (v) { return Number(v).toFixed(2) + ' ms'; }
export function fmtK  (v) { return v >= 1e6 ? (v/1e6).toFixed(2)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'k' : String(v); }
export function timeAgo(ts) {
  const d = Math.floor(Date.now()/1000 - ts);
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.floor(d/60)}m ago`;
  return `${Math.floor(d/3600)}h ago`;
}

// ── API calls ───────────────────────────────────────────────────────────────
async function apiFetch(path) {
  try {
    const r = await fetch(BASE + path);
    if (!r.ok) throw new Error(r.statusText);
    return await r.json();
  } catch (e) {
    console.warn('API error:', path, e.message);
    return null;
  }
}
export const api = {
  stats:       () => apiFetch('/api/stats'),
  nodes:       () => apiFetch('/api/nodes'),
  node:        (id) => apiFetch(`/api/nodes/${id}`),
  auctions:    () => apiFetch('/api/auctions'),
  auction:     (id) => apiFetch(`/api/auctions/${id}`),
  benchmarks:  () => apiFetch('/api/benchmarks'),
  attacks:     () => apiFetch('/api/attacks'),
  simulateAttack: (attack) => fetch('/api/attacks/simulate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({attack}),
  }).then(r => r.json()),
};

// ── Mock banner ──────────────────────────────────────────────────────────────
export function showMockBanner(isMock) {
  if (!isMock) return;
  const b = document.createElement('div');
  b.className = 'mock-banner';
  b.textContent = '⚠ MOCK DATA — Backend unreachable or MOCK=1';
  document.body.insertBefore(b, document.body.firstChild);
}

// ── SSE event stream ─────────────────────────────────────────────────────────
export function connectEventStream(onEvent) {
  const es = new EventSource('/events');
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)); }
    catch (_) {}
  };
  es.onerror = () => setTimeout(() => connectEventStream(onEvent), 3000);
  return es;
}

// ── Event type → styling ─────────────────────────────────────────────────────
const EVT_STYLE = {
  TASK_ALLOCATED:     { dot: 'cyan',   label: 'ALLOCATED' },
  BID_RECEIVED:       { dot: 'cyan',   label: 'BID' },
  SLA_MET:            { dot: 'green',  label: 'SLA MET' },
  SLA_BREACH:         { dot: 'red',    label: 'SLA BREACH' },
  COLLATERAL_SLASHED: { dot: 'red',    label: 'SLASHED' },
  NODE_REGISTERED:    { dot: 'orange', label: 'NODE REG' },
};

export function makeEventFeedItem(evt) {
  const s = EVT_STYLE[evt.type] || { dot: 'cyan', label: evt.type };
  const div = document.createElement('div');
  div.className = 'feed-item';
  div.innerHTML = `
    <div class="feed-dot ${s.dot}"></div>
    <div style="flex:1">
      <span class="feed-text"><strong class="mono">${s.label}</strong>
        — node <strong>${evt.node_id}</strong>
        auction <strong>${evt.auction_id}</strong>
        val <strong>${fmt$(evt.value)}</strong>
      </span>
    </div>
    <span class="feed-time">${new Date(evt.timestamp*1000).toLocaleTimeString()}</span>
  `;
  return div;
}

// ── Node Graph Renderer (SVG) ────────────────────────────────────────────────
export function renderNodeGraph(svgEl, nodes, onNodeClick) {
  const W = svgEl.clientWidth  || 800;
  const H = svgEl.clientHeight || 420;
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgEl.innerHTML = '';

  const typeColor = {
    HONEST_STABLE:  '#10B981',
    CHEAP_UNSTABLE: '#F59E0B',
    LIAR:           '#EF4444',
    STRATEGIC:      '#8B5CF6',
  };

  // Draw edges first (beneath nodes)
  const edgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  edgeG.setAttribute('opacity', '0.15');
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j += 3) {
      const a = nodes[i], b = nodes[j];
      const nx = n => n.x / 800 * W;
      const ny = n => n.y / 450 * H;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', nx(a)); line.setAttribute('y1', ny(a));
      line.setAttribute('x2', nx(b)); line.setAttribute('y2', ny(b));
      line.setAttribute('stroke', '#06B6D4');
      line.setAttribute('stroke-width', '0.5');
      edgeG.appendChild(line);
    }
  }
  svgEl.appendChild(edgeG);

  // Active allocation animated edge (random pair)
  if (nodes.length >= 2) {
    const a = nodes[Math.floor(Math.random() * nodes.length)];
    const b = nodes[Math.floor(Math.random() * nodes.length)];
    const nx = n => (n.x / 800) * W;
    const ny = n => (n.y / 450) * H;
    const animEdge = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    animEdge.setAttribute('x1', nx(a)); animEdge.setAttribute('y1', ny(a));
    animEdge.setAttribute('x2', nx(b)); animEdge.setAttribute('y2', ny(b));
    animEdge.setAttribute('stroke', '#06B6D4');
    animEdge.setAttribute('stroke-width', '1.5');
    animEdge.innerHTML = `<animate attributeName="opacity" values="0;1;0" dur="1.8s" repeatCount="indefinite"/>`;
    svgEl.appendChild(animEdge);
  }

  // Draw nodes
  nodes.forEach(n => {
    const nx = (n.x / 800) * W;
    const ny = (n.y / 450) * H;
    const r = 6 + (n.capacity_cpu / 16) * 10;
    const color = typeColor[n.node_type] || '#06B6D4';
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.style.cursor = 'pointer';

    // Outer ring for liars
    if (n.node_type === 'LIAR' || n.node_type === 'STRATEGIC') {
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      ring.setAttribute('cx', nx); ring.setAttribute('cy', ny);
      ring.setAttribute('r', r + 4);
      ring.setAttribute('fill', 'none');
      ring.setAttribute('stroke', '#EF4444');
      ring.setAttribute('stroke-width', '1');
      ring.setAttribute('stroke-dasharray', '3 2');
      ring.innerHTML = `<animateTransform attributeName="transform" type="rotate" from="0 ${nx} ${ny}" to="360 ${nx} ${ny}" dur="6s" repeatCount="indefinite"/>`;
      g.appendChild(ring);
    }

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', nx); circle.setAttribute('cy', ny);
    circle.setAttribute('r', r);
    circle.setAttribute('fill', color);
    circle.setAttribute('fill-opacity', '0.85');
    circle.setAttribute('stroke', color);
    circle.setAttribute('stroke-width', '1.5');
    g.appendChild(circle);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', nx); label.setAttribute('y', ny + r + 12);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', '#64748B');
    label.setAttribute('font-size', '9');
    label.setAttribute('font-family', 'JetBrains Mono, monospace');
    label.textContent = n.node_id;
    g.appendChild(label);

    g.addEventListener('click', () => onNodeClick && onNodeClick(n));
    svgEl.appendChild(g);
  });
}

// ── Tier badge ───────────────────────────────────────────────────────────────
export function trustBadge(tier) {
  const map = { HIGH: 'badge-green', MED: 'badge-orange', LOW: 'badge-red' };
  return `<span class="badge ${map[tier]||'badge-cyan'}">${tier}</span>`;
}
export function typeBadge(type) {
  const map = {
    HONEST_STABLE:  'badge-green',
    CHEAP_UNSTABLE: 'badge-orange',
    LIAR:           'badge-red',
    STRATEGIC:      'badge-purple',
  };
  return `<span class="badge ${map[type]||'badge-cyan'}">${type.replace('_',' ')}</span>`;
}
