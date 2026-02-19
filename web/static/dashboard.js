// ═══════════════════════════════════════════════════════
// Nexus AI — Dashboard Controller
// ═══════════════════════════════════════════════════════

const SKILL_CATEGORIES = {
    information:  { label: '資訊',   color: '#00d4ff', emoji: '◈' },
    research:     { label: '研究',   color: '#00ffaa', emoji: '⬡' },
    productivity: { label: '生產力', color: '#ff9a3c', emoji: '◆' },
    tools:        { label: '工具',   color: '#aa66ff', emoji: '◇' },
    system:       { label: '系統',   color: '#ffd700', emoji: '✦' },
    general:      { label: '其他',   color: '#8ab4d8', emoji: '○' },
};

let dashData = null;
let graphRendered = false;
let _lastGraphW = 0;
let _lastGraphH = 0;

// ─── Init ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    drawHexBg();
    startClock();
    setupTabs();
    fetchDashboard();
    setInterval(fetchDashboard, 30000);
    setupGraphResizeObserver();
});

// ─── Data Fetch ─────────────────────────────────────────
async function fetchDashboard() {
    try {
        const apiKey = window.__NEXUS_API_KEY || '';
        const headers = apiKey ? { 'X-API-Key': apiKey } : {};
        const r = await fetch('/api/dashboard', { headers });
        if (!r.ok) return;
        dashData = await r.json();
        updateMainPanel(dashData);
    } catch (e) {
        console.warn('Dashboard fetch error:', e);
    }
}

// ─── Update UI ──────────────────────────────────────────
function updateMainPanel(data) {
    // Online badge
    const isReady = data.status === 'operational';
    const onlineText = document.getElementById('dash-online-text');
    onlineText.textContent = isReady ? 'ONLINE' : 'INITIALIZING';

    // System stats
    setText('sys-agents', data.agents?.length ?? '—');
    setText('sys-skills',  data.skills?.length  ?? '—');
    setText('sys-reqs',    data.budget?.request_count ?? '—');

    // Telegram channel
    const tgDot   = document.getElementById('tg-dot');
    const tgBadge = document.getElementById('tg-badge');
    if (data.telegram) {
        tgDot.className   = 'ch-dot online';
        tgBadge.textContent = 'online';
        tgBadge.className   = 'ch-badge online';
    } else {
        tgDot.className   = 'ch-dot offline';
        tgBadge.textContent = 'offline';
        tgBadge.className   = 'ch-badge offline';
    }

    // Token pool
    const budget = data.budget || {};
    const used   = budget.tokens_used   || 0;
    const limit  = budget.daily_limit   || 50000;
    const ratio  = budget.usage_ratio   || 0;
    const remaining = 1 - ratio;

    setText('tp-used',  used.toLocaleString());
    setText('tp-limit', limit.toLocaleString());
    setText('tp-pct',   Math.round(remaining * 100) + '%');

    const fill = document.getElementById('tp-fill');
    fill.style.width = remaining * 100 + '%';
    fill.className = 'tp-bar-fill' + (ratio > 0.9 ? ' danger' : ratio > 0.7 ? ' warning' : '');

    // Daily brief
    updateBrief(data.schedules || []);

    // If skill tab is visible, render graph
    const skillTab = document.getElementById('tab-skills');
    if (skillTab.classList.contains('active') && !graphRendered) {
        renderSkillGraph(data.skills || []);
    }
}

function updateBrief(schedules) {
    const now = new Date();
    const dayLabels = ['日', '一', '二', '三', '四', '五', '六'];
    const dateStr = `${now.getMonth() + 1}月${now.getDate()}日（星期${dayLabels[now.getDay()]}）`;
    setText('brief-date', dateStr);

    if (!schedules.length) {
        document.getElementById('brief-list').innerHTML =
            '<div class="brief-placeholder">今日無排程</div>';
        return;
    }

    // Map JS day index → schedule day keys
    const dayKeys = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
    const todayKey  = dayKeys[now.getDay()];
    const isWeekday = now.getDay() >= 1 && now.getDay() <= 5;
    const todayStr  = now.toISOString().split('T')[0];

    const todayItems = schedules
        .filter(s => {
            if (!s.enabled) return false;
            const d = s.days || 'daily';
            return d === 'daily' ||
                   (d === 'weekdays' && isWeekday) ||
                   (d === 'weekends' && !isWeekday) ||
                   d.split(',').map(x => x.trim()).includes(todayKey);
        })
        .sort((a, b) => (a.time || '').localeCompare(b.time || ''));

    if (!todayItems.length) {
        document.getElementById('brief-list').innerHTML =
            '<div class="brief-placeholder">今日無排程</div>';
        return;
    }

    document.getElementById('brief-list').innerHTML = todayItems.map(s => {
        const isDone = s.last_run && s.last_run.startsWith(todayStr);
        return `
            <div class="brief-item ${isDone ? 'done' : ''}">
                <span class="bi-time">${s.time || '--:--'}</span>
                <span class="bi-name">${escHtml(s.name || s.action || '—')}</span>
                ${isDone ? '<span class="bi-done">✓</span>' : ''}
            </div>`;
    }).join('');
}

// ─── Quick Access ────────────────────────────────────────
function openChat(query) {
    // Navigate to main chat page and pre-fill query via URL param
    window.location.href = '/?q=' + encodeURIComponent(query);
}

// ─── ResizeObserver for skill graph ─────────────────────
function setupGraphResizeObserver() {
    if (!window.ResizeObserver) return;
    const wrap = document.querySelector('.skills-graph-wrap');
    if (!wrap) return;
    new ResizeObserver(() => {
        if (document.getElementById('tab-skills').classList.contains('active') && dashData) {
            renderSkillGraph(dashData.skills || []);
        }
    }).observe(wrap);
}

// ─── Tab switching ───────────────────────────────────────
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');

            if (tab === 'skills' && dashData && !graphRendered) {
                // Slight delay so the container is visible/sized
                setTimeout(() => renderSkillGraph(dashData.skills || []), 50);
            }
        });
    });
}

// ─── Clock ───────────────────────────────────────────────
function startClock() {
    function tick() {
        const n = new Date();
        const t = [n.getHours(), n.getMinutes(), n.getSeconds()]
            .map(x => String(x).padStart(2, '0')).join(':');
        setText('dash-clock', t);
    }
    tick();
    setInterval(tick, 1000);
}

// ═══════════════════════════════════════════════════════
//  D3.js Skill Evolution Graph
// ═══════════════════════════════════════════════════════
function renderSkillGraph(skills) {
    const wrap = document.querySelector('.skills-graph-wrap');
    if (!wrap) return;
    const W = wrap.clientWidth  || 800;
    const H = wrap.clientHeight || 480;

    // Skip if size unchanged (debounce resize)
    if (Math.abs(W - _lastGraphW) < 10 && Math.abs(H - _lastGraphH) < 10 && graphRendered) return;
    _lastGraphW = W;
    _lastGraphH = H;
    graphRendered = true;

    // Clear
    d3.select('#skill-graph').selectAll('*').remove();

    const svg = d3.select('#skill-graph')
        .attr('width', W)
        .attr('height', H);

    // ─── Defs: glow filters ───────────────────────────
    const defs = svg.append('defs');

    function addGlow(id, color, blur) {
        const f = defs.append('filter').attr('id', id);
        f.append('feColorMatrix')
            .attr('type', 'matrix')
            .attr('values', `0 0 0 0 ${hexR(color)}  0 0 0 0 ${hexG(color)}  0 0 0 0 ${hexB(color)}  0 0 0 1 0`);
        f.append('feGaussianBlur').attr('stdDeviation', blur).attr('result', 'blur');
        const m = f.append('feMerge');
        m.append('feMergeNode').attr('in', 'blur');
        m.append('feMergeNode').attr('in', 'SourceGraphic');
    }

    addGlow('glow-core',  '#ffd700', 8);
    Object.entries(SKILL_CATEGORIES).forEach(([key, cat]) => {
        addGlow('glow-' + key, cat.color, 5);
    });

    // ─── Build node/link data ─────────────────────────
    const catGroups = {};
    skills.forEach(s => {
        const k = s.category || 'general';
        if (!catGroups[k]) catGroups[k] = [];
        catGroups[k].push(s);
    });

    const nodes = [{ id: '__core', label: 'NEXUS\nCORE', type: 'core', r: 26 }];
    const links = [];

    Object.entries(catGroups).forEach(([catKey, catSkills]) => {
        const cat = SKILL_CATEGORIES[catKey] || SKILL_CATEGORIES.general;
        const catId = 'cat_' + catKey;
        nodes.push({ id: catId, label: cat.label, type: 'category', color: cat.color, r: 18, catKey });
        links.push({ source: '__core', target: catId, dist: 110, strength: 0.25 });

        catSkills.forEach(skill => {
            nodes.push({
                id: skill.name,
                label: skill.name,
                desc:  skill.description || '',
                type:  'skill',
                color: cat.color,
                r: 11,
                catKey,
            });
            links.push({ source: catId, target: skill.name, dist: 70, strength: 0.5 });
        });
    });

    // Render sidebar
    renderSkillSidebar(catGroups);

    // ─── Force simulation ─────────────────────────────
    const sim = d3.forceSimulation(nodes)
        .force('link',    d3.forceLink(links).id(d => d.id)
                            .distance(d => d.dist || 80)
                            .strength(d => d.strength || 0.4))
        .force('charge',  d3.forceManyBody().strength(d => d.type === 'core' ? -600 : -180))
        .force('center',  d3.forceCenter(W / 2, H / 2))
        .force('collide', d3.forceCollide(d => d.r + 12).strength(0.8));

    // Pin core to center
    const coreNode = nodes.find(n => n.id === '__core');
    if (coreNode) { coreNode.fx = W / 2; coreNode.fy = H / 2; }

    // ─── Links ────────────────────────────────────────
    const linkSel = svg.append('g').attr('class', 'links')
        .selectAll('line').data(links).join('line')
        .attr('stroke', d => {
            const t = typeof d.target === 'object' ? d.target : nodes.find(n => n.id === d.target);
            return t?.color || '#336';
        })
        .attr('stroke-opacity', 0.25)
        .attr('stroke-width', 1);

    // ─── Nodes ────────────────────────────────────────
    const nodeSel = svg.append('g').attr('class', 'nodes')
        .selectAll('g').data(nodes).join('g')
        .attr('class', 'graph-node')
        .style('cursor', d => d.type === 'skill' ? 'pointer' : 'default')
        .call(d3.drag()
            .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end',   (e, d) => {
                if (!e.active) sim.alphaTarget(0);
                if (d.type !== 'core') { d.fx = null; d.fy = null; }
            })
        );

    // Outer glow ring for categories
    nodeSel.filter(d => d.type === 'category').append('circle')
        .attr('r', d => d.r + 7)
        .attr('fill', 'none')
        .attr('stroke', d => d.color)
        .attr('stroke-width', 0.5)
        .attr('opacity', 0.25);

    // Main circle
    nodeSel.append('circle')
        .attr('r', d => d.r)
        .attr('fill', d => {
            if (d.type === 'core') return 'rgba(255,215,0,0.12)';
            return d.color + '20';
        })
        .attr('stroke', d => d.type === 'core' ? '#ffd700' : d.color)
        .attr('stroke-width', d => d.type === 'core' ? 2.5 : 1.5)
        .attr('filter', d => {
            if (d.type === 'core') return 'url(#glow-core)';
            return 'url(#glow-' + (d.catKey || 'general') + ')';
        });

    // Labels
    nodeSel.each(function(d) {
        const g = d3.select(this);
        if (d.type === 'core') {
            // Two-line label
            g.append('text').text('NEXUS')
                .attr('text-anchor', 'middle')
                .attr('dy', '-0.3em')
                .attr('font-family', 'Orbitron, monospace')
                .attr('font-size', '9px')
                .attr('fill', '#ffd700')
                .attr('pointer-events', 'none');
            g.append('text').text('CORE')
                .attr('text-anchor', 'middle')
                .attr('dy', '0.9em')
                .attr('font-family', 'Orbitron, monospace')
                .attr('font-size', '9px')
                .attr('fill', '#ffd700')
                .attr('pointer-events', 'none');
        } else {
            g.append('text').text(d.label)
                .attr('text-anchor', 'middle')
                .attr('dy', '0.35em')
                .attr('font-family', 'Orbitron, monospace')
                .attr('font-size', d.type === 'category' ? '9px' : '7.5px')
                .attr('fill', d.color)
                .attr('pointer-events', 'none');
        }
    });

    // Tooltip (mouse + touch)
    const tooltip = document.getElementById('skill-tooltip');

    function showTooltip(d, cx, cy) {
        if (d.type !== 'skill') { tooltip.classList.add('hidden'); return; }
        const cat = SKILL_CATEGORIES[d.catKey] || SKILL_CATEGORIES.general;
        setText('stt-name',     d.label);
        setText('stt-category', cat.label);
        setText('stt-desc',     d.desc || '—');
        document.getElementById('stt-category').style.color = cat.color;
        tooltip.classList.remove('hidden');
        const rect = wrap.getBoundingClientRect();
        let x = cx - rect.left + 14;
        let y = cy - rect.top  - 10;
        if (x + 210 > W) x -= 220;
        if (y + 130 > H) y -= 110;
        tooltip.style.left = x + 'px';
        tooltip.style.top  = y + 'px';
    }

    nodeSel
        .on('mouseenter', (e, d) => showTooltip(d, e.clientX, e.clientY))
        .on('mousemove',  (e, d) => showTooltip(d, e.clientX, e.clientY))
        .on('mouseleave', ()     => tooltip.classList.add('hidden'))
        // Touch tap = toggle tooltip
        .on('click', (e, d) => {
            if (tooltip.classList.contains('hidden')) {
                showTooltip(d, e.clientX || (e.touches?.[0]?.clientX ?? 0), e.clientY || (e.touches?.[0]?.clientY ?? 0));
            } else {
                tooltip.classList.add('hidden');
            }
        });

    // Tick update
    sim.on('tick', () => {
        linkSel
            .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}

// ─── Skill sidebar ───────────────────────────────────────
function renderSkillSidebar(catGroups) {
    const sidebar = document.getElementById('skills-sidebar');
    if (!Object.keys(catGroups).length) {
        sidebar.innerHTML = '<div class="sb-loading">No skills loaded</div>';
        return;
    }

    sidebar.innerHTML = Object.entries(catGroups).map(([catKey, skills]) => {
        const cat = SKILL_CATEGORIES[catKey] || SKILL_CATEGORIES.general;
        const skillsHtml = skills.map(s => `
            <div class="sb-skill-item">
                <span class="sb-dot" style="background:${cat.color}"></span>
                <span>${escHtml(s.name)}</span>
            </div>`).join('');
        return `
            <div class="sb-category">
                <div class="sb-cat-header" style="color:${cat.color};border-color:${cat.color}">
                    <span>${cat.emoji}</span>
                    <span>${cat.label}</span>
                    <span class="sb-cat-count">${skills.length}</span>
                </div>
                <div class="sb-skills">${skillsHtml}</div>
            </div>`;
    }).join('');
}

// ═══════════════════════════════════════════════════════
//  Hex Background (same as app.js)
// ═══════════════════════════════════════════════════════
function drawHexBg() {
    const canvas = document.getElementById('hex-bg');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w, h;

    function resize() {
        w = canvas.width  = window.innerWidth;
        h = canvas.height = window.innerHeight;
        draw();
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const size = 30;
        const hGap = size * Math.sqrt(3);
        const vGap = size * 1.5;
        ctx.strokeStyle = 'rgba(0,150,255,0.06)';
        ctx.lineWidth = 0.5;
        for (let row = -1; row < h / vGap + 1; row++) {
            for (let col = -1; col < w / hGap + 1; col++) {
                const x = col * hGap + (row % 2 ? hGap / 2 : 0);
                const y = row * vGap;
                hexPath(ctx, x, y, size);
            }
        }
    }

    function hexPath(ctx, x, y, s) {
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i - Math.PI / 6;
            const px = x + s * Math.cos(a);
            const py = y + s * Math.sin(a);
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
    }

    window.addEventListener('resize', resize);
    resize();
}

// ─── Utilities ───────────────────────────────────────────
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function escHtml(str) {
    return String(str)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Parse hex color components (0..1 range for feColorMatrix)
function hexR(hex) { return parseInt(hex.slice(1, 3), 16) / 255; }
function hexG(hex) { return parseInt(hex.slice(3, 5), 16) / 255; }
function hexB(hex) { return parseInt(hex.slice(5, 7), 16) / 255; }
