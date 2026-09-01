const API_BASE = "/api";

const AGENT_LIST = [
    { key: "orchestrator", name: "Orchestrator", desc: "Classifies the brief into a scenario", num: "00" },
    { key: "a01_brief_framing", name: "Brief Framing", desc: "Structures the raw brief", num: "01" },
    { key: "a02_business_goals", name: "Business Goals", desc: "Extracts goals & stakeholder map", num: "02" },
    { key: "a03_domain_market", name: "Domain Research", desc: "Analyzes market trends & regulations", num: "03" },
    { key: "a04_competitive", name: "Competitive Analysis", desc: "Feature matrix & gap analysis", num: "04" },
    { key: "a05_secondary_research", name: "User Research", desc: "Secondary user pain themes", num: "05" },
    { key: "a06_ux_audit", name: "UX Audit", desc: "Heuristic audit of existing product", num: "06" },
    { key: "a07_persona", name: "Persona Building", desc: "Builds grounded user personas", num: "07" },
    { key: "a08_jtbd", name: "Jobs to Be Done", desc: "Maps user jobs & outcomes", num: "08" },
    { key: "a09_journey", name: "Journey Mapping", desc: "End-to-end user journey maps", num: "09" },
    { key: "a10_task_flows", name: "Key Task Flows", desc: "Critical task flow diagrams", num: "10" },
    { key: "a11_ia", name: "Info Architecture", desc: "Sitemap & navigation structure", num: "11" },
    { key: "a12_prioritization", name: "Feature Priority", desc: "MoSCoW & RICE prioritization", num: "12" },
    { key: "a13_success_matrix", name: "Success Matrix", desc: "KPIs & measurement framework", num: "13" }
];

let currentJobId = null;
let pollInterval = null;
let latestState = null;
let selectedAgentKey = null;
let currentTab = 'report'; // 'report' or 'agent'
const alertedAgents = new Set();

// ── Submit ────────────────────────────────────────────────
document.getElementById('submitBtn').addEventListener('click', async () => {
    const brief = document.getElementById('briefInput').value.trim();
    if (!brief) { document.getElementById('briefInput').focus(); return; }

    document.getElementById('submitBtn').disabled = true;
    document.getElementById('progressSection').classList.add('active');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressPercent').innerText = '0%';
    document.getElementById('currentAgentLabel').innerText = 'Starting...';
    document.getElementById('statusDot').className = 'status-dot running';
    document.getElementById('statusLabel').innerText = 'Running';
    document.getElementById('tabBar').style.display = 'none';
    selectedAgentKey = null;
    currentTab = 'report';
    alertedAgents.clear();

    document.getElementById('outputTitle').innerText = 'Output Inspector';
    document.getElementById('outputSubtitle').innerText = 'Pipeline is running...';
    document.getElementById('outputViewer').innerHTML = `
        <div class="empty-state"><div class="empty-state-icon">⚡</div>
        <p>The pipeline is running. Click on any agent in the sidebar to inspect its output as it completes.</p></div>`;

    renderPipeline({}, false);

    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief })
        });
        const data = await response.json();
        currentJobId = data.job_id;
        pollInterval = setInterval(pollStatus, 2000);
    } catch (err) {
        console.error(err);
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('statusDot').className = 'status-dot idle';
        document.getElementById('statusLabel').innerText = 'Error';
        document.getElementById('outputViewer').innerHTML = `<div class="error-block">Failed to connect to the backend. Make sure the server is running.</div>`;
    }
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

        if (selectedAgentKey && currentTab === 'agent') {
            const agentMeta = AGENT_LIST.find(a => a.key === selectedAgentKey);
            const agentData = latestState[selectedAgentKey] || { status: 'pending' };
            showAgentOutput(agentMeta, agentData);
        }

        if (data.is_done) {
            clearInterval(pollInterval);
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('progressBar').style.width = '100%';
            document.getElementById('progressPercent').innerText = '100%';
            document.getElementById('currentAgentLabel').innerText = 'Complete ✓';
            document.getElementById('statusDot').className = 'status-dot idle';
            document.getElementById('statusLabel').innerText = 'Complete';

            // Show tabs and auto-render report
            document.getElementById('tabBar').style.display = 'flex';
            currentTab = 'report';
            updateTabUI();
            renderFullReport(latestState);
        }
    } catch (err) { console.error('Polling error:', err); }
}

// ── Tabs ──────────────────────────────────────────────────
function switchTab(tab) {
    currentTab = tab;
    updateTabUI();
    if (tab === 'report') {
        renderFullReport(latestState);
    } else {
        if (selectedAgentKey) {
            const agentMeta = AGENT_LIST.find(a => a.key === selectedAgentKey);
            const agentData = latestState[selectedAgentKey] || { status: 'pending' };
            showAgentOutput(agentMeta, agentData);
        } else {
            document.getElementById('outputTitle').innerText = 'Agent Inspector';
            document.getElementById('outputSubtitle').innerText = 'Select an agent from the sidebar';
            document.getElementById('outputViewer').innerHTML = `
                <div class="empty-state"><div class="empty-state-icon">🔍</div>
                <p>Click on any agent in the sidebar to see its raw JSON payload and reasoning process.</p></div>`;
        }
    }
}
function updateTabUI() {
    document.getElementById('tabReport').className = `tab-btn ${currentTab === 'report' ? 'active' : ''}`;
    document.getElementById('tabAgent').className = `tab-btn ${currentTab === 'agent' ? 'active' : ''}`;
}
// expose to window for onclick
window.switchTab = switchTab;

// ── Degradation Popup ─────────────────────────────────────
function checkDegradations(state) {
    AGENT_LIST.forEach(agent => {
        const d = state[agent.key];
        if (d && d.status === 'degraded' && !alertedAgents.has(agent.key)) {
            alertedAgents.add(agent.key);
            document.getElementById('modalFallbackText').innerText = `${agent.name}: ${d.fallback_instruction || d.error_message || 'Manual intervention required.'}`;
            document.getElementById('interventionModal').style.display = 'flex';
        }
    });
}

// ── Pipeline Sidebar ──────────────────────────────────────
function renderPipeline(state, isDone) {
    const pipelineDiv = document.getElementById('pipeline');
    pipelineDiv.innerHTML = '';
    let completedCount = 0, currentlyWorkingIndex = -1;

    AGENT_LIST.forEach((agent, i) => {
        const d = state[agent.key] || { status: 'pending' };
        if (d.status !== 'pending') completedCount++;
        else if (currentlyWorkingIndex === -1 && !isDone) currentlyWorkingIndex = i;
    });

    const pct = Math.round((completedCount / AGENT_LIST.length) * 100);
    if (!isDone) {
        document.getElementById('progressBar').style.width = `${pct}%`;
        document.getElementById('progressPercent').innerText = `${pct}%`;
        if (currentlyWorkingIndex !== -1) document.getElementById('currentAgentLabel').innerText = AGENT_LIST[currentlyWorkingIndex].name;
    }

    AGENT_LIST.forEach((agent, i) => {
        const d = state[agent.key] || { status: 'pending' };
        let rs = d.status;
        if (i === currentlyWorkingIndex) rs = 'working';

        const card = document.createElement('div');
        card.className = `agent-card${selectedAgentKey === agent.key ? ' selected' : ''}`;
        card.onclick = () => {
            selectedAgentKey = agent.key;
            currentTab = 'agent';
            if (document.getElementById('tabBar').style.display !== 'none') updateTabUI();
            showAgentOutput(agent, d);
            document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
        };
        card.innerHTML = `
            <div class="agent-icon ${rs}">${getIcon(rs)}</div>
            <div class="agent-info"><div class="agent-name">${agent.name}</div><div class="agent-status-text">${rs === 'working' ? 'Running...' : rs}</div></div>
            <span class="agent-badge ${rs}">${rs}</span>`;
        pipelineDiv.appendChild(card);
    });
}
function getIcon(s) { return { success:'✓', degraded:'!', skipped:'—', working:'◉' }[s] || '○'; }

// ── Agent Inspector View ──────────────────────────────────
function showAgentOutput(agent, d) {
    const viewer = document.getElementById('outputViewer');
    document.getElementById('outputTitle').innerText = agent.name;
    document.getElementById('outputSubtitle').innerText = agent.desc;
    let h = '';

    if (d.status === 'pending') {
        h = `<div class="empty-state fade-in"><div class="empty-state-icon">⏳</div><p>This agent hasn't started yet.</p></div>`;
    } else if (d.status === 'skipped') {
        h = `<div class="empty-state fade-in"><div class="empty-state-icon">⏭️</div><p>Skipped by the Orchestrator's scenario classification.</p></div>`;
    } else {
        h = '<div class="fade-in">';
        if (d.status === 'degraded' && d.fallback_instruction) {
            h += `<div class="degradation-block"><div class="degradation-block-header">⚠️ Degradation Contract Triggered</div><p><strong>Action:</strong> ${d.fallback_instruction}</p></div>`;
        }
        if (d.payload && d.payload.thinking_process) {
            h += `<div class="thinking-block"><div class="thinking-block-header">🧠 Agent Reasoning</div><p>${esc(d.payload.thinking_process)}</p></div>`;
        }
        if (d.payload) {
            const dp = { ...d.payload }; delete dp.thinking_process;
            h += `<div class="payload-header"><h4>Structured Output</h4><button class="copy-btn" onclick="copyJSON()">Copy JSON</button></div><pre id="jsonPayload">${esc(JSON.stringify(dp, null, 2))}</pre>`;
        }
        if (d.error_message) h += `<div class="error-block"><strong>Error:</strong> ${esc(d.error_message)}</div>`;
        h += '</div>';
    }
    viewer.innerHTML = h;
}

// ── Full Report View ──────────────────────────────────────
function renderFullReport(state) {
    if (!state) return;
    document.getElementById('outputTitle').innerText = 'UX POC Research Report';
    document.getElementById('outputSubtitle').innerText = 'Consolidated findings from all agents';
    const viewer = document.getElementById('outputViewer');

    let successCount = 0, degradedCount = 0, skippedCount = 0;
    AGENT_LIST.forEach(a => {
        const s = (state[a.key] || {}).status;
        if (s === 'success') successCount++;
        else if (s === 'degraded') degradedCount++;
        else if (s === 'skipped') skippedCount++;
    });

    let h = '<div class="report fade-in">';

    // Header
    h += `<div class="report-header">
        <h2>UX POC Research Report</h2>
        <div class="report-meta">
            <span style="color:var(--success)">✓ ${successCount} Completed</span>
            <span style="color:var(--warning)">⚠ ${degradedCount} Degraded</span>
            <span style="color:var(--skip)">— ${skippedCount} Skipped</span>
            <span>Generated ${new Date().toLocaleDateString('en-US', { year:'numeric', month:'long', day:'numeric' })}</span>
        </div>
    </div>`;

    // Orchestrator section
    const orch = state.orchestrator;
    if (orch && orch.payload) {
        h += reportSection('00', 'Scenario Classification', orch.status, `
            <div class="report-card"><div class="report-kv">
                <dt>Primary Scenario</dt><dd><strong>${val(orch.payload.primary_scenario)}</strong></dd>
                <dt>Confidence</dt><dd>${val(orch.payload.confidence)}</dd>
                <dt>Complexity</dt><dd>${val(orch.payload.complexity_tier)}</dd>
                <dt>Reasoning</dt><dd>${val(orch.payload.reasoning)}</dd>
            </div></div>`);
    }

    // Agent sections — render rich summaries from payload
    const agentRenderers = [
        { key:'a01_brief_framing', num:'01', title:'Brief Framing', render: p => kvCard({
            'Product Name': p.product_name, 'Domain': p.domain, 'Product Type': p.product_type,
            'Maturity Stage': p.maturity_stage, 'Primary Users': p.primary_users,
            'Core Problem': p.core_problem, 'Scope Boundaries': p.scope_boundaries
        })},
        { key:'a02_business_goals', num:'02', title:'Business Goals & Stakeholders', render: p => {
            let c = '';
            if (p.goal_hierarchy) c += listCard('Goal Hierarchy', p.goal_hierarchy, i => `<strong>${i.level || ''}:</strong> ${i.goal || i.description || JSON.stringify(i)}`);
            if (p.stakeholder_map) c += listCard('Stakeholder Map', p.stakeholder_map, i => `<strong>${i.role || i.name || ''}:</strong> ${i.influence || i.interest || JSON.stringify(i)}`);
            return c;
        }},
        { key:'a03_domain_market', num:'03', title:'Domain & Market Research', render: p => {
            let c = '';
            if (p.trends) c += listCard('Market Trends', p.trends, i => `<strong>${i.trend_name || i.name || ''}:</strong> ${i.relevance || i.description || JSON.stringify(i)}`);
            if (p.regulatory) c += listCard('Regulatory Landscape', p.regulatory, i => `${i.regulation || i.name || ''} — ${i.impact || JSON.stringify(i)}`);
            if (p.key_players) c += listCard('Key Players', p.key_players, i => `<strong>${i.name || ''}:</strong> ${i.differentiator || i.description || JSON.stringify(i)}`);
            return c;
        }},
        { key:'a04_competitive', num:'04', title:'Competitive Analysis', render: p => {
            let c = '';
            if (p.feature_matrix) c += listCard('Feature Matrix', p.feature_matrix, i => `<strong>${i.feature || i.name || ''}:</strong> ${i.availability || i.coverage || JSON.stringify(i)}`);
            if (p.gaps) c += listCard('Identified Gaps', p.gaps, i => `<strong>${i.gap || i.name || ''}:</strong> ${i.opportunity || i.description || JSON.stringify(i)}`);
            if (p.pattern_inventory) c += listCard('UX Patterns', p.pattern_inventory, i => `<strong>${i.pattern || i.name || ''}:</strong> ${i.usage || i.description || JSON.stringify(i)}`);
            return c;
        }},
        { key:'a05_secondary_research', num:'05', title:'Secondary User Research', render: p => {
            let c = '';
            if (p.pain_themes) c += listCard('Pain Themes', p.pain_themes, i => `<strong>${i.theme || i.name || ''}:</strong> ${i.evidence || i.description || JSON.stringify(i)}`);
            return c || genericCard(p);
        }},
        { key:'a06_ux_audit', num:'06', title:'UX Audit Findings', render: p => {
            let c = '';
            if (p.competitor_issues) c += listCard('Competitor Usability Issues', p.competitor_issues, i => `<strong>${i.competitor || i.name || ''}:</strong> ${i.issue || i.finding || JSON.stringify(i)}`);
            return c || genericCard(p);
        }},
        { key:'a07_persona', num:'07', title:'User Personas', render: p => {
            if (p.personas) return p.personas.map(persona => `<div class="report-card"><h5>${persona.name || 'Persona'}</h5><div class="report-kv">
                <dt>Archetype</dt><dd>${val(persona.archetype)}</dd>
                <dt>Age Range</dt><dd>${val(persona.age_range)}</dd>
                <dt>Occupation</dt><dd>${val(persona.occupation)}</dd>
                <dt>Tech Comfort</dt><dd>${val(persona.tech_comfort)}</dd>
                <dt>Quote</dt><dd><em>"${val(persona.quote)}"</em></dd>
            </div></div>`).join('');
            return genericCard(p);
        }},
        { key:'a08_jtbd', num:'08', title:'Jobs to Be Done', render: p => {
            if (p.jobs) return listCard('User Jobs', p.jobs, i => `<strong>When</strong> ${i.when || '...'}, <strong>I want to</strong> ${i.i_want_to || '...'}, <strong>so that</strong> ${i.so_that || '...'}`);
            return genericCard(p);
        }},
        { key:'a09_journey', num:'09', title:'Journey Maps', render: p => {
            if (p.journeys) return p.journeys.map(j => {
                let jh = `<div class="report-card"><h5>Journey: ${j.journey_name || j.name || 'Unnamed'}</h5>`;
                if (j.stages) jh += '<ul>' + j.stages.map(s => `<li><strong>${s.stage_name || s.name || ''}:</strong> ${s.user_action || s.description || JSON.stringify(s)}</li>`).join('') + '</ul>';
                jh += '</div>';
                return jh;
            }).join('');
            return genericCard(p);
        }},
        { key:'a10_task_flows', num:'10', title:'Key Task Flows', render: p => {
            if (p.flows) return p.flows.map(f => {
                let fh = `<div class="report-card"><h5>Flow: ${f.flow_name || f.name || 'Unnamed'}</h5>`;
                if (f.nodes) fh += '<ul>' + f.nodes.map(n => `<li>${n.label || n.name || JSON.stringify(n)}</li>`).join('') + '</ul>';
                fh += '</div>';
                return fh;
            }).join('');
            return genericCard(p);
        }},
        { key:'a11_ia', num:'11', title:'Information Architecture', render: p => {
            let c = '';
            if (p.sitemap) c += `<div class="report-card"><h5>Sitemap</h5><pre>${esc(JSON.stringify(p.sitemap, null, 2))}</pre></div>`;
            if (p.navigation) c += listCard('Navigation', p.navigation, i => `<strong>${i.label || i.name || ''}:</strong> ${i.destination || i.url || JSON.stringify(i)}`);
            return c || genericCard(p);
        }},
        { key:'a12_prioritization', num:'12', title:'Feature Prioritization', render: p => {
            if (p.backlog) return listCard('Prioritized Backlog', p.backlog, i => `<strong>[${(i.moscow || i.priority || '').toUpperCase()}]</strong> ${i.feature || i.name || ''} — RICE: ${i.rice_calc ? i.rice_calc.score || JSON.stringify(i.rice_calc) : 'N/A'}`);
            return genericCard(p);
        }},
        { key:'a13_success_matrix', num:'13', title:'Success Matrix & KPIs', render: p => {
            if (p.metrics) return listCard('Key Metrics', p.metrics, i => `<strong>${i.metric_name || i.name || ''}:</strong> Target: ${i.target || 'TBD'} | Baseline: ${i.baseline || 'N/A'} | Tool: ${i.tool || 'N/A'}`);
            return genericCard(p);
        }}
    ];

    agentRenderers.forEach(ar => {
        const d = state[ar.key];
        if (!d) return;

        if (d.status === 'skipped') {
            h += reportSection(ar.num, ar.title, 'skipped', `<div class="report-card"><p style="color:var(--text-muted)">Skipped by the Orchestrator — not required for this scenario.</p></div>`);
        } else if (d.status === 'degraded') {
            let content = `<div class="degradation-block"><div class="degradation-block-header">⚠️ Degradation Contract Triggered</div><p><strong>Action:</strong> ${d.fallback_instruction || 'Manual intervention required.'}</p></div>`;
            if (d.payload) { try { content += ar.render(d.payload); } catch(e) { content += genericCard(d.payload); } }
            h += reportSection(ar.num, ar.title, 'degraded', content);
        } else if (d.status === 'success' && d.payload) {
            let content = '';
            try { content = ar.render(d.payload); } catch(e) { content = genericCard(d.payload); }
            h += reportSection(ar.num, ar.title, 'success', content);
        }
    });

    // Download bar
    h += `<div class="download-bar">
        <button class="btn-secondary" onclick="downloadJSON()">📥 Download Full JSON</button>
        <button class="btn-secondary" onclick="window.print()">🖨️ Print Report</button>
    </div>`;

    h += '</div>';
    viewer.innerHTML = h;
}

// ── Report Helpers ────────────────────────────────────────
function reportSection(num, title, status, content) {
    return `<div class="report-section">
        <div class="report-section-header">
            <div class="report-section-number ${status}">${num}</div>
            <div class="report-section-title">${title}</div>
            <span class="report-section-badge ${status}">${status}</span>
        </div>
        ${content}
    </div>`;
}

function kvCard(obj) {
    let kv = '<div class="report-card"><div class="report-kv">';
    for (const [k, v] of Object.entries(obj)) {
        if (v !== undefined && v !== null && v !== '') kv += `<dt>${k}</dt><dd>${esc(String(v))}</dd>`;
    }
    kv += '</div></div>';
    return kv;
}

function listCard(title, arr, formatter) {
    if (!Array.isArray(arr) || arr.length === 0) return '';
    let h = `<div class="report-card"><h5>${title}</h5><ul>`;
    arr.forEach(item => { h += `<li>${formatter(item)}</li>`; });
    h += '</ul></div>';
    return h;
}

function genericCard(payload) {
    const dp = { ...payload }; delete dp.thinking_process;
    return `<div class="report-card"><pre>${esc(JSON.stringify(dp, null, 2))}</pre></div>`;
}

function val(v) { return v !== undefined && v !== null ? esc(String(v)) : '<span style="color:var(--text-muted)">—</span>'; }

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
}

// ── Utilities ─────────────────────────────────────────────
function copyJSON() {
    const el = document.getElementById('jsonPayload');
    if (el) {
        navigator.clipboard.writeText(el.innerText).then(() => {
            const btn = document.querySelector('.copy-btn');
            btn.innerText = 'Copied!';
            setTimeout(() => { btn.innerText = 'Copy JSON'; }, 1500);
        });
    }
}
window.copyJSON = copyJSON;

function downloadJSON() {
    if (!latestState) return;
    const blob = new Blob([JSON.stringify(latestState, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'ux-poc-report.json'; a.click();
    URL.revokeObjectURL(url);
}
window.downloadJSON = downloadJSON;

// Initial render
renderPipeline({}, false);
