const API_BASE = "/api";

const AGENT_LIST = [
    { key: "orchestrator", name: "Orchestrator", desc: "Classifies scenario", num: "00" },
    { key: "a01_brief_framing", name: "Brief Framing", desc: "Structures brief", num: "01" },
    { key: "a02_business_goals", name: "Business Goals", desc: "Extracts goals", num: "02" },
    { key: "a03_domain_market", name: "Domain Research", desc: "Market trends", num: "03" },
    { key: "a04_competitive", name: "Competitive Analysis", desc: "Feature matrix", num: "04" },
    { key: "a05_secondary_research", name: "User Research", desc: "Pain themes", num: "05" },
    { key: "a06_ux_audit", name: "UX Audit", desc: "Heuristic audit", num: "06" },
    { key: "a07_persona", name: "Persona Building", desc: "User personas", num: "07" },
    { key: "a08_jtbd", name: "Jobs to Be Done", desc: "User jobs", num: "08" },
    { key: "a09_journey", name: "Journey Mapping", desc: "Journey maps", num: "09" },
    { key: "a10_task_flows", name: "Key Task Flows", desc: "Flow diagrams", num: "10" },
    { key: "a11_ia", name: "Info Architecture", desc: "Sitemap", num: "11" },
    { key: "a12_prioritization", name: "Feature Priority", desc: "Prioritization", num: "12" },
    { key: "a13_success_matrix", name: "Success Matrix", desc: "KPIs", num: "13" },
    { key: "a14_compiler", name: "Report Compiler", desc: "Final synthesis", num: "14" },
    { key: "a15_wireframes", name: "Wireframe UI", desc: "Generates HTML mockups", num: "15" }
];

let currentJobId = null;
let pollInterval = null;
let latestState = null;
let selectedAgentKey = null;
let currentTab = 'report'; // 'report', 'wireframes', 'agent'
const alertedAgents = new Set();

// ── Startup ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    fetchHistory();
    renderPipeline({}, false);
});

// ── Generate ──────────────────────────────────────────────
document.getElementById('submitBtn').addEventListener('click', async () => {
    const brief = document.getElementById('briefInput').value.trim();
    if (!brief) return;

    setLoadingUI();
    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief })
        });
        const data = await response.json();
        currentJobId = data.job_id;
        pollInterval = setInterval(pollStatus, 2000);
        setTimeout(fetchHistory, 3000); // refresh history
    } catch (err) {
        showErrorUI("Failed to connect to backend server.");
    }
});

// ── Stop Execution ────────────────────────────────────────
document.getElementById('stopBtn').addEventListener('click', async () => {
    if (!currentJobId) return;
    try {
        await fetch(`${API_BASE}/stop/${currentJobId}`, { method: 'POST' });
        document.getElementById('stopBtn').innerText = "Stopping...";
    } catch (err) { console.error(err); }
});

// ── Polling ───────────────────────────────────────────────
async function pollStatus() {
    if (!currentJobId) return;
    try {
        const response = await fetch(`${API_BASE}/status/${currentJobId}`);
        const data = await response.json();
        latestState = data.state;
        
        renderPipeline(latestState, data.is_done);
        checkDegradations(latestState);

        // Update UI based on active tab
        if (currentTab === 'agent' && selectedAgentKey) {
            const agentMeta = AGENT_LIST.find(a => a.key === selectedAgentKey);
            showAgentOutput(agentMeta, latestState[selectedAgentKey] || { status: 'pending' });
        } else if (currentTab === 'report' && data.is_done) {
            renderFullReport(latestState);
        } else if (currentTab === 'wireframes') {
            renderWireframes(latestState);
        }

        if (data.is_done) {
            clearInterval(pollInterval);
            resetLoadingUI();
            
            // Check if wireframes button should show
            document.getElementById('tabBar').style.display = 'flex';
            if (latestState.a15_wireframes && latestState.a15_wireframes.status !== 'pending') {
                document.getElementById('tabWireframes').style.display = 'block';
            }
            
            if (currentTab === 'report') renderFullReport(latestState);
        }
    } catch (err) { console.error(err); }
}

// ── History ───────────────────────────────────────────────
async function fetchHistory() {
    try {
        const response = await fetch(`${API_BASE}/history`);
        const history = await response.json();
        const hl = document.getElementById('historyList');
        hl.innerHTML = '';
        history.forEach(h => {
            const el = document.createElement('div');
            el.className = `history-item ${h.job_id === currentJobId ? 'active' : ''}`;
            el.innerHTML = `<p>${esc(h.brief)}</p>`;
            el.onclick = () => loadJob(h.job_id);
            hl.appendChild(el);
        });
    } catch (err) { console.error("History fetch failed"); }
}

async function loadJob(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    currentJobId = jobId;
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    setLoadingUI();
    document.getElementById('stopBtn').style.display = 'none'; // Past job, no stop needed
    await pollStatus(); // single poll
    fetchHistory();
}

// ── UI States ─────────────────────────────────────────────
function setLoadingUI() {
    document.getElementById('submitBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = 'flex';
    document.getElementById('stopBtn').innerText = '⏹';
    document.getElementById('progressSection').classList.add('active');
    document.getElementById('statusDot').className = 'status-dot running';
    document.getElementById('statusLabel').innerText = 'Running';
    document.getElementById('tabBar').style.display = 'none';
    currentTab = 'report'; selectedAgentKey = null; alertedAgents.clear();
    document.getElementById('outputViewer').innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚡</div><p>Pipeline running...</p></div>`;
    renderPipeline({}, false);
}

function resetLoadingUI() {
    document.getElementById('submitBtn').style.display = 'flex';
    document.getElementById('submitBtn').disabled = false;
    document.getElementById('stopBtn').style.display = 'none';
    document.getElementById('progressBar').style.width = '100%';
    document.getElementById('progressPercent').innerText = '100%';
    document.getElementById('currentAgentLabel').innerText = latestState.cancelled ? 'Cancelled' : 'Complete ✓';
    document.getElementById('statusDot').className = 'status-dot idle';
    document.getElementById('statusLabel').innerText = latestState.cancelled ? 'Cancelled' : 'Complete';
}

function showErrorUI(msg) {
    document.getElementById('submitBtn').disabled = false;
    document.getElementById('outputViewer').innerHTML = `<div class="error-block">${msg}</div>`;
}

// ── Tabs ──────────────────────────────────────────────────
function switchTab(tab) {
    currentTab = tab;
    document.getElementById('tabReport').classList.toggle('active', tab === 'report');
    document.getElementById('tabWireframes').classList.toggle('active', tab === 'wireframes');
    document.getElementById('tabAgent').classList.toggle('active', tab === 'agent');
    
    if (tab === 'report') renderFullReport(latestState);
    else if (tab === 'wireframes') renderWireframes(latestState);
    else {
        if (selectedAgentKey) {
            const agentMeta = AGENT_LIST.find(a => a.key === selectedAgentKey);
            showAgentOutput(agentMeta, latestState[selectedAgentKey] || { status: 'pending' });
        } else {
            document.getElementById('outputViewer').innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔍</div><p>Select an agent from the sidebar.</p></div>`;
        }
    }
}
window.switchTab = switchTab;

// ── Generate Wireframes ───────────────────────────────────
window.triggerWireframes = async function() {
    if (!currentJobId) return;
    document.getElementById('tabBar').style.display = 'flex';
    document.getElementById('tabWireframes').style.display = 'block';
    switchTab('wireframes');
    
    try {
        await fetch(`${API_BASE}/generate_wireframes/${currentJobId}`, { method: 'POST' });
        pollInterval = setInterval(pollStatus, 2000);
    } catch (e) { console.error(e); }
};

function renderWireframes(state) {
    const viewer = document.getElementById('outputViewer');
    document.getElementById('outputTitle').innerText = 'Wireframes Mockup';
    document.getElementById('outputSubtitle').innerText = 'Generated HTML/Tailwind Screens';
    
    const wf = state.a15_wireframes;
    if (!wf || wf.status === 'pending') {
        viewer.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🎨</div><p>Click "Generate Wireframes" in the report to render UI screens.</p></div>`;
        return;
    }
    if (wf.status === 'working') {
        viewer.innerHTML = `<div class="empty-state"><div class="empty-state-icon" style="animation: pulse-icon 1s infinite">🎨</div><p>Agent 15 is writing HTML/Tailwind code for 5 screens...</p></div>`;
        return;
    }
    if (wf.status === 'degraded' || wf.error_message) {
        viewer.innerHTML = `<div class="error-block">${wf.error_message || wf.fallback_instruction}</div>`;
        return;
    }

    let h = '<div class="fade-in">';
    wf.payload.screens.forEach(s => {
        h += `<div class="wireframe-container">
            <div class="wireframe-header">
                <h4>${esc(s.screen_name)}</h4>
                <p>${esc(s.description)}</p>
            </div>
            <iframe class="wireframe-frame" srcdoc="${escAttr(s.html_tailwind_code)}"></iframe>
        </div>`;
    });
    h += '</div>';
    viewer.innerHTML = h;
}

// ── Export PDF ────────────────────────────────────────────
window.exportPDF = function() {
    const element = document.getElementById('pdf-report-content');
    if (!element) return;
    
    // Temporarily hide buttons for print
    const dlBar = element.querySelector('.download-bar');
    if (dlBar) dlBar.style.display = 'none';

    html2pdf().set({
        margin: 10,
        filename: 'ux-poc-report.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    }).from(element).save().then(() => {
        if (dlBar) dlBar.style.display = 'flex';
    });
};

// ── Degradations & Pipeline (same as before mostly) ───────
function checkDegradations(state) {
    AGENT_LIST.forEach(agent => {
        const d = state[agent.key];
        if (d && d.status === 'degraded' && !alertedAgents.has(agent.key)) {
            alertedAgents.add(agent.key);
            document.getElementById('modalFallbackText').innerText = `${agent.name}: ${d.fallback_instruction || d.error_message}`;
            document.getElementById('interventionModal').style.display = 'flex';
        }
    });
}

function renderPipeline(state, isDone) {
    const pipelineDiv = document.getElementById('pipeline');
    pipelineDiv.innerHTML = '';
    let completedCount = 0, currentlyWorkingIndex = -1;

    // We don't count a15 in the main progress bar as it's optional
    const coreAgents = AGENT_LIST.slice(0, 15);
    
    coreAgents.forEach((agent, i) => {
        const d = state[agent.key] || { status: 'pending' };
        if (d.status !== 'pending') completedCount++;
        else if (currentlyWorkingIndex === -1 && !isDone && !state.cancelled) currentlyWorkingIndex = i;
    });

    const pct = Math.round((completedCount / coreAgents.length) * 100);
    if (!isDone && !state.cancelled) {
        document.getElementById('progressBar').style.width = `${pct}%`;
        document.getElementById('progressPercent').innerText = `${pct}%`;
        if (currentlyWorkingIndex !== -1) document.getElementById('currentAgentLabel').innerText = coreAgents[currentlyWorkingIndex].name;
    }

    AGENT_LIST.forEach((agent, i) => {
        const d = state[agent.key] || { status: 'pending' };
        let rs = d.status;
        if (i === currentlyWorkingIndex) rs = 'working';
        if (agent.key === 'a15_wireframes' && rs === 'working') rs = 'working';

        const card = document.createElement('div');
        card.className = `agent-card${selectedAgentKey === agent.key ? ' selected' : ''}`;
        card.onclick = () => {
            selectedAgentKey = agent.key;
            currentTab = 'agent';
            if (document.getElementById('tabBar').style.display !== 'none') switchTab('agent');
            showAgentOutput(agent, d);
            document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
        };
        card.innerHTML = `
            <div class="agent-icon ${rs}">${getIcon(rs)}</div>
            <div class="agent-info"><div class="agent-name">${agent.name}</div><div class="agent-status-text">${rs === 'working' ? 'Running...' : rs}</div></div>
        `;
        pipelineDiv.appendChild(card);
    });
}
function getIcon(s) { return { success:'✓', degraded:'!', skipped:'—', working:'◉' }[s] || '○'; }

function showAgentOutput(agent, d) {
    const viewer = document.getElementById('outputViewer');
    document.getElementById('outputTitle').innerText = agent.name;
    document.getElementById('outputSubtitle').innerText = agent.desc;
    if (d.status === 'pending') { viewer.innerHTML = `<div class="empty-state fade-in"><div class="empty-state-icon">⏳</div><p>Pending.</p></div>`; return; }
    if (d.status === 'skipped') { viewer.innerHTML = `<div class="empty-state fade-in"><div class="empty-state-icon">⏭️</div><p>Skipped.</p></div>`; return; }
    
    let h = '<div class="fade-in">';
    if (d.status === 'degraded') h += `<div class="degradation-block"><p><strong>Action:</strong> ${d.fallback_instruction}</p></div>`;
    if (d.payload && d.payload.thinking_process) h += `<div class="thinking-block"><h4>🧠 Reasoning</h4><p>${esc(d.payload.thinking_process)}</p></div>`;
    if (d.payload) {
        const dp = { ...d.payload }; delete dp.thinking_process;
        h += `<pre>${esc(JSON.stringify(dp, null, 2))}</pre>`;
    }
    h += '</div>';
    viewer.innerHTML = h;
}

// ── Full Report ───────────────────────────────────────────
function renderFullReport(state) {
    if (!state) return;
    document.getElementById('outputTitle').innerText = 'Final UX Report';
    document.getElementById('outputSubtitle').innerText = 'Consolidated AI Findings';
    
    if (state.cancelled) {
        document.getElementById('outputViewer').innerHTML = `<div class="error-block">Job cancelled by user.</div>`;
        return;
    }

    const a14 = state.a14_compiler;
    if (!a14 || a14.status === 'pending') {
        document.getElementById('outputViewer').innerHTML = `<div class="empty-state"><div class="empty-state-icon">⏳</div><p>Compiling report...</p></div>`;
        return;
    }

    let h = '<div id="pdf-report-content" class="report fade-in">';
    
    if (a14.payload) {
        h += `<div class="report-header">
            <h2>Executive Summary</h2>
            <p>${esc(a14.payload.executive_summary)}</p>
        </div>`;
        h += listCard('Key Findings', a14.payload.key_findings);
        h += listCard('Strategic Recommendations', a14.payload.strategic_recommendations);
        h += listCard('Next Steps', a14.payload.next_steps_for_design_team);
    } else {
        h += `<div class="error-block">${a14.fallback_instruction}</div>`;
    }

    h += `<div class="download-bar">
        <button class="btn-success" onclick="triggerWireframes()">🎨 Proceed to Wireframes</button>
        <button class="btn-secondary" onclick="exportPDF()">📄 Download PDF</button>
        <button class="btn-secondary" onclick="window.downloadJSON()">📥 Download JSON</button>
    </div>`;

    h += '</div>';
    document.getElementById('outputViewer').innerHTML = h;
}

function listCard(title, arr) {
    if (!arr || !arr.length) return '';
    let h = `<div class="report-card"><h5>${title}</h5><ul>`;
    arr.forEach(i => h += `<li>${esc(i)}</li>`);
    return h + '</ul></div>';
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
}

function escAttr(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

window.downloadJSON = function() {
    const blob = new Blob([JSON.stringify(latestState, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'ux-poc.json'; a.click();
}
