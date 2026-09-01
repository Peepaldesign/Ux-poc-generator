const API_BASE = "http://localhost:8000/api";

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
    document.getElementById('loading').style.display = 'block';
    document.getElementById('outputViewer').innerHTML = '<p>Click on an agent in the pipeline to view its output or fallback instructions.</p>';
    
    // Initialize pipeline UI to pending
    renderPipeline({});

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
        document.getElementById('loading').style.display = 'none';
    }
});

async function pollStatus() {
    if (!currentJobId) return;

    try {
        const response = await fetch(`${API_BASE}/status/${currentJobId}`);
        const data = await response.json();
        
        latestState = data.state;
        renderPipeline(latestState);

        if (data.is_done) {
            clearInterval(pollInterval);
            document.getElementById('submitBtn').disabled = false;
            document.getElementById('loading').innerHTML = 'Workflow Complete!';
            setTimeout(() => { document.getElementById('loading').style.display = 'none'; }, 3000);
        }
    } catch (err) {
        console.error('Polling error:', err);
    }
}

function renderPipeline(state) {
    const pipelineDiv = document.getElementById('pipeline');
    pipelineDiv.innerHTML = '';

    AGENT_LIST.forEach(agent => {
        const agentData = state[agent.key] || { status: 'pending' };
        
        const node = document.createElement('div');
        node.className = `agent-node ${agentData.status}`;
        node.onclick = () => showOutput(agent.name, agentData);
        
        node.innerHTML = `
            <span>${agent.name}</span>
            <span class="badge ${agentData.status}">${agentData.status}</span>
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
