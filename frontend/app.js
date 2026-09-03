const PHASE_LIST = [
    { key: 'orchestrator', name: 'Orchestrator', desc: 'Classifies scenario' },
    { key: 'frame', name: 'Frame', desc: 'Brief framing & business goals' },
    { key: 'research', name: 'Research', desc: 'Market, competitive & user research' },
    { key: 'synthesis', name: 'Synthesis', desc: 'Personas, JTBD & journey maps' },
    { key: 'structure', name: 'Structure', desc: 'Task flows, IA, prioritization & metrics' },
    { key: 'design_system', name: 'Design System', desc: 'Visual design tokens & guidelines' },
];

let currentJobId = null;
let pollInterval = null;
let currentState = null;

const API_BASE = '/api';

// DOM Elements
const briefInput = document.getElementById('brief-input');
const btnGenerate = document.getElementById('btn-generate');
const btnStop = document.getElementById('btn-stop');
const historyList = document.getElementById('history-list');
const pipelineList = document.getElementById('pipeline-list');
const tabs = document.querySelectorAll('.tab');
const views = {
    report: document.getElementById('view-report'),
    hifi: document.getElementById('view-hifi'),
    inspector: document.getElementById('view-inspector')
};
const downloadBar = document.getElementById('download-bar');
const inspectorSelect = document.getElementById('inspector-select');
const inspectorJson = document.getElementById('inspector-json');

// Init
function init() {
    renderPipeline();
    document.getElementById('btn-collapse-history').addEventListener('click', () => {
        document.getElementById('sidebar-history').style.display = 'none';
        document.getElementById('btn-expand-history').style.display = 'block';
    });
    document.getElementById('btn-expand-history').addEventListener('click', () => {
        document.getElementById('sidebar-history').style.display = 'flex';
        document.getElementById('btn-expand-history').style.display = 'none';
    });

    // Hi-Fi: Generate All button
    const btnGenAll = document.getElementById('btn-generate-all-hifi');
    if (btnGenAll) {
        btnGenAll.addEventListener('click', async () => {
            if (!currentJobId) return;
            btnGenAll.disabled = true;
            btnGenAll.innerHTML = 'Generating...';
            try {
                await fetch(`${API_BASE}/hifi/${currentJobId}`, { method: 'POST' });
                startPolling();
            } catch (e) {
                console.error(e);
                btnGenAll.innerHTML = 'Generate All Screens';
                btnGenAll.disabled = false;
            }
        });
    }

    // Download tokens
    const btnTokensJson = document.getElementById('btn-dl-tokens-json');
    if (btnTokensJson) {
        btnTokensJson.addEventListener('click', () => {
            if (currentJobId) window.open(`${API_BASE}/hifi/${currentJobId}/design-tokens.json`);
        });
    }
    const btnTokensCss = document.getElementById('btn-dl-tokens-css');
    if (btnTokensCss) {
        btnTokensCss.addEventListener('click', () => {
            if (!currentState?.design_system?.payload) return;
            const ds = currentState.design_system.payload;
            let css = `:root {\n`;
            css += `  /* Design System: ${ds.tone} */\n`;
            css += `  --ds-color: ${ds.tokens.color};\n`;
            css += `  --ds-font-family: ${ds.tokens.typography.font_family};\n`;
            css += `  --ds-font-scale: ${ds.tokens.typography.scale};\n`;
            css += `  --ds-spacing: ${ds.tokens.spacing};\n`;
            css += `  --ds-radius: ${ds.tokens.radius};\n`;
            css += `  --ds-elevation: ${ds.tokens.elevation};\n`;
            css += `  --ds-density: ${ds.tokens.density};\n`;
            css += `}`;
            const blob = new Blob([css], { type: 'text/css' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'design-tokens.css';
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    populateInspectorSelect();
    loadHistory();

    btnGenerate.addEventListener('click', startGeneration);
    btnStop.addEventListener('click', stopGeneration);

    tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    inspectorSelect.addEventListener('change', updateInspector);

    document.getElementById('btn-dl-md').addEventListener('click', () => {
        if (currentJobId) window.open(`${API_BASE}/report/${currentJobId}.md`);
    });
    document.getElementById('btn-dl-pdf').addEventListener('click', () => {
        if (currentJobId) window.open(`${API_BASE}/report/${currentJobId}.html`);
    });
    document.getElementById('btn-dl-json').addEventListener('click', () => {
        if (currentState) {
            const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(currentState, null, 2));
            const a = document.createElement('a');
            a.setAttribute('href', dataStr);
            a.setAttribute('download', `ux-state-${currentJobId.substring(0, 8)}.json`);
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
    });
}

function renderPipeline(activeKey = null, isDone = false) {
    pipelineList.innerHTML = '';
    
    // Infer running phase: the first one that is pending
    let inferredRunningKey = activeKey;
    if (!inferredRunningKey && currentState && !isDone) {
        for (const phase of PHASE_LIST) {
            if (currentState[phase.key]?.status === 'pending') {
                inferredRunningKey = phase.key;
                break;
            }
        }
    }

    PHASE_LIST.forEach(phase => {
        let status = currentState ? currentState[phase.key]?.status || 'pending' : 'pending';
        
        // If this is the inferred running phase, pretend it's running for the UI
        if (status === 'pending' && phase.key === inferredRunningKey) {
            status = 'running';
        }

        let icon = '○';
        if (status === 'running') icon = '<div class="spinner"></div>';
        else if (status === 'success') icon = '✓';
        else if (status === 'degraded') icon = '⚠';
        else if (status === 'skipped') icon = '⏭';
        else if (status === 'error') icon = '✗';

        const el = document.createElement('div');
        el.className = `agent-card status-${status} ${inferredRunningKey === phase.key ? 'active' : ''}`;
        el.innerHTML = `
            <div class="agent-status-icon">${icon}</div>
            <div class="agent-info">
                <div class="agent-name">${phase.name}</div>
                <div class="agent-desc">${phase.desc}</div>
            </div>
        `;

        if (status === 'degraded' || status === 'error') {
            const errMsg = currentState[phase.key]?.error_message || '';
            if (errMsg) {
                el.innerHTML += `<div style="color: var(--error); font-size: 0.75rem; margin-top: 4px;">Error: ${errMsg}</div>`;
            }
        }
        pipelineList.appendChild(el);
    });
}

function populateInspectorSelect() {
    inspectorSelect.innerHTML = '<option value="all">Full State</option>';
    PHASE_LIST.forEach(p => {
        inspectorSelect.innerHTML += `<option value="${p.key}">${p.name}</option>`;
    });
    inspectorSelect.innerHTML += '<option value="hifi_screens">Hi-Fi Screens</option>';
}

function switchTab(tabId) {
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add('active');

    Object.values(views).forEach(v => v.style.display = 'none');
    views[tabId].style.display = 'block';

    if (tabId === 'inspector') updateInspector();
    if (tabId === 'hifi') renderHiFiView();
}

async function loadHistory() {
    try {
        const res = await fetch(`${API_BASE}/history`);
        const history = await res.json();
        historyList.innerHTML = '';
        history.forEach(item => {
            const el = document.createElement('div');
            el.className = `history-item ${item.job_id === currentJobId ? 'active' : ''}`;
            el.innerHTML = `
                <div class="history-item-id">${item.job_id.substring(0, 8)}</div>
                <div>${item.brief}</div>
            `;
            el.addEventListener('click', () => loadJob(item.job_id));
            historyList.appendChild(el);
        });
    } catch (e) {
        console.error('Failed to load history', e);
    }
}

async function startGeneration() {
    const brief = briefInput.value.trim();
    if (!brief) return alert('Enter a brief');

    btnGenerate.style.display = 'none';
    btnStop.style.display = 'block';
    briefInput.disabled = true;
    currentState = null;

    try {
        const res = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief })
        });
        const data = await res.json();
        currentJobId = data.job_id;
        loadHistory();
        startPolling();
    } catch (e) {
        console.error('Start failed', e);
        resetUI();
    }
}

async function stopGeneration() {
    if (!currentJobId) return;
    try {
        await fetch(`${API_BASE}/stop/${currentJobId}`, { method: 'POST' });
        btnStop.innerHTML = 'Stopping...';
        btnStop.disabled = true;
    } catch (e) {
        console.error(e);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollStatus, 2000);
    pollStatus();
}

async function pollStatus() {
    if (!currentJobId) return;
    try {
        const res = await fetch(`${API_BASE}/status/${currentJobId}`);
        const data = await res.json();

        currentState = data.state;

        let activeKey = null;
        for (const phase of PHASE_LIST) {
            if (currentState[phase.key]?.status === 'running') {
                activeKey = phase.key;
                break;
            }
        }

        renderPipeline(activeKey, data.is_done);

        updateViews();

        if (data.is_done) {
            clearInterval(pollInterval);
            pollInterval = null;
            resetUI();
            switchTab('report');
        }
    } catch (e) {
        console.error(e);
    }
}

function loadJob(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    currentJobId = jobId;
    loadHistory();

    fetch(`${API_BASE}/status/${jobId}`)
        .then(res => res.json())
        .then(data => {
            currentState = data.state;
            briefInput.value = currentState.brief;
            renderPipeline(null, data.is_done);
            updateViews();
            downloadBar.style.display = 'flex';
        });
}

function resetUI() {
    btnGenerate.style.display = 'block';
    btnStop.style.display = 'none';
    btnStop.innerHTML = 'Stop';
    btnStop.disabled = false;
    briefInput.disabled = false;
    downloadBar.style.display = 'flex';
}

function updateViews() {
    if (!currentState) return;
    renderReportView();
    renderHiFiView();
    if (views.inspector.style.display !== 'none') updateInspector();
}

function updateInspector() {
    if (!currentState) return;
    const key = inspectorSelect.value;
    const data = key === 'all' ? currentState : currentState[key];
    inspectorJson.textContent = JSON.stringify(data, null, 2);
}

function renderReportView() {
    let html = `<h1>UX POC Report</h1><p><strong>Brief:</strong> ${currentState.brief}</p>`;

    // Frame
    const f = currentState.frame;
    if (f && f.status === 'success' && f.payload) {
        const p = f.payload;
        html += `<div class="report-section"><h2>1. Frame & Business Goals</h2>
            <h3>Problem Statement</h3><p>${p.problem_statement || ''}</p>`;
        if (p.assumptions) html += `<h3>Assumptions</h3><ul>${p.assumptions.map(a => `<li>${a}</li>`).join('')}</ul>`;
        if (p.success_definition) html += `<h3>Success Definition</h3><p>${p.success_definition}</p>`;
        if (p.stakeholder_map) {
            html += `<h3>Stakeholder Map</h3><table><tr><th>Role</th><th>Interest</th><th>Assumed?</th></tr>
                ${p.stakeholder_map.map(s => `<tr><td>${s.role}</td><td>${s.likely_interest}</td><td>${s.assumption ? 'Yes' : 'No'}</td></tr>`).join('')}</table>`;
        }
        html += `</div>`;
    }

    // Research
    const r = currentState.research;
    if (r && r.status === 'success' && r.payload) {
        const p = r.payload;
        html += `<div class="report-section"><h2>2. Research</h2>`;
        if (p.market_overview) html += `<h3>Market</h3><p>${p.market_overview}</p>`;
        if (p.gaps) html += `<h3>Gaps</h3><ul>${p.gaps.map(g => `<li><strong>${g.gap}</strong>: ${g.evidence}</li>`).join('')}</ul>`;
        if (p.feature_matrix) {
            html += `<h3>Feature Matrix</h3><table><tr><th>Feature</th><th>Competitors...</th></tr>
                ${p.feature_matrix.map(fm => `<tr><td>${fm.feature}</td><td>${JSON.stringify(fm.by_competitor)}</td></tr>`).join('')}</table>`;
        }
        html += `</div>`;
    }

    // Synthesis
    const s = currentState.synthesis;
    if (s && s.status === 'success' && s.payload) {
        const p = s.payload;
        html += `<div class="report-section"><h2>3. Synthesis</h2>`;
        if (p.personas) {
            p.personas.forEach(per => {
                html += `<div class="metric-card"><h4>${per.name} (${per.role})</h4><p>${per.context}</p></div>`;
            });
        }
        if (p.jobs) html += `<h3>Jobs to be Done</h3><ul>${p.jobs.map(j => `<li>[${j.priority}] ${j.job_statement}</li>`).join('')}</ul>`;
        html += `</div>`;
    }

    // Structure
    const st = currentState.structure;
    if (st && st.status === 'success' && st.payload) {
        const p = st.payload;
        html += `<div class="report-section"><h2>4. Structure</h2>`;
        if (p.sitemap) html += `<h3>Sitemap</h3><ul>${p.sitemap.map(n => `<li><strong>${n.node}</strong> -> ${n.children.join(', ')}</li>`).join('')}</ul>`;
        if (p.backlog) {
            html += `<h3>Backlog</h3><table><tr><th>Item</th><th>MoSCoW</th><th>Score</th></tr>
                ${p.backlog.map(b => `<tr><td>${b.item}</td><td>${b.moscow}</td><td>${b.rice?.score || ''}</td></tr>`).join('')}</table>`;
        }
        html += `</div>`;
    }

    // Design System summary in report
    const ds = currentState.design_system;
    if (ds && ds.status === 'success' && ds.payload) {
        html += `<div class="report-section"><h2>5. Design System</h2>`;
        html += `<p><strong>Tone:</strong> ${ds.payload.tone}</p>`;
        html += `<p><strong>Rationale:</strong> ${ds.payload.design_rationale}</p>`;
        if (ds.payload.provisional) html += `<p><em>⚠ Provisional — no brand guidelines provided</em></p>`;
        html += `<div class="ds-token-grid">`;
        html += `<div class="ds-token"><div class="ds-token-label">Color</div><div class="ds-token-value">${ds.payload.tokens.color}</div></div>`;
        html += `<div class="ds-token"><div class="ds-token-label">Font</div><div class="ds-token-value">${ds.payload.tokens.typography.font_family}</div></div>`;
        html += `<div class="ds-token"><div class="ds-token-label">Spacing</div><div class="ds-token-value">${ds.payload.tokens.spacing}</div></div>`;
        html += `<div class="ds-token"><div class="ds-token-label">Radius</div><div class="ds-token-value">${ds.payload.tokens.radius}</div></div>`;
        html += `<div class="ds-token"><div class="ds-token-label">Density</div><div class="ds-token-value">${ds.payload.tokens.density}</div></div>`;
        html += `</div></div>`;
    }

    views.report.innerHTML = html;
}

// ---- Hi-Fi Screens ----

async function renderHiFiView() {
    const btnGenAll = document.getElementById('btn-generate-all-hifi');
    const statusText = document.getElementById('hifi-status-text');
    const dsSummary = document.getElementById('design-system-summary');
    const dsContent = document.getElementById('design-system-content');
    const screenListEl = document.getElementById('hifi-screen-list');
    const btnTokensJson = document.getElementById('btn-dl-tokens-json');
    const btnTokensCss = document.getElementById('btn-dl-tokens-css');

    if (!currentState || !currentJobId) return;

    // Check if design system is ready
    const ds = currentState.design_system;
    if (!ds || ds.status !== 'success' || !ds.payload) {
        if (btnGenAll) btnGenAll.disabled = true;
        if (statusText) statusText.innerText = ds?.status === 'running' ? 'Design system generating...' : 'Requires completed report';
        if (dsSummary) dsSummary.style.display = 'none';
        if (screenListEl) screenListEl.innerHTML = '';
        if (btnTokensJson) btnTokensJson.disabled = true;
        if (btnTokensCss) btnTokensCss.disabled = true;
        return;
    }

    // Show design system summary
    if (dsSummary && dsContent) {
        dsSummary.style.display = 'block';
        dsContent.innerHTML = `
            <div class="ds-token-grid">
                <div class="ds-token"><div class="ds-token-label">Tone</div><div class="ds-token-value">${ds.payload.tone}</div></div>
                <div class="ds-token"><div class="ds-token-label">Color</div><div class="ds-token-value">${ds.payload.tokens.color}</div></div>
                <div class="ds-token"><div class="ds-token-label">Font</div><div class="ds-token-value">${ds.payload.tokens.typography.font_family}</div></div>
                <div class="ds-token"><div class="ds-token-label">Spacing</div><div class="ds-token-value">${ds.payload.tokens.spacing}</div></div>
                <div class="ds-token"><div class="ds-token-label">Radius</div><div class="ds-token-value">${ds.payload.tokens.radius}</div></div>
                <div class="ds-token"><div class="ds-token-label">Density</div><div class="ds-token-value">${ds.payload.tokens.density}</div></div>
                <div class="ds-token"><div class="ds-token-label">Contrast</div><div class="ds-token-value">${ds.payload.accessibility.min_contrast}</div></div>
                <div class="ds-token"><div class="ds-token-label">Tap Target</div><div class="ds-token-value">${ds.payload.accessibility.min_tap_target_px}px</div></div>
            </div>
            ${ds.payload.provisional ? '<p style="margin-top:8px;font-size:0.8rem;color:var(--warning);">⚠ Provisional design — no brand guidelines provided</p>' : ''}
        `;
    }

    // Enable download buttons
    if (btnTokensJson) btnTokensJson.disabled = false;
    if (btnTokensCss) btnTokensCss.disabled = false;

    // Fetch screen list from API
    try {
        const res = await fetch(`${API_BASE}/hifi/${currentJobId}/screens`);
        const data = await res.json();
        const screens = data.screens || [];

        if (btnGenAll) {
            btnGenAll.disabled = false;
            btnGenAll.innerHTML = 'Generate All Screens';
        }
        if (statusText) statusText.innerText = `${screens.length} screens derived from report`;

        let html = '';
        screens.forEach(screen => {
            const screenState = currentState.hifi_screens?.[screen.ref];
            const status = screenState?.status || 'pending';

            html += `<div class="hifi-card" id="hifi-card-${CSS.escape(screen.ref)}">`;
            html += `<div class="hifi-card-header">`;
            html += `<div><div class="hifi-card-title">${screen.ref}</div><div class="hifi-card-meta">${screen.flow ? 'Flow: ' + screen.flow : 'From sitemap'}</div></div>`;
            html += `<div class="hifi-card-actions">`;
            html += `<select onchange="window._hifiDeviceChanged('${screen.ref}', this.value)">`;
            html += `<option value="desktop" ${screen.device === 'desktop' ? 'selected' : ''}>🖥 Desktop</option>`;
            html += `<option value="mobile" ${screen.device === 'mobile' ? 'selected' : ''}>📱 Mobile</option>`;
            html += `</select>`;

            if (status === 'pending') {
                html += `<button onclick="window._generateOneHifi('${screen.ref}', '${screen.device}')">Generate</button>`;
            } else if (status === 'running') {
                html += `<button disabled><div class="spinner" style="width:12px;height:12px;border-width:1px;"></div> Generating...</button>`;
            } else if (status === 'success') {
                html += `<button onclick="window._generateOneHifi('${screen.ref}', '${screen.device}')">Regenerate</button>`;
                html += `<button onclick="window.open('${API_BASE}/hifi/${currentJobId}/${encodeURIComponent(screen.ref)}/html')">⬇ HTML</button>`;
            } else if (status === 'degraded') {
                html += `<button onclick="window._generateOneHifi('${screen.ref}', '${screen.device}')">Retry</button>`;
            }

            html += `</div></div>`;

            // Body
            if (status === 'running') {
                html += `<div class="hifi-placeholder"><div class="spinner"></div><br>Generating hi-fi screen...</div>`;
            } else if (status === 'success' && screenState.payload) {
                // Render HTML in sandboxed iframe
                const escapedHtml = screenState.payload.html.replace(/'/g, '\'');
                html += `<div class="hifi-iframe-wrapper"><iframe sandbox="allow-same-origin" srcdoc='${screenState.payload.html.replace(/'/g, "&#39;")}'></iframe></div>`;
                if (screenState.payload.design_notes) {
                    html += `<div class="hifi-notes">📝 ${screenState.payload.design_notes}</div>`;
                }
            } else if (status === 'degraded') {
                html += `<div class="hifi-error">⚠ Failed: ${screenState.error_message || 'Unknown error'}</div>`;
            } else {
                html += `<div class="hifi-placeholder">Click Generate to create this screen</div>`;
            }

            html += `</div>`;
        });

        if (screenListEl) screenListEl.innerHTML = html;
    } catch (e) {
        console.error('Failed to load screen list', e);
    }
}

// Global handlers for hi-fi screen generation
window._hifiDeviceChanged = function(screenRef, device) {
    // Store preference — will be used on next generate click
    const el = document.querySelector(`#hifi-card-${CSS.escape(screenRef)} .hifi-card-actions button:first-of-type`);
    if (el && !el.disabled) {
        el.setAttribute('onclick', `window._generateOneHifi('${screenRef}', '${device}')`);
    }
};

window._generateOneHifi = async function(screenRef, device) {
    if (!currentJobId) return;
    try {
        await fetch(`${API_BASE}/hifi/${currentJobId}/${encodeURIComponent(screenRef)}?device=${device}`, { method: 'POST' });
        startPolling();
    } catch (e) {
        console.error(e);
    }
};

init();
