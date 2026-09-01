const API_BASE = "/api";

const AGENT_LIST = [
    { key: "orchestrator", name: "Orchestrator", desc: "Classifies the brief into a scenario" },
    { key: "a01_brief_framing", name: "Brief Framing", desc: "Structures the raw brief" },
    { key: "a02_business_goals", name: "Business Goals", desc: "Extracts goals & stakeholder map" },
    { key: "a03_domain_market", name: "Domain Research", desc: "Analyzes market trends & regulations" },
    { key: "a04_competitive", name: "Competitive Analysis", desc: "Feature matrix & gap analysis" },
    { key: "a05_secondary_research", name: "User Research", desc: "Secondary user pain themes" },
    { key: "a06_ux_audit", name: "UX Audit", desc: "Heuristic audit of existing product" },
    { key: "a07_persona", name: "Persona Building", desc: "Builds grounded user personas" },
    { key: "a08_jtbd", name: "Jobs to Be Done", desc: "Maps user jobs & outcomes" },
    { key: "a09_journey", name: "Journey Mapping", desc: "End-to-end user journey maps" },
    { key: "a10_task_flows", name: "Key Task Flows", desc: "Critical task flow diagrams" },
    { key: "a11_ia", name: "Info Architecture", desc: "Sitemap & navigation structure" },
    { key: "a12_prioritization", name: "Feature Priority", desc: "MoSCoW & RICE prioritization" },
    { key: "a13_success_matrix", name: "Success Matrix", desc: "KPIs & measurement framework" }
];

let currentJobId = null;
let pollInterval = null;
let latestState = null;
let selectedAgentKey = null;

// Track which agents have already shown a popup
const alertedAgents = new Set();

document.getElementById('submitBtn').addEventListener('click', async () => {
    const brief = document.getElementById('briefInput').value.trim();
    if (!brief) {
        document.getElementById('briefInput').focus();
        return;
    }

    document.getElementById('submitBtn').disabled = true;
    document.getElementById('progressSection').classList.add('active');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressPercent').innerText = '0%';
    document.getElementById('currentAgentLabel').innerText = 'Starting...';
    document.getElementById('statusDot').className = 'status-dot running';
    document.getElementById('statusLabel').innerText = 'Running';
    selectedAgentKey = null;

    // Clear previous state
    alertedAgents.clear();

    // Reset output viewer
    document.getElementById('outputTitle').innerText = 'Output Inspector';
    document.getElementById('outputSubtitle').innerText = 'Select an agent to view its output';
    document.getElementById('outputViewer').innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚡</div>
            <p>The pipeline is running. Click on any agent in the sidebar to inspect its output as it completes.</p>
        </div>
    `;

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
        document.getElementById('outputViewer').innerHTML = `
            <div class="error-block">Failed to connect to the backend server. Make sure it is running on the correct port.</div>
        `;
    }
});

async function pollStatus() {
    if (!currentJobId) return;
    try {
        const response = await fetch(`${API_BASE}/status/${currentJobId}`);
        const data = await response.json();

        latestState = data.state;
        renderPipeline(latestState, data.is_done);
        checkDegradations(latestState);

        // If user has selected an agent, auto-refresh its output
        if (selectedAgentKey) {
            const agentMeta = AGENT_LIST.find(a => a.key === selectedAgentKey);
            const agentData = latestState[selectedAgentKey] || { status: 'pending' };
            showOutput(agentMeta, agentData);
        }

        if (data.is_done) {
            clearInterval(pollInterval);
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('progressBar').style.width = '100%';
            document.getElementById('progressPercent').innerText = '100%';
            document.getElementById('currentAgentLabel').innerText = 'Complete ✓';
            document.getElementById('statusDot').className = 'status-dot idle';
            document.getElementById('statusLabel').innerText = 'Complete';
        }
    } catch (err) {
        console.error('Polling error:', err);
    }
}

function checkDegradations(state) {
    AGENT_LIST.forEach(agent => {
        const agentData = state[agent.key];
        if (agentData && agentData.status === 'degraded' && !alertedAgents.has(agent.key)) {
            alertedAgents.add(agent.key);
            const fallbackText = agentData.fallback_instruction || agentData.error_message || "Manual intervention required.";
            document.getElementById('modalFallbackText').innerText = `${agent.name}: ${fallbackText}`;
            document.getElementById('interventionModal').style.display = 'flex';
        }
    });
}

function renderPipeline(state, isDone) {
    const pipelineDiv = document.getElementById('pipeline');
    pipelineDiv.innerHTML = '';

    let completedCount = 0;
    let currentlyWorkingIndex = -1;

    AGENT_LIST.forEach((agent, index) => {
        const agentData = state[agent.key] || { status: 'pending' };
        if (agentData.status !== 'pending') {
            completedCount++;
        } else if (currentlyWorkingIndex === -1 && !isDone) {
            currentlyWorkingIndex = index;
        }
    });

    // Update progress
    const percentage = Math.round((completedCount / AGENT_LIST.length) * 100);
    if (!isDone) {
        document.getElementById('progressBar').style.width = `${percentage}%`;
        document.getElementById('progressPercent').innerText = `${percentage}%`;
        if (currentlyWorkingIndex !== -1) {
            document.getElementById('currentAgentLabel').innerText = AGENT_LIST[currentlyWorkingIndex].name;
        }
    }

    // Render agent cards
    AGENT_LIST.forEach((agent, index) => {
        const agentData = state[agent.key] || { status: 'pending' };
        let renderStatus = agentData.status;
        if (index === currentlyWorkingIndex) renderStatus = 'working';

        const card = document.createElement('div');
        card.className = `agent-card ${selectedAgentKey === agent.key ? 'selected' : ''}`;
        card.onclick = () => {
            selectedAgentKey = agent.key;
            showOutput(agent, agentData);
            // Update selection visually
            document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
        };

        const statusIcon = getStatusIcon(renderStatus);
        const statusLabel = renderStatus === 'working' ? 'Running...' : renderStatus;

        card.innerHTML = `
            <div class="agent-icon ${renderStatus}">${statusIcon}</div>
            <div class="agent-info">
                <div class="agent-name">${agent.name}</div>
                <div class="agent-status-text">${statusLabel}</div>
            </div>
            <span class="agent-badge ${renderStatus}">${renderStatus}</span>
        `;

        pipelineDiv.appendChild(card);
    });
}

function getStatusIcon(status) {
    switch (status) {
        case 'success': return '✓';
        case 'degraded': return '!';
        case 'skipped': return '—';
        case 'working': return '◉';
        default: return '○';
    }
}

function showOutput(agent, agentData) {
    const viewer = document.getElementById('outputViewer');
    document.getElementById('outputTitle').innerText = agent.name;
    document.getElementById('outputSubtitle').innerText = agent.desc;

    let html = '';

    if (agentData.status === 'pending') {
        html = `
            <div class="empty-state fade-in">
                <div class="empty-state-icon">⏳</div>
                <p>This agent hasn't started yet. It will execute once its upstream dependencies are complete.</p>
            </div>
        `;
    } else if (agentData.status === 'skipped') {
        html = `
            <div class="empty-state fade-in">
                <div class="empty-state-icon">⏭️</div>
                <p>This agent was intentionally skipped based on the Orchestrator's scenario classification. It is not required for this type of brief.</p>
            </div>
        `;
    } else {
        html = '<div class="fade-in">';

        // Degradation block
        if (agentData.status === 'degraded' && agentData.fallback_instruction) {
            html += `
                <div class="degradation-block">
                    <div class="degradation-block-header">⚠️ Degradation Contract Triggered</div>
                    <p><strong>Action for designer:</strong> ${agentData.fallback_instruction}</p>
                </div>
            `;
        }

        // Thinking process
        if (agentData.payload && agentData.payload.thinking_process) {
            html += `
                <div class="thinking-block">
                    <div class="thinking-block-header">🧠 Agent Reasoning</div>
                    <p>${agentData.payload.thinking_process}</p>
                </div>
            `;
        }

        // JSON Payload
        if (agentData.payload) {
            const displayPayload = { ...agentData.payload };
            delete displayPayload.thinking_process;

            html += `
                <div class="payload-header">
                    <h4>Structured Output</h4>
                    <button class="copy-btn" onclick="copyPayload()">Copy JSON</button>
                </div>
                <pre id="jsonPayload">${JSON.stringify(displayPayload, null, 2)}</pre>
            `;
        }

        // Error message
        if (agentData.error_message) {
            html += `<div class="error-block"><strong>Internal Error:</strong> ${agentData.error_message}</div>`;
        }

        html += '</div>';
    }

    viewer.innerHTML = html;
}

function copyPayload() {
    const el = document.getElementById('jsonPayload');
    if (el) {
        navigator.clipboard.writeText(el.innerText).then(() => {
            const btn = document.querySelector('.copy-btn');
            btn.innerText = 'Copied!';
            setTimeout(() => { btn.innerText = 'Copy JSON'; }, 1500);
        });
    }
}

// Initial render
renderPipeline({}, false);
