const PHASE_LIST = [
    { key: 'orchestrator', name: 'Orchestrator', desc: 'Classifies scenario' },
    { key: 'frame', name: 'Frame', desc: 'Brief framing & business goals' },
    { key: 'research', name: 'Research', desc: 'Market, competitive & user research' },
    { key: 'synthesis', name: 'Synthesis', desc: 'Personas, JTBD & journey maps' },
    { key: 'structure', name: 'Structure', desc: 'Task flows, IA, prioritization & metrics' },
    { key: 'wireframe', name: 'Wireframe', desc: 'Grey-box screen layouts' },
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
    wireframes: document.getElementById('view-wireframes'),
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
    
    const btnGenWf = document.getElementById('btn-generate-wireframes');
    if(btnGenWf) {
        btnGenWf.addEventListener('click', async () => {
            if(!currentJobId) return;
            btnGenWf.disabled = true;
            btnGenWf.innerHTML = "Generating...";
            try {
                await fetch(`${API_BASE}/generate_wireframes/${currentJobId}`, { method: 'POST' });
                startPolling(); // Restart polling to track wireframes
            } catch(e) {
                console.error(e);
                btnGenWf.innerHTML = "Generate Wireframes";
                btnGenWf.disabled = false;
            }
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
        if(currentJobId) window.open(`${API_BASE}/report/${currentJobId}.md`);
    });
    document.getElementById('btn-dl-pdf').addEventListener('click', () => {
        if(currentJobId) window.open(`${API_BASE}/report/${currentJobId}.html`);
    });
    document.getElementById('btn-dl-json').addEventListener('click', () => {
        if(currentState) {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentState, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", `ux-state-${currentJobId.substring(0,8)}.json`);
            document.body.appendChild(downloadAnchorNode);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }
    });
}

function renderPipeline(activeKey = null) {
    pipelineList.innerHTML = '';
    PHASE_LIST.forEach(phase => {
        const status = currentState ? currentState[phase.key]?.status || 'pending' : 'pending';
        let icon = '○';
        if (status === 'running') icon = '<div class="spinner"></div>';
        else if (status === 'success') icon = '✓';
        else if (status === 'degraded') icon = '⚠';
        else if (status === 'skipped') icon = '⏭';
        else if (status === 'error') icon = '✗';
        
        const el = document.createElement('div');
        el.className = `agent-card status-${status} ${activeKey === phase.key ? 'active' : ''}`;
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
}

function switchTab(tabId) {
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add('active');
    
    Object.values(views).forEach(v => v.style.display = 'none');
    views[tabId].style.display = 'block';
    
    if (tabId === 'inspector') updateInspector();
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
        console.error("Failed to load history", e);
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
        console.error("Start failed", e);
        resetUI();
    }
}

async function stopGeneration() {
    if (!currentJobId) return;
    try {
        await fetch(`${API_BASE}/stop/${currentJobId}`, { method: 'POST' });
        btnStop.innerHTML = "Stopping...";
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
        
        // Find active phase
        let activeKey = null;
        for (const phase of PHASE_LIST) {
            if (currentState[phase.key]?.status === 'running') {
                activeKey = phase.key;
                break;
            }
        }
        
        renderPipeline(activeKey);
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
            renderPipeline();
            updateViews();
            downloadBar.style.display = 'flex';
        });
}

function resetUI() {
    btnGenerate.style.display = 'block';
    btnStop.style.display = 'none';
    btnStop.innerHTML = "Stop";
    btnStop.disabled = false;
    briefInput.disabled = false;
    downloadBar.style.display = 'flex';
}

function updateViews() {
    if (!currentState) return;
    renderReportView();
    renderWireframesView();
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
        
        if (p.assumptions) html += `<h3>Assumptions</h3><ul>${p.assumptions.map(a=>`<li>${a}</li>`).join('')}</ul>`;
        if (p.success_definition) html += `<h3>Success Definition</h3><p>${p.success_definition}</p>`;
        
        if (p.stakeholder_map) {
            html += `<h3>Stakeholder Map</h3><table><tr><th>Role</th><th>Interest</th><th>Assumed?</th></tr>
                ${p.stakeholder_map.map(s=>`<tr><td>${s.role}</td><td>${s.likely_interest}</td><td>${s.assumption?'Yes':'No'}</td></tr>`).join('')}</table>`;
        }
        html += `</div>`;
    }

    // Research
    const r = currentState.research;
    if (r && r.status === 'success' && r.payload) {
        const p = r.payload;
        html += `<div class="report-section"><h2>2. Research</h2>`;
        if (p.market_overview) html += `<h3>Market</h3><p>${p.market_overview}</p>`;
        if (p.gaps) html += `<h3>Gaps</h3><ul>${p.gaps.map(g=>`<li><strong>${g.gap}</strong>: ${g.evidence}</li>`).join('')}</ul>`;
        if (p.feature_matrix) {
            html += `<h3>Feature Matrix</h3><table><tr><th>Feature</th><th>Competitors...</th></tr>
                ${p.feature_matrix.map(fm=>`<tr><td>${fm.feature}</td><td>${JSON.stringify(fm.by_competitor)}</td></tr>`).join('')}</table>`;
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
        if (p.jobs) html += `<h3>Jobs to be Done</h3><ul>${p.jobs.map(j=>`<li>[${j.priority}] ${j.job_statement}</li>`).join('')}</ul>`;
        html += `</div>`;
    }

    // Structure
    const st = currentState.structure;
    if (st && st.status === 'success' && st.payload) {
        const p = st.payload;
        html += `<div class="report-section"><h2>4. Structure</h2>`;
        if (p.sitemap) html += `<h3>Sitemap</h3><ul>${p.sitemap.map(n=>`<li><strong>${n.node}</strong> -> ${n.children.join(', ')}</li>`).join('')}</ul>`;
        if (p.backlog) {
            html += `<h3>Backlog</h3><table><tr><th>Item</th><th>MoSCoW</th><th>Score</th></tr>
                ${p.backlog.map(b=>`<tr><td>${b.item}</td><td>${b.moscow}</td><td>${b.rice?.score||''}</td></tr>`).join('')}</table>`;
        }
        html += `</div>`;
    }

    views.report.innerHTML = html;
}


function renderWireframesView() {
    const container = document.getElementById('wireframes-container');
    const btnGenWf = document.getElementById('btn-generate-wireframes');
    const statusText = document.getElementById('wireframe-status-text');
    
    // Check if report is done
    if (!currentState || currentState.structure?.status !== 'success') {
        if(btnGenWf) btnGenWf.disabled = true;
        if(statusText) statusText.innerText = "Requires completed report";
        if(container) container.innerHTML = "";
        return;
    }
    
    // Check wireframe status
    const w = currentState.wireframe;
    if (!w || w.status === 'pending') {
        if(btnGenWf) {
            btnGenWf.disabled = false;
            btnGenWf.innerHTML = "Generate Wireframes";
        }
        if(statusText) statusText.innerText = "Ready to generate wireframes";
        if(container) container.innerHTML = "";
        return;
    }
    
    if (w.status === 'running') {
        if(btnGenWf) {
            btnGenWf.disabled = true;
            btnGenWf.innerHTML = "Generating...";
        }
        if(statusText) statusText.innerText = "Wireframes are generating...";
        if(container) container.innerHTML = `<div style="text-align: center; padding: 40px;"><div class="spinner"></div></div>`;
        return;
    }

    if (w.status === 'degraded' || w.status === 'error') {
        if(btnGenWf) {
            btnGenWf.disabled = false;
            btnGenWf.innerHTML = "Retry Wireframes";
        }
        if(statusText) statusText.innerText = `Failed: ${w.error_message || 'Unknown error'}`;
        if(container) container.innerHTML = "";
        return;
    }

    if(btnGenWf) btnGenWf.style.display = 'none';
    if(statusText) statusText.style.display = 'none';

    if (!w.payload || !w.payload.screens) {
        if(container) container.innerHTML = `<div style="color:var(--text-muted); padding: 40px; text-align: center;">No screens generated.</div>`;
        return;
    }

    let html = '';
    w.payload.screens.forEach(screen => {
        let hasSidebar = screen.regions.some(r => r.type === 'sidebar');
        let bodyClass = hasSidebar ? 'wf-body wf-has-sidebar' : 'wf-body';
        
        let screenHtml = `<div class="wf-screen">
            <div class="wf-screen-title">${screen.name} <span>${screen.route}</span></div>
            <div class="${bodyClass}">`;
            
        screen.regions.forEach(region => {
            screenHtml += `<div class="wf-region ${region.type}" data-type="${region.type}">
                <div class="wf-label">${region.label}</div>
                <ul class="wf-items">
                    ${region.items.map(item => `<li>${item}</li>`).join('')}
                </ul>
            </div>`;
        });
        
        screenHtml += `</div></div>`;
        html += screenHtml;
    });

    if(container) container.innerHTML = html;
}


init();
