/**
 * ResearchPilotAI — Frontend Script
 * Fixed and Optimized for performance.
 */

// ── Application State ──────────────────────────────────────────────────────────
const state = {
    selectedAgent: "research",
    pdfContent: "",
    pdfDocumentId: "",
    selectedEnhancementTool: "topic_generator",
    isChatStreaming: false,
    activeRequests: new Set(),
    statsCache: null,
    lastStatsFetch: 0
};

// ── Utilities ──────────────────────────────────────────────────────────────────

function $(selector) {
    return document.querySelector(selector);
}

function showLoader(show, text = "Processing...") {
    const loader = $("#loader");
    const loaderText = $("#loader-text");
    if (loaderText) loaderText.textContent = text;
    if (loader) loader.classList.toggle("hidden", !show);
}

function showToast(message, type = "success") {
    const toast = $("#toast");
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove("hidden");
    setTimeout(() => toast.classList.add("hidden"), 3500);
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function renderMarkdown(text) {
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/^### (.+)$/gm, "<h4>$1</h4>")
        .replace(/^## (.+)$/gm, "<h3>$1</h3>")
        .replace(/^# (.+)$/gm, "<h2>$1</h2>")
        .replace(/^---$/gm, "<hr>")
        .replace(/^[-•▸]\s+(.+)$/gm, "<li>$1</li>")
        .replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>")
        .replace(/\n{2,}/g, "</p><p>")
        .replace(/\n/g, "<br>");
}

async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || `Request failed (${response.status})`);
        }
        const data = await response.json();
        if (data.success === false) {
            throw new Error(data.error || "Operation failed.");
        }
        return data;
    } catch (e) {
        throw e;
    }
}

function getModelSettings() {
    const selectedModel = document.querySelector('input[name="ai-model"]:checked');
    const model = selectedModel ? selectedModel.value : document.body.dataset.defaultModel || "qwen2.5-coder:3b";
    const tempSlider = $("#temp-slider");
    const maxTokensInput = $("#max-tokens-input");
    const temperature = tempSlider ? parseFloat(tempSlider.value) : 0.7;
    const maxTokens = maxTokensInput ? parseInt(maxTokensInput.value) : 2048;
    return { model, temperature, maxTokens };
}

function isStreamingEnabled() {
    const toggle = $("#streaming-toggle");
    return toggle ? toggle.checked : true;
}

// ── Tab Navigation ─────────────────────────────────────────────────────────────

function updateNavIndicator() {
    const activeTab = document.querySelector('.tab-btn.active');
    const indicator = document.querySelector('.nav-indicator');
    if (activeTab && indicator) {
        indicator.style.width = activeTab.offsetWidth + 'px';
        indicator.style.left = activeTab.offsetLeft + 'px';
    }
}
window.addEventListener('resize', updateNavIndicator);

function initTabs() {
    document.querySelectorAll(".tab-btn").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((btn) => btn.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
            button.classList.add("active");
            updateNavIndicator();
            const target = $(`#tab-${button.dataset.tab}`);
            if (target) target.classList.add("active");
        });
    });
}

// ── Settings Panel ─────────────────────────────────────────────────────────────

function initSettings() {
    const toggleBtn = $("#settings-toggle-btn");
    const panel = $("#model-settings-panel");
    const closeBtn = $("#close-settings");
    const tempSlider = $("#temp-slider");
    const tempVal = $("#temp-val");

    if (toggleBtn && panel) {
        toggleBtn.addEventListener("click", () => panel.classList.toggle("hidden"));
    }
    if (closeBtn && panel) {
        closeBtn.addEventListener("click", () => panel.classList.add("hidden"));
    }
    if (tempSlider && tempVal) {
        tempSlider.addEventListener("input", () => {
            tempVal.textContent = parseFloat(tempSlider.value).toFixed(1);
        });
    }
}

// ── Chat ───────────────────────────────────────────────────────────────────────

function formatMessageTimestamp() {
    return new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function attachCopyMessageAction(messageEl) {
    const copyBtn = messageEl.querySelector(".msg-copy-btn");
    if (!copyBtn) return;
    copyBtn.addEventListener("click", async () => {
        const body = messageEl.querySelector(".msg-body");
        const text = body ? body.innerText : "";
        if (!text) {
            showToast("Nothing to copy.", "error");
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            const original = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied';
            setTimeout(() => {
                copyBtn.innerHTML = original;
            }, 1400);
            showToast("Response copied to clipboard.", "success");
        } catch (error) {
            showToast("Copy failed.", "error");
        }
    });
}

function appendChatMessage(role, text, streaming = false) {
    const chatBox = $("#chat-box");
    if (!chatBox) return null;
    const div = document.createElement("div");
    div.className = `message ${role}`;
    if (streaming) div.dataset.streaming = "true";

    const displayName = role === "user" ? "You" : role === "ai" ? "AI" : "Alert";
    const timeStamp = `<span class="message-time">${formatMessageTimestamp()}</span>`;
    const copyMarkup = role === "ai" && !streaming
        ? `<button class="msg-copy-btn" type="button"><i class="fa-regular fa-copy"></i> Copy</button>`
        : "";
    const bodyMarkup = role === "ai" && !streaming
        ? renderMarkdown(text)
        : escapeHtml(text);

    div.innerHTML = `
        <div class="message-header">
            <span>${displayName}</span>
            <span class="message-meta">${timeStamp}${copyMarkup}</span>
        </div>
        <span class="msg-body">${bodyMarkup}</span>
    `;

    chatBox.appendChild(div);
    if (role === "ai" && !streaming) attachCopyMessageAction(div);
    chatBox.scrollTop = chatBox.scrollHeight;
    return div;
}

function appendTypingIndicator() {
    const chatBox = $("#chat-box");
    if (!chatBox) return null;
    const div = document.createElement("div");
    div.className = "message ai typing-indicator";
    div.id = "typing-indicator";
    div.innerHTML = `
        <div class="message-header">
            <span>AI</span>
            <span class="message-meta"><span class="message-time">${formatMessageTimestamp()}</span></span>
        </div>
        <span class="msg-body"><span class="typing-dots"><span></span><span></span><span></span></span></span>
    `;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
    return div;
}

function removeTypingIndicator() {
    const indicator = $("#typing-indicator");
    if (indicator) indicator.remove();
}

async function sendChatMessage() {
    const input = $("#chat-input");
    const sendBtn = $("#chat-send");
    if (!input || !sendBtn) return;
    const message = input.value.trim();

    if (!message) return;
    if (state.isChatStreaming) return; // prevent duplicate sends

    appendChatMessage("user", message);
    input.value = "";

    if (isStreamingEnabled()) {
        await sendChatStreaming(message, sendBtn);
    } else {
        await sendChatBlocking(message, sendBtn);
    }
}

async function sendChatStreaming(message, sendBtn) {
    state.isChatStreaming = true;
    sendBtn.disabled = true;
    sendBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing`;

    const typingEl = appendTypingIndicator();

    try {
        const settings = getModelSettings();
        const response = await fetch("/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                modelSettings: settings,
            }),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || "Streaming failed");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamingDiv = null;
        let fullText = "";

        removeTypingIndicator();
        sendBtn.innerHTML = `<i class="fa-solid fa-stop"></i> Streaming`;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                try {
                    const payload = JSON.parse(line.slice(6));

                    if (payload.error) {
                        appendChatMessage("error", payload.error);
                        break;
                    }

                    if (payload.done) {
                        if (streamingDiv) {
                            const finalText = payload.full || fullText;
                            streamingDiv.innerHTML = `
                                <div class="message-header">
                                    <span>AI</span>
                                    <span class="message-meta"><span class="message-time">${formatMessageTimestamp()}</span><button class="msg-copy-btn" type="button"><i class="fa-regular fa-copy"></i> Copy</button></span>
                                </div>
                                <span class="msg-body">${renderMarkdown(finalText)}</span>
                            `;
                            streamingDiv.removeAttribute("data-streaming");
                            attachCopyMessageAction(streamingDiv);
                        }
                        loadStats();
                        break;
                    }

                    if (payload.token) {
                        fullText += payload.token;
                        if (!streamingDiv) {
                            const chatBox = $("#chat-box");
                            streamingDiv = document.createElement("div");
                            streamingDiv.className = "message ai";
                            streamingDiv.dataset.streaming = "true";
                            streamingDiv.innerHTML = `
                                <div class="message-header">
                                    <span>AI</span>
                                    <span class="message-meta"><span class="message-time">${formatMessageTimestamp()}</span></span>
                                </div>
                                <span class="msg-body"></span>
                            `;
                            chatBox.appendChild(streamingDiv);
                        }
                        const bodySpan = streamingDiv.querySelector(".msg-body");
                        if (bodySpan) bodySpan.textContent = fullText;
                        const chatBox = $("#chat-box");
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                } catch (e) { }
            }
        }

    } catch (error) {
        removeTypingIndicator();
        appendChatMessage("error", error.message);
        showToast(error.message, "error");
    } finally {
        state.isChatStreaming = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Send`;
    }
}

async function sendChatBlocking(message, sendBtn) {
    sendBtn.disabled = true;
    showLoader(true, "Generating Response...");
    appendTypingIndicator();

    try {
        const settings = getModelSettings();
        const data = await apiRequest("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, modelSettings: settings }),
        });
        removeTypingIndicator();
        appendChatMessage("ai", data.response);
        loadStats();
    } catch (error) {
        removeTypingIndicator();
        appendChatMessage("error", error.message);
        showToast(error.message, "error");
    } finally {
        sendBtn.disabled = false;
        showLoader(false);
    }
}

function initChat() {
    const sendBtn = $("#chat-send");
    const chatInput = $("#chat-input");
    if (sendBtn) sendBtn.addEventListener("click", sendChatMessage);
    if (chatInput) {
        chatInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendChatMessage();
            }
        });
        chatInput.addEventListener("input", function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
            if (this.value === '') {
                this.style.height = 'auto';
            }
        });
    }
}

// ── PDF Upload ─────────────────────────────────────────────────────────────────

async function uploadPdf(file) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showToast("Please upload a valid PDF file.", "error");
        return;
    }

    const MAX_SIZE = 32 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
        showToast("File too large. Maximum size is 32 MB.", "error");
        return;
    }

    const fileKey = `${file.name}-${file.size}`;
    if (state.activeRequests.has(fileKey)) {
        showToast("This PDF is already being uploaded.", "error");
        return;
    }

    state.activeRequests.add(fileKey);
    const formData = new FormData();
    formData.append("file", file);

    const progressBar = $("#upload-progress-bar");
    const progressFill = $("#upload-progress-fill");
    if (progressBar) progressBar.classList.remove("hidden");
    if (progressFill) progressFill.style.width = "0%";

    try {
        showLoader(true, "Uploading PDF...");

        let progress = 0;
        const progressInterval = setInterval(() => {
            progress = Math.min(progress + 15, 85);
            if (progressFill) progressFill.style.width = `${progress}%`;
        }, 300);

        const response = await fetch("/upload-pdf", { method: "POST", body: formData });
        clearInterval(progressInterval);
        if (progressFill) progressFill.style.width = "100%";

        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Upload failed");
        }

        state.pdfContent = data.content;
        state.pdfDocumentId = data.stored_as;
        const pdfText = $("#pdf-text");
        if (pdfText) pdfText.value = data.content;
        const charCount = data.char_count || data.content.length;
        const meta = $("#pdf-meta");
        if (meta) {
            meta.innerHTML = `<i class="fa-solid fa-file-pdf"></i> Uploaded: ${data.filename} &nbsp;·&nbsp; ${charCount.toLocaleString()} characters extracted`;
            meta.classList.remove("hidden");
        }
        const analyzeBtn = $("#analyze-pdf");
        if (analyzeBtn) analyzeBtn.disabled = false;
        const askDocumentBtn = $("#ask-document");
        if (askDocumentBtn) askDocumentBtn.disabled = false;
        
        showToast("PDF uploaded and text extracted successfully.", "success");
        loadStats();

        setTimeout(() => {
            if (progressBar) progressBar.classList.add("hidden");
        }, 800);

    } catch (error) {
        if (progressBar) progressBar.classList.add("hidden");
        showToast(error.message, "error");
    } finally {
        state.activeRequests.delete(fileKey);
        showLoader(false);
    }
}

function initPdfUpload() {
    const fileInput = $("#pdf-file");
    const uploadZone = $("#upload-zone");
    const browsePdf = $("#browse-pdf");

    if (browsePdf && fileInput) browsePdf.addEventListener("click", () => fileInput.click());
    if (fileInput) fileInput.addEventListener("change", (event) => uploadPdf(event.target.files[0]));

    if (uploadZone) {
        uploadZone.addEventListener("dragover", (event) => {
            event.preventDefault();
            uploadZone.classList.add("dragover");
        });
        uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
        uploadZone.addEventListener("drop", (event) => {
            event.preventDefault();
            uploadZone.classList.remove("dragover");
            uploadPdf(event.dataTransfer.files[0]);
        });
        uploadZone.addEventListener("click", (event) => {
            if (event.target.id !== "browse-pdf" && fileInput) fileInput.click();
        });
    }

    const analyzeBtn = $("#analyze-pdf");
    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", async () => {
            const pdfTextEl = $("#pdf-text");
            const content = pdfTextEl ? pdfTextEl.value.trim() : state.pdfContent;
            if (!content) {
                showToast("Upload a PDF first.", "error");
                return;
            }

            if (state.activeRequests.has("analyze-pdf")) return;
            state.activeRequests.add("analyze-pdf");
            analyzeBtn.disabled = true;

            try {
                showLoader(true, "Analyzing Document...");
                const data = await apiRequest("/analyze-pdf", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content }),
                });

                const summaryEl = $("#analysis-summary");
                const keywordsEl = $("#analysis-keywords");
                const insightsEl = $("#analysis-insights");

                if (summaryEl) summaryEl.textContent = data.summary;
                if (keywordsEl) keywordsEl.textContent = data.keywords;
                if (insightsEl) insightsEl.textContent = data.insights;
                showToast("PDF analysis complete.", "success");
            } catch (error) {
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("analyze-pdf");
                analyzeBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    const askDocumentBtn = $("#ask-document");
    if (askDocumentBtn) {
        askDocumentBtn.addEventListener("click", async () => {
            const questionInput = $("#document-question");
            const question = questionInput ? questionInput.value.trim() : "";
            if (!state.pdfDocumentId) {
                showToast("Upload a PDF first.", "error");
                return;
            }
            if (!question) {
                showToast("Enter a question about the uploaded PDF.", "error");
                return;
            }

            askDocumentBtn.disabled = true;
            const answerEl = $("#document-answer");
            const sourcesEl = $("#document-sources");
            if (answerEl) answerEl.textContent = "";
            if (sourcesEl) sourcesEl.replaceChildren();

            try {
                showLoader(true, "Retrieving Evidence...");
                const data = await apiRequest("/document-ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ stored_as: state.pdfDocumentId, question }),
                });

                if (answerEl) answerEl.textContent = data.answer;
                if (sourcesEl) {
                    data.sources.forEach((source, index) => {
                        const item = document.createElement("article");
                        item.className = "document-source";
                        const heading = document.createElement("strong");
                        heading.textContent = `[${index + 1}] ${source.filename} — Page ${source.page}`;
                        const excerpt = document.createElement("p");
                        excerpt.textContent = source.excerpt;
                        item.append(heading, excerpt);
                        sourcesEl.appendChild(item);
                    });
                }
            } catch (error) {
                if (answerEl) answerEl.textContent = error.message;
                showToast(error.message, "error");
            } finally {
                askDocumentBtn.disabled = false;
                showLoader(false);
            }
        });
    }
}

// ── Research Agents ────────────────────────────────────────────────────────────

function initAgents() {
    document.querySelectorAll(".agent-card").forEach((card) => {
        card.addEventListener("click", () => {
            document.querySelectorAll(".agent-card").forEach((item) => item.classList.remove("active"));
            card.classList.add("active");
            state.selectedAgent = card.dataset.agent;
            const citationFormatRow = $("#citation-format-row");
            if (citationFormatRow) citationFormatRow.classList.toggle("hidden", state.selectedAgent !== "citation");
        });
    });

    const runBtn = $("#run-agent");
    if (runBtn) {
        runBtn.addEventListener("click", async () => {
            const agentInput = $("#agent-input");
            const content = agentInput ? agentInput.value.trim() : "";
            if (!content) {
                showToast("Enter content for the agent.", "error");
                return;
            }

            if (state.activeRequests.has("agent")) return;
            state.activeRequests.add("agent");
            runBtn.disabled = true;

            const payload = { agent: state.selectedAgent, content };
            const citationFormat = $("#citation-format");
            if (state.selectedAgent === "citation" && citationFormat) {
                payload.format = citationFormat.value;
            }

            const agentLabels = {
                research: "Generating Research...",
                summary: "Summarizing Content...",
                citation: "Generating Citations...",
                report: "Generating Report...",
            };

            try {
                showLoader(true, agentLabels[state.selectedAgent] || "Processing...");
                const data = await apiRequest("/agent", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const outputEl = $("#agent-output");
                if (outputEl) outputEl.textContent = data.result;
                showToast(`${data.agent} agent completed.`, "success");
            } catch (error) {
                const outputEl = $("#agent-output");
                if (outputEl) outputEl.textContent = `Error: ${error.message}`;
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("agent");
                runBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    const copyAgentBtn = $("#copy-agent-output");
    if (copyAgentBtn) {
        copyAgentBtn.addEventListener("click", () => {
            const outputEl = $("#agent-output");
            const text = outputEl ? outputEl.textContent : "";
            if (text && text !== "Select an agent and run it to see results.") {
                navigator.clipboard.writeText(text).then(() => showToast("Output copied to clipboard!", "success"));
            } else {
                showToast("No output to copy.", "error");
            }
        });
    }
}

// ── Generators ───────────────────────────────────────────────────────────────

function initGenerators() {
    // Report Generator
    const genReportBtn = $("#generate-report");
    if (genReportBtn) {
        genReportBtn.addEventListener("click", async () => {
            const inputEl = $("#report-input");
            const content = inputEl ? inputEl.value.trim() : "";
            if (!content) {
                showToast("Enter report content or topic.", "error");
                return;
            }
            if (state.activeRequests.has("report")) return;
            state.activeRequests.add("report");
            genReportBtn.disabled = true;
            const status = $("#report-status");
            const download = $("#report-download");

            try {
                showLoader(true, "Generating Report...");
                if (status) status.textContent = "Generating structured academic report sections...";
                if (download) download.classList.add("hidden");

                const data = await apiRequest("/generate-report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content }),
                });

                if (status) status.textContent = data.message;
                if (download) {
                    download.href = data.download_url;
                    download.innerHTML = `<i class="fa-solid fa-download"></i> Download PDF`;
                    download.classList.remove("hidden");
                }
                showToast("PDF Report generated successfully.", "success");
                loadStats();
            } catch (error) {
                if (status) status.textContent = `Error: ${error.message}`;
                if (download) download.classList.add("hidden");
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("report");
                genReportBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    // DOCX Generator
    const genDocxBtn = $("#generate-docx");
    if (genDocxBtn) {
        genDocxBtn.addEventListener("click", async () => {
            const inputEl = $("#docx-input");
            const content = inputEl ? inputEl.value.trim() : "";
            if (!content) {
                showToast("Enter report content or topic.", "error");
                return;
            }
            if (state.activeRequests.has("docx")) return;
            state.activeRequests.add("docx");
            genDocxBtn.disabled = true;
            const status = $("#docx-status");
            const download = $("#docx-download");

            try {
                showLoader(true, "Generating Document...");
                if (status) status.textContent = "Generating structured academic DOCX report...";
                if (download) download.classList.add("hidden");

                const data = await apiRequest("/generate-docx", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content }),
                });

                if (status) status.textContent = data.message;
                if (download) {
                    download.href = data.download_url;
                    download.innerHTML = `<i class="fa-solid fa-download"></i> Download DOCX`;
                    download.classList.remove("hidden");
                }
                showToast("DOCX Report generated successfully.", "success");
                loadStats();
            } catch (error) {
                if (status) status.textContent = `Error: ${error.message}`;
                if (download) download.classList.add("hidden");
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("docx");
                genDocxBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    // PPT Generator
    const genPptBtn = $("#generate-ppt");
    if (genPptBtn) {
        genPptBtn.addEventListener("click", async () => {
            const titleEl = $("#ppt-title");
            const contentEl = $("#ppt-content");
            const title = titleEl ? titleEl.value.trim() : "";
            const content = contentEl ? contentEl.value.trim() : "";

            if (!title || !content) {
                showToast("Enter both title and content.", "error");
                return;
            }
            if (state.activeRequests.has("ppt")) return;
            state.activeRequests.add("ppt");
            genPptBtn.disabled = true;
            const status = $("#ppt-status");
            const download = $("#ppt-download");

            try {
                showLoader(true, "Generating Presentation...");
                if (status) status.textContent = "Generating 10-slide academic presentation...";
                if (download) download.classList.add("hidden");

                const data = await apiRequest("/generate-ppt", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, content }),
                });

                if (status) status.textContent = data.message;
                if (download) {
                    download.href = data.download_url;
                    download.innerHTML = `<i class="fa-solid fa-download"></i> Download Presentation`;
                    download.classList.remove("hidden");
                }
                showToast("Presentation generated successfully.", "success");
                loadStats();
            } catch (error) {
                if (status) status.textContent = `Error: ${error.message}`;
                if (download) download.classList.add("hidden");
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("ppt");
                genPptBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    // Citation Generator
    const genCitationsBtn = $("#generate-citations");
    if (genCitationsBtn) {
        genCitationsBtn.addEventListener("click", async () => {
            const titleEl = $("#cite-title");
            const authorEl = $("#cite-author");
            const yearEl = $("#cite-year");
            const journalEl = $("#cite-journal");
            const publisherEl = $("#cite-publisher");
            
            const title = titleEl ? titleEl.value.trim() : "";
            const author = authorEl ? authorEl.value.trim() : "";
            const year = yearEl ? yearEl.value.trim() : "";
            const journal = journalEl ? journalEl.value.trim() : "";
            const publisher = publisherEl ? publisherEl.value.trim() : "";

            if (!title) {
                showToast("Source title is required.", "error");
                if (titleEl) titleEl.focus();
                return;
            }

            if (year && !/^\d{4}$/.test(year)) {
                showToast("Year must be a 4-digit number (e.g., 2024).", "error");
                if (yearEl) yearEl.focus();
                return;
            }

            if (state.activeRequests.has("citations")) return;
            state.activeRequests.add("citations");
            genCitationsBtn.disabled = true;

            const targets = ["cite-apa-val", "cite-ieee-val", "cite-mla-val", "cite-chicago-val"];
            targets.forEach(id => {
                const el = $(`#${id}`);
                if (el) el.textContent = "Generating...";
            });

            try {
                showLoader(true, "Generating Citations...");
                const data = await apiRequest("/generate-citations", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, author, year, journal, publisher }),
                });

                const apaEl = $("#cite-apa-val");
                const ieeeEl = $("#cite-ieee-val");
                const mlaEl = $("#cite-mla-val");
                const chicagoEl = $("#cite-chicago-val");

                if (apaEl) apaEl.textContent = data.apa || "—";
                if (ieeeEl) ieeeEl.textContent = data.ieee || "—";
                if (mlaEl) mlaEl.textContent = data.mla || "—";
                if (chicagoEl) chicagoEl.textContent = data.chicago || "—";

                showToast("Citations generated successfully.", "success");
                loadStats();
            } catch (error) {
                targets.forEach(id => {
                    const el = $(`#${id}`);
                    if (el) el.textContent = "—";
                });
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("citations");
                genCitationsBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    document.querySelectorAll(".btn-copy").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.target;
            const targetEl = $(`#${targetId}`);
            const text = targetEl ? targetEl.textContent : "";
            if (text && text !== "—" && text !== "Generating...") {
                navigator.clipboard.writeText(text).then(() => {
                    const original = btn.innerHTML;
                    btn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
                    btn.style.color = "var(--accent)";
                    setTimeout(() => {
                        btn.innerHTML = original;
                        btn.style.color = "";
                    }, 1500);
                    showToast("Citation copied to clipboard!", "success");
                }).catch(() => showToast("Copy failed.", "error"));
            } else {
                showToast("No citation content to copy.", "error");
            }
        });
    });
}

// ── Research Tools ─────────────────────────────────────────────────────────────

function initResearchTools() {
    const toolConfigs = {
        topic_generator: {
            label: "Research Domain / Keywords",
            placeholder: "e.g., quantum computing, deep learning in healthcare..."
        },
        gap_finder: {
            label: "Research Topic / Literature Summary",
            placeholder: "Enter details about the topic or a summary of existing studies..."
        },
        lit_review: {
            label: "Research Topic / Source Materials",
            placeholder: "Enter details about your topic or raw findings..."
        },
        abstract_generator: {
            label: "Research Findings / Paper Summary",
            placeholder: "Enter key points, objectives, methods, and results..."
        }
    };

    document.querySelectorAll(".tool-select-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tool-select-btn").forEach(item => item.classList.remove("active"));
            btn.classList.add("active");
            state.selectedEnhancementTool = btn.dataset.tool;

            const config = toolConfigs[state.selectedEnhancementTool];
            if (config) {
                const labelEl = $("#enhancement-label");
                const inputEl = $("#enhancement-input");
                if (labelEl) labelEl.textContent = config.label;
                if (inputEl) inputEl.placeholder = config.placeholder;
            }
        });
    });

    const runBtn = $("#run-enhancement");
    if (runBtn) {
        runBtn.addEventListener("click", async () => {
            const inputEl = $("#enhancement-input");
            const content = inputEl ? inputEl.value.trim() : "";
            if (!content) {
                showToast("Please enter the required inputs.", "error");
                return;
            }

            if (state.activeRequests.has("enhancement")) return;
            state.activeRequests.add("enhancement");
            runBtn.disabled = true;

            const toolLabels = {
                topic_generator: "Generating Topics...",
                gap_finder: "Finding Research Gaps...",
                lit_review: "Writing Literature Review...",
                abstract_generator: "Generating Abstract...",
            };

            try {
                showLoader(true, toolLabels[state.selectedEnhancementTool] || "Processing...");
                const data = await apiRequest("/research-enhancements", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        tool: state.selectedEnhancementTool,
                        content: content
                    })
                });

                const outputEl = $("#enhancement-output");
                if (outputEl) outputEl.textContent = data.result;
                showToast("Content generated successfully.", "success");
            } catch (error) {
                const outputEl = $("#enhancement-output");
                if (outputEl) outputEl.textContent = `Error: ${error.message}`;
                showToast(error.message, "error");
            } finally {
                state.activeRequests.delete("enhancement");
                runBtn.disabled = false;
                showLoader(false);
            }
        });
    }

    const copyBtn = $("#copy-enhancement");
    if (copyBtn) {
        copyBtn.addEventListener("click", () => {
            const outputEl = $("#enhancement-output");
            const text = outputEl ? outputEl.textContent : "";
            if (text && text.trim() !== "" && !text.startsWith("Select a tool") && !text.startsWith("Error:")) {
                navigator.clipboard.writeText(text).then(() => showToast("Output copied to clipboard!", "success"));
            } else {
                showToast("No content to copy.", "error");
            }
        });
    }
}

// ── Statistics ─────────────────────────────────────────────────────────────────

async function loadStats() {
    const now = Date.now();
    if (state.statsCache && (now - state.lastStatsFetch < 10000)) {
        updateStatsUI(state.statsCache);
        return;
    }

    try {
        const response = await fetch("/stats");
        if (response.ok) {
            const data = await response.json();
            state.statsCache = data;
            state.lastStatsFetch = now;
            updateStatsUI(data);
        }
    } catch (err) {
        console.error("Failed to load statistics:", err);
    }
}

function updateStatsUI(data) {
    const statMap = {
        "#totalChats": data.total_chats,
        "#pdfUploads": data.pdf_uploads,
        "#reportsGenerated": data.reports_generated,
        "#docxGenerated": data.docx_generated,
        "#citationsGenerated": data.citations_generated,
        "#pptGenerated": data.ppt_generated,
    };

    let anyChanged = false;
    for (const [selector, value] of Object.entries(statMap)) {
        const el = $(selector);
        if (el) {
            const targetVal = value || 0;
            if (el.getAttribute("data-target") != targetVal) {
                el.setAttribute("data-target", targetVal);
                anyChanged = true;
            }
        }
    }
    if (anyChanged) animateCounters();
}

function animateCounters() {
    const counters = document.querySelectorAll('.counter');
    counters.forEach(counter => {
        const target = +counter.getAttribute('data-target');
        const count = +counter.innerText;
        if (count < target) {
            const inc = Math.max(1, Math.ceil((target - count) / 10));
            counter.innerText = count + inc;
            setTimeout(() => {
                animateCounters();
            }, 30);
        } else {
            counter.innerText = target;
        }
    });
}

// ── Chat History ───────────────────────────────────────────────────────────────

async function loadChatHistory() {
    try {
        const response = await fetch("/history");
        const data = await response.json();
        const chatBox = $("#chat-box");
        if (!chatBox) return;
        chatBox.innerHTML = "";

        if (!data.length) {
            const empty = document.createElement("div");
            empty.className = "message ai";
            empty.innerHTML = "<strong>AI:</strong> No chat history found.";
            chatBox.appendChild(empty);
            return;
        }

        data.forEach(chat => {
            appendChatMessage("user", chat.question);
            appendChatMessage("ai", chat.answer);
        });

        chatBox.scrollTop = chatBox.scrollHeight;
        showToast(`Loaded ${data.length} chat(s) from history.`, "success");
    } catch (err) {
        console.error("Failed to load chat history:", err);
        showToast("Failed to load chat history.", "error");
    }
}

// ── Init ───────────────────────────────────────────────────────────────────────

function initLoginModal() {
    const trigger = $("#login-trigger");
    const overlay = $("#auth-overlay");
    const closeBtn = $("#auth-close");
    const form = $("#auth-form");

    if (trigger && overlay) {
        trigger.addEventListener("click", () => {
            overlay.classList.remove("hidden");
            overlay.setAttribute("aria-hidden", "false");
        });
    }

    if (closeBtn && overlay) {
        closeBtn.addEventListener("click", () => {
            overlay.classList.add("hidden");
            overlay.setAttribute("aria-hidden", "true");
        });
    }

    if (overlay) {
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                overlay.classList.add("hidden");
                overlay.setAttribute("aria-hidden", "true");
            }
        });
    }

    if (form) {
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            showToast("This is a frontend-only sign-in mockup.", "success");
            if (overlay) {
                overlay.classList.add("hidden");
                overlay.setAttribute("aria-hidden", "true");
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initSettings();
    initChat();
    initPdfUpload();
    initAgents();
    initGenerators();
    initResearchTools();
    initLoginModal();

    loadStats();

    const historyBtn = $("#load-history-btn");
    if (historyBtn) {
        historyBtn.addEventListener("click", loadChatHistory);
    }
    setTimeout(updateNavIndicator, 100);
});
