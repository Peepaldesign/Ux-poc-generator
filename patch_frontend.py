import re

# 1. Patch index.html
with open('frontend/index.html', 'r') as f:
    html = f.read()

# Make history panel collapsible
html = html.replace('<div class="history-header">History</div>', 
'''<div class="history-header">
    History
    <button id="btn-collapse-history" style="float: right; background: none; border: none; color: var(--text-muted); cursor: pointer;">◀</button>
</div>''')

html = html.replace('<div class="sidebar-history">', '<div class="sidebar-history" id="sidebar-history">')
html = html.replace('<body>', '<body>\n    <button id="btn-expand-history" style="display: none; position: absolute; left: 0; top: 10px; background: var(--bg-card); color: white; border: 1px solid var(--border); padding: 5px; cursor: pointer; border-radius: 0 4px 4px 0; z-index: 100;">▶ History</button>')

# Add generate wireframes button in wireframes view
wireframe_html = '''<div class="view-content" id="view-wireframes" style="display: none;">
    <div id="wireframe-controls" style="margin-bottom: 20px; text-align: center;">
        <button id="btn-generate-wireframes" class="btn-primary" style="width: auto; padding: 10px 20px;" disabled>Generate Wireframes</button>
        <div id="wireframe-status-text" style="font-size: 0.8rem; color: var(--text-muted); margin-top: 5px;">Requires completed report</div>
    </div>
    <div id="wireframes-container"></div>
</div>'''
html = re.sub(r'<div class="view-content" id="view-wireframes" style="display: none;">.*?</div>', wireframe_html, html, flags=re.DOTALL)

with open('frontend/index.html', 'w') as f:
    f.write(html)

# 2. Patch app.js
with open('frontend/app.js', 'r') as f:
    js = f.read()

# Add init handlers for the new buttons
init_additions = '''
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
'''

js = js.replace('function init() {\n    renderPipeline();', 'function init() {\n    renderPipeline();' + init_additions)

# Update renderPipeline to show error_message
render_pipe_patch = '''
        if (status === 'degraded' || status === 'error') {
            const errMsg = currentState[phase.key]?.error_message || '';
            if (errMsg) {
                el.innerHTML += `<div style="color: var(--error); font-size: 0.75rem; margin-top: 4px;">Error: ${errMsg}</div>`;
            }
        }
        pipelineList.appendChild(el);
'''
js = js.replace('pipelineList.appendChild(el);', render_pipe_patch)

# In renderWireframesView, we must now write into #wireframes-container
render_wf_patch = '''
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
'''
js = re.sub(r'function renderWireframesView\(\).*?^}', render_wf_patch, js, flags=re.MULTILINE|re.DOTALL)

with open('frontend/app.js', 'w') as f:
    f.write(js)

