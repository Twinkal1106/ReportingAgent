
function formatCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.innerText = text;
    return div.innerHTML;
}

function scrollToBottom() {
    const container = document.getElementById('report-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function appendUserMessage(text) {
    const container = document.getElementById('report-container');
    const time = formatCurrentTime();
    const safeText = escapeHtml(text);

    const row = document.createElement('div');
    row.className = 'message-row user-row';
    row.innerHTML = `
        <div class="avatar user-avatar" title="User">🧑</div>
        <div class="message-wrapper">
            <div class="message-bubble user-bubble">${safeText}</div>
            <span class="message-time">${time}</span>
        </div>
    `;
    container.appendChild(row);
    scrollToBottom();
}

function showLoadingIndicator() {
    const container = document.getElementById('report-container');
    const loadingRow = document.createElement('div');
    loadingRow.className = 'message-row agent-row';
    loadingRow.id = 'agent-loading-indicator';
    loadingRow.innerHTML = `
        <div class="avatar agent-avatar" title="FedEx Agent">🤖</div>
        <div class="message-wrapper">
            <div class="message-bubble agent-bubble">
                <div class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
            <span class="message-time">Thinking...</span>
        </div>
    `;
    container.appendChild(loadingRow);
    scrollToBottom();
}

function removeLoadingIndicator() {
    const indicator = document.getElementById('agent-loading-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function appendAgentMessage(contentHtml, isError = false) {
    removeLoadingIndicator();
    const container = document.getElementById('report-container');
    const time = formatCurrentTime();

    const row = document.createElement('div');
    row.className = 'message-row agent-row';
    row.innerHTML = `
        <div class="avatar agent-avatar" title="FedEx Agent">🤖</div>
        <div class="message-wrapper">
            <div class="message-bubble agent-bubble ${isError ? 'error-bubble' : ''}">
                ${contentHtml}
            </div>
            <span class="message-time">${time}</span>
        </div>
    `;
    container.appendChild(row);
    scrollToBottom();
}

async function generate() {
    const inputField = document.getElementById('msg');
    const sendBtn = document.getElementById('send-btn');
    const question = inputField.value.trim();

    if (!question) {
        return;
    }

    // Clear input immediately and lock send button during execution
    inputField.value = '';
    if (sendBtn) sendBtn.disabled = true;

    // Append user message bubble to the thread
    appendUserMessage(question);

    // Show agent thinking indicator
    showLoadingIndicator();

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ question })
        });

        if (!response.ok) {
            const err = await response.json();
            appendAgentMessage(`<strong>❌ Request Error:</strong><br>${escapeHtml(err.error || 'Server error')}`, true);
            return;
        }

        const data = await response.json();

        if (data.success && data.data && data.data.response) {
            let responseText = data.data.response;
            let displayHTML = '';

            try {
                // Check if JSON with PDF download info
                const pdfInfo = JSON.parse(responseText);

                if (pdfInfo.success && pdfInfo.download_url) {
                    displayHTML = `
                        <div class="pdf-card">
                            <div class="pdf-card-title">📄 PDF Report Generated Successfully!</div>
                            <div class="pdf-meta"><strong>File:</strong> ${escapeHtml(pdfInfo.filename || '')}</div>
                            <div class="pdf-meta"><strong>Records:</strong> ${pdfInfo.record_count ?? 'N/A'}</div>
                            <div class="pdf-meta"><strong>Size:</strong> ${pdfInfo.file_size_kb ?? 'N/A'} KB</div>
                            <a class="pdf-download-btn" href="${pdfInfo.download_url}" download="${pdfInfo.filename || 'report.pdf'}">
                                📥 Download PDF Report
                            </a>
                        </div>
                    `;
                } else {
                    displayHTML = `
                        <div style="font-weight: 600; margin-bottom: 6px; color: #4D148C;">Agent Response:</div>
                        <pre>${escapeHtml(JSON.stringify(pdfInfo, null, 2))}</pre>
                    `;
                }
            } catch (e) {
                // Not JSON, format regular text and links
                let formattedText = escapeHtml(responseText);
                formattedText = formattedText.replace(
                    /(https?:\/\/[^\s]+)/g,
                    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
                );

                displayHTML = `<div style="white-space: pre-wrap;">${formattedText}</div>`;
            }

            appendAgentMessage(displayHTML);
        } else {
            appendAgentMessage(`<strong>❌ Error:</strong><br>${escapeHtml(data.error || 'Failed to get AI response')}`, true);
        }
    } catch (error) {
        appendAgentMessage(`<strong>❌ Connection Error:</strong><br>${escapeHtml(error.message)}`, true);
    } finally {
        removeLoadingIndicator();
        if (sendBtn) sendBtn.disabled = false;
        inputField.focus();
    }
}

function applyQuickPrompt(promptText) {
    const inputField = document.getElementById('msg');
    if (!inputField) return;
    inputField.value = promptText;
    inputField.focus();
    generate();
}

function applyUserName(name) {
    if (!name || !name.trim()) return;
    const cleanName = name.trim();
    const initial = cleanName[0].toUpperCase();

    const greetingEl = document.getElementById('user-greeting-text');
    if (greetingEl) greetingEl.textContent = `Hi, ${cleanName}`;

    const badgeEl = document.getElementById('user-badge-initial');
    if (badgeEl) {
        badgeEl.textContent = initial;
        badgeEl.title = cleanName;
    }

    const welcomeNameEl = document.getElementById('welcome-user-name');
    if (welcomeNameEl) welcomeNameEl.textContent = cleanName;

    localStorage.setItem('fedex_user_name', cleanName);
    document.cookie = `fedex_user_name=${encodeURIComponent(cleanName)}; path=/; max-age=31536000`;
}

// Bind events on load
document.addEventListener('DOMContentLoaded', function() {
    // Check URL query parameters (?user=... or ?name=...)
    const params = new URLSearchParams(window.location.search);
    const paramName = params.get('user') || params.get('name');
    if (paramName) {
        applyUserName(paramName);
    } else {
        const savedName = localStorage.getItem('fedex_user_name');
        if (savedName) {
            applyUserName(savedName);
        }
    }

    // Allow user to click the header badge/greeting to change display name
    const userBtn = document.getElementById('header-user-btn');
    if (userBtn) {
        userBtn.addEventListener('click', function() {
            const currentGreeting = document.getElementById('user-greeting-text');
            const current = currentGreeting ? currentGreeting.textContent.replace('Hi, ', '').trim() : '';
            const newName = prompt('Enter your name for the FedEx Reporting Agent:', current);
            if (newName && newName.trim()) {
                applyUserName(newName);
            }
        });
    }

    const inputField = document.getElementById('msg');
    if (inputField) {
        inputField.focus();
        inputField.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                generate();
            }
        });
    }

    // Attach click listener to all quick action chips
    document.querySelectorAll('.chip').forEach(function(chip) {
        chip.addEventListener('click', function(e) {
            e.preventDefault();
            const promptText = chip.getAttribute('data-prompt') || chip.innerText.trim();
            applyQuickPrompt(promptText);
        });
    });
});

function newChat() {
    const container = document.getElementById('report-container');
    if (!container) return;
    const nameElem = document.getElementById('welcome-user-name');
    const currentName = nameElem ? nameElem.textContent.trim() : (localStorage.getItem('fedex_user_name') || 'Twinkal');
    
    container.innerHTML = `
        <div class="welcome-banner">
            <div class="welcome-avatar">🤖</div>
            <div class="welcome-text">
                <h3>Hi <span id="welcome-user-name">${escapeHtml(currentName)}</span> 👋 Welcome to your FedEx Reporting Agent</h3>
                <p>How can I assist you today? Ask me to generate standard or consolidated reports, query Cassandra, or create customized PDF reports.</p>
            </div>
        </div>
    `;
    const inputField = document.getElementById('msg');
    if (inputField) {
        inputField.value = '';
        inputField.focus();
    }
}
