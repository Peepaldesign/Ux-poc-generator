const API_BASE = "/api";

const AGENT_LIST = [
    { key: "orchestrator", name: "Orchestrator Classifier" },
    { key: "a01_brief_framing", name: "01: Brief Framing" },
    { key: "a02_business_goals", name: "02: Business Goals" },
    { key: "a03_domain_market", name: "03: Domain/Market Research" },
    { key: "a04_competitive", name: "04: Competitive Analysis" },
    { key: "a05_secondary_research", name: "05: Secondary User Research" },
    { key: "a06_ux_audit", name: "06: UX Audit" },
    { key: "a07_persona", name: "07: Persona Building" },
    { key: "a08_jtbd", name: "08: JTBD / User Need" },
    { key: "a09_journey", name: "09: Journey Mapping" },
    { key: "a10_task_flows", name: "10: Key Task Flows" },
    { key: "a11_ia", name: "11: Information Architecture" },
    { key: "a12_prioritization", name: "12: Feature Prioritization" },
    { key: "a13_success_matrix", name: "13: Success Matrix" }
];

let currentJobId = null;
let pollInterval = null;
let latestState = null;

document.getElementById('submitBtn').addEventListener('click', async () => {
    const brief = document.getElementById('briefInput').value.trim();
    if (!brief) return alert('Please enter a brief.');

    document.getElementById('submitBtn').disabled = true;
    document.getElementById('progressContainer').style.display = 'block';
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressText').innerText = '0% Complete';
    document.getElementById('outputViewer').innerHTML = '<p>Click on an agent in the pipeline to view its output or fallback instructions.</p>';
    
    // Initialize pipeline UI to pending
    renderPipeline({}, false);

    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief })
        });
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Start polling
        pollInterval = setInterval(pollStatus, 2000);
    } catch (err) {
        console.error(err);
        alert('Failed to start workflow.');
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('progressContainer').style.display = 'none';
    }
});

async function pollStatus() {
    if (!currentJobId) return;

    try {
        const response = await fetch(`${API_BASE}/status/${currentJobId}`);
        const data = await response.json();
        
        latestState = data.state;
        renderPipeline(latestState, data.is_done);

        if (data.is_done) {
            clearInterval(pollInterval);
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('progressBar').style.width = '100%';
            document.getElementById('progressText').innerText = '100% Complete - Workflow Finished!';
        }
    } catch (err) {
        console.error('Polling error:', err);
    }
}

function renderPipeline(state, isDone) {
    const pipelineDiv = document.getElementById('pipeline');
    pipelineDiv.innerHTML = '';

    let completedCount = 0;
    let currentlyWorkingIndex = -1;

    // First pass to determine counts and currently working agent
    AGENT_LIST.forEach((agent, index) => {
        const agentData = state[agent.key] || { status: 'pending' };
        if (agentData.status !== 'pending') {
            completedCount++;
        } else if (currentlyWorkingIndex === -1 && !isDone) {
            currentlyWorkingIndex = index;
        }
    });

    // Update progress bar
    const percentage = Math.round((completedCount / AGENT_LIST.length) * 100);
    if (!isDone) {
        document.getElementById('progressBar').style.width = `${percentage}%`;
        
        if (currentlyWorkingIndex !== -1) {
            const workingAgentName = AGENT_LIST[currentlyWorkingIndex].name;
            document.getElementById('progressText').innerText = `${percentage}% Complete - ${workingAgentName} is working...`;
        }
    }

    // Second pass to render
    AGENT_LIST.forEach((agent, index) => {
        const agentData = state[agent.key] || { status: 'pending' };
        let renderStatus = agentData.status;

        // Override visual status for the currently working agent
        if (index === currentlyWorkingIndex) {
            renderStatus = 'working';
        }
        
        const node = document.createElement('div');
        node.className = `agent-node ${renderStatus}`;
        node.onclick = () => showOutput(agent.name, agentData);
        
        node.innerHTML = `
            <span>${agent.name}</span>
            <span class="badge ${renderStatus}">${renderStatus}</span>
        `;
        
        pipelineDiv.appendChild(node);
    });
}

function showOutput(agentName, agentData) {
    const viewer = document.getElementById('outputViewer');
    let html = `<h3>${agentName}</h3>`;

    if (agentData.status === 'pending') {
        html += `<p>This agent has not executed yet.</p>`;
    } else if (agentData.status === 'skipped') {
        html += `<p>This agent was deliberately skipped based on the orchestrator's scenario matrix.</p>`;
    } else {
        // Show Fallback if degraded
        if (agentData.status === 'degraded' && agentData.fallback_instruction) {
            html += `
                <div class="fallback-box">
                    <h4>DEGRADATION CONTRACT TRIGGERED</h4>
                    <p><strong>Action required by human designer:</strong></p>
                    <p>${agentData.fallback_instruction}</p>
                </div>
            `;
        }

        // Show Payload if exists
        if (agentData.payload) {
            html += `<p><strong>JSON Payload:</strong></p>`;
            html += `<pre>${JSON.stringify(agentData.payload, null, 2)}</pre>`;
        }
        
        // Show Error if degraded
        if (agentData.error_message) {
            html += `<p style="color: red;"><strong>Internal Error:</strong> ${agentData.error_message}</p>`;
        }
    }

    viewer.innerHTML = html;
}

// Initial render
renderPipeline({});
