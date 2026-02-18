// ═══════════════════════════════════════════════════════
// Nexus AI - SAO x Tensura (Great Sage) UI Controller
// ═══════════════════════════════════════════════════════

let ws = null;
let sessionId = 'session_' + Date.now();
let isProcessing = false;
let startTime = Date.now();

// Agent/Skill definitions (SAO-style skill list)
const SKILLS = [
    { name: 'Coder',     icon: '&#xe2bf;', desc: 'Code generation & debug',     emoji: '\u2699' },
    { name: 'Reasoning', icon: '&#xe1e0;', desc: 'Chain-of-thought logic',      emoji: '\u2727' },
    { name: 'Research',  icon: '&#xe153;', desc: 'Web search & extraction',     emoji: '\u2741' },
    { name: 'Knowledge', icon: '&#xe155;', desc: 'Knowledge graph queries',     emoji: '\u25C8' },
    { name: 'File',      icon: '&#xe14e;', desc: 'File operations',             emoji: '\u2630' },
    { name: 'Web',       icon: '&#xe157;', desc: 'Web browsing & scraping',     emoji: '\u2302' },
    { name: 'Shell',     icon: '&#xe157;', desc: 'Sandboxed shell execution',   emoji: '\u276F' },
    { name: 'Vision',    icon: '&#xe155;', desc: 'Image/PDF analysis',          emoji: '\u25CE' },
    { name: 'Optimizer', icon: '&#xe1e0;', desc: 'Self-optimization engine',    emoji: '\u2726' },
];

// ═══ Initialize ═══
document.addEventListener('DOMContentLoaded', () => {
    drawHexBackground();
    renderSkillList();
    connectWebSocket();
    setupInput();
    startUptimeTimer();
    document.getElementById('session-id').textContent = sessionId.slice(-6);
});

// ═══ Hex Background (SAO-style) ═══
function drawHexBackground() {
    const canvas = document.getElementById('hex-bg');
    const ctx = canvas.getContext('2d');
    let w, h;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
        draw();
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        const size = 30;
        const hGap = size * Math.sqrt(3);
        const vGap = size * 1.5;

        ctx.strokeStyle = 'rgba(0, 150, 255, 0.06)';
        ctx.lineWidth = 0.5;

        for (let row = -1; row < h / vGap + 1; row++) {
            for (let col = -1; col < w / hGap + 1; col++) {
                const x = col * hGap + (row % 2 ? hGap / 2 : 0);
                const y = row * vGap;
                drawHex(ctx, x, y, size);
            }
        }

        // Glow spots
        const time = Date.now() * 0.001;
        for (let i = 0; i < 3; i++) {
            const gx = (Math.sin(time * 0.3 + i * 2.1) * 0.5 + 0.5) * w;
            const gy = (Math.cos(time * 0.2 + i * 1.7) * 0.5 + 0.5) * h;
            const grad = ctx.createRadialGradient(gx, gy, 0, gx, gy, 150);
            grad.addColorStop(0, 'rgba(0, 180, 255, 0.05)');
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.fillRect(gx - 150, gy - 150, 300, 300);
        }
    }

    function drawHex(ctx, x, y, s) {
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 6;
            const px = x + s * Math.cos(angle);
            const py = y + s * Math.sin(angle);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
    }

    window.addEventListener('resize', resize);
    resize();

    // Animate glow spots
    function animateGlow() {
        draw();
        requestAnimationFrame(animateGlow);
    }
    animateGlow();
}

// ═══ Skill List Renderer ═══
function renderSkillList() {
    const container = document.getElementById('skill-list');
    SKILLS.forEach((skill, i) => {
        const card = document.createElement('div');
        card.className = 'skill-card';
        card.id = `skill-${skill.name.toLowerCase()}`;
        card.innerHTML = `
            <div class="skill-icon">${skill.emoji}</div>
            <div class="skill-info">
                <div class="skill-name">${skill.name}</div>
                <div class="skill-desc">${skill.desc}</div>
            </div>
            <div class="skill-level">Lv.${Math.floor(Math.random() * 5) + 5}</div>
        `;
        container.appendChild(card);
    });
}

// ═══ WebSocket Connection ═══
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiKey = window.__NEXUS_API_KEY || '';
    const keyParam = apiKey ? `?api_key=${apiKey}` : '';
    ws = new WebSocket(`${protocol}//${location.host}/ws${keyParam}`);

    ws.onopen = () => {
        const badge = document.getElementById('status-badge');
        badge.classList.remove('offline');
        badge.querySelector('.status-text').textContent = 'ONLINE';
        console.log('Neural link established');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleEvent(data);
    };

    ws.onclose = () => {
        const badge = document.getElementById('status-badge');
        badge.classList.add('offline');
        badge.querySelector('.status-text').textContent = 'OFFLINE';
        console.log('Neural link severed. Reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => console.error('Link error:', err);
}

// ═══ Event Handlers ═══
function handleEvent(data) {
    const type = data.type;
    const content = data.content || '';

    switch (type) {
        case 'received':
            addThinkEntry('\u25C8', content, 'received');
            break;
        case 'memory_scan':
            addThinkEntry('\u2726', content, 'memory');
            break;
        case 'memory_found':
            addThinkEntry('\u25C7', content, 'memory');
            break;
        case 'cache_hit':
            addThinkEntry('\u26A1', content, 'selected');
            showSkillActivation('CACHE HIT');
            break;
        case 'routing':
            addThinkEntry('\u2192', content, 'routing');
            break;
        case 'routed':
            addThinkEntry('\u2713', content, 'routing');
            parseAndActivateAgent(content);
            break;
        case 'hypothesis':
            addThinkEntry('\u2727', content, 'hypothesis');
            break;
        case 'selected':
            addThinkEntry('\u2714', content, 'selected');
            break;
        case 'verified':
            addThinkEntry('\u2611', content, 'selected');
            break;
        case 'generating':
            addThinkEntry('\u270E', content, 'generating');
            break;
        case 'final_answer':
            addAssistantMessage(content);
            setProcessing(false);
            clearActiveAgent();
            break;
        case 'budget_status':
            try { updateBudget(JSON.parse(content)); } catch (e) {}
            break;
        case 'budget_exhausted':
            addThinkEntry('\u26D4', content, 'error');
            break;
        case 'error':
            addThinkEntry('\u2716', content, 'error');
            addAssistantMessage('Error: ' + content);
            setProcessing(false);
            clearActiveAgent();
            break;
        default:
            addThinkEntry('\u2022', `[${type}] ${content}`, '');
    }
}

// ═══ Agent activation ═══
function parseAndActivateAgent(content) {
    // Parse "Agents: ['reasoning']" from routed event
    const match = content.match(/Agents:\s*\[([^\]]*)\]/i);
    if (match) {
        const agents = match[1].replace(/['"]/g, '').split(',').map(s => s.trim()).filter(Boolean);
        if (agents.length > 0) {
            activateSkill(agents[0]);
        }
    }
}

function activateSkill(agentName) {
    // Highlight in skill list
    document.querySelectorAll('.skill-card').forEach(c => c.classList.remove('active'));
    const card = document.getElementById(`skill-${agentName.toLowerCase()}`);
    if (card) card.classList.add('active');

    // Show active agent panel
    const panel = document.getElementById('active-agent');
    panel.innerHTML = `
        <div class="agent-active">
            <div class="agent-active-name">${agentName}</div>
            <div class="agent-active-status">Processing...</div>
        </div>
    `;

    // Show overlay briefly
    showSkillActivation(agentName.toUpperCase());
}

function clearActiveAgent() {
    document.querySelectorAll('.skill-card').forEach(c => c.classList.remove('active'));
    const panel = document.getElementById('active-agent');
    panel.innerHTML = `
        <div class="agent-idle">
            <div class="idle-diamond">
                <svg viewBox="0 0 40 40">
                    <polygon points="20,2 38,20 20,38 2,20" fill="none" stroke="currentColor" stroke-width="1"/>
                </svg>
            </div>
            <span>Awaiting Input</span>
        </div>
    `;
}

function showSkillActivation(name) {
    const overlay = document.getElementById('skill-overlay');
    document.getElementById('skill-activate-name').textContent = name;
    overlay.classList.remove('hidden');
    overlay.classList.add('show');
    setTimeout(() => {
        overlay.classList.remove('show');
        overlay.classList.add('hidden');
    }, 1200);
}

// ═══ Thinking Log (Great Sage Style) ═══
function addThinkEntry(icon, text, className) {
    const log = document.getElementById('thinking-log');
    const entry = document.createElement('div');
    entry.className = 'think-entry ' + (className || '');

    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    entry.innerHTML = `<span class="time">${time}</span> <span class="icon">${icon}</span> ${escapeHtml(text)}`;

    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;

    // Keep log manageable
    while (log.children.length > 100) {
        log.removeChild(log.firstChild);
    }
}

// ═══ Chat Messages ═══
function addUserMessage(text) {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function addAssistantMessage(text) {
    const messages = document.getElementById('messages');

    // Remove streaming indicator if present
    const streaming = messages.querySelector('.streaming-msg');
    if (streaming) streaming.remove();

    const div = document.createElement('div');
    div.className = 'message assistant';
    div.innerHTML = `
        <div class="bubble">
            <div class="agent-label">Nexus AI</div>
            ${formatMessage(text)}
        </div>
    `;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

function addStreamingIndicator() {
    const messages = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'message assistant streaming-msg';
    div.innerHTML = `
        <div class="bubble">
            <div class="agent-label">Nexus AI</div>
            <div class="streaming-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

// ═══ Budget Update ═══
function updateBudget(status) {
    const used = status.tokens_used || 0;
    const total = status.daily_limit || 50000;
    const ratio = status.usage_ratio || 0;
    const remaining = 1 - ratio;
    const reqCount = status.request_count || 0;

    // HUD bar
    document.getElementById('budget-text').textContent = (total - used).toLocaleString();
    const tpFill = document.getElementById('budget-fill');
    tpFill.style.width = (remaining * 100) + '%';
    tpFill.className = 'bar-fill tp-fill';
    if (ratio > 0.9) tpFill.classList.add('danger');
    else if (ratio > 0.7) tpFill.classList.add('warning');

    // Request bar
    const maxReq = 100;
    document.getElementById('req-text').textContent = reqCount;
    document.getElementById('req-fill').style.width = Math.min(100, (reqCount / maxReq) * 100) + '%';

    // Pool ring
    const circle = document.getElementById('pool-circle');
    const circumference = 264; // 2 * PI * 42
    circle.style.strokeDashoffset = circumference * ratio;
    if (ratio > 0.9) circle.style.stroke = '#ff4466';
    else if (ratio > 0.7) circle.style.stroke = '#ffaa33';
    else circle.style.stroke = 'var(--accent)';

    document.getElementById('pool-pct').textContent = Math.round(remaining * 100) + '%';
    document.getElementById('tokens-used').textContent = used.toLocaleString();
    document.getElementById('tokens-limit').textContent = total.toLocaleString();
    document.getElementById('req-count').textContent = reqCount;
}

// ═══ Processing State ═══
function setProcessing(state) {
    isProcessing = state;
    document.getElementById('send-btn').disabled = state;
    if (state) {
        addStreamingIndicator();
    }
    if (!state) {
        document.getElementById('user-input').focus();
    }
}

// ═══ Input Handling ═══
function setupInput() {
    const input = document.getElementById('user-input');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
}

function sendMessage() {
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text || isProcessing) return;

    addUserMessage(text);
    setProcessing(true);
    input.value = '';

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            content: text,
            session_id: sessionId,
        }));
    } else {
        addAssistantMessage('Neural link disconnected. Attempting to reconnect...');
        setProcessing(false);
        connectWebSocket();
    }
}

// ═══ Uptime Timer ═══
function startUptimeTimer() {
    setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const s = (elapsed % 60).toString().padStart(2, '0');
        document.getElementById('uptime').textContent = `${m}:${s}`;
    }, 1000);
}

// ═══ Utilities ═══
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMessage(text) {
    let html = escapeHtml(text);

    // Code blocks
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
}
