// Ghidorah Three-Headed Dragon Dashboard JavaScript

class GhidorahChat {
    constructor() {
        this.conversationId = null;
        this.messageCount = 0;
        this.lastRole = null;
        this.lastResponse = null;
        this.isLoading = false;
        this.taskStartTime = null;
        this.timerInterval = null;
        this.discordConnected = false;
        this.discordWebhook = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadRoles();
        this.loadDiscordSettings();
    }

    initializeElements() {
        this.elements = {
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            handoffBtn: document.getElementById('handoff-btn'),
            handoffControls: document.getElementById('handoff-controls'),
            roleSelect: document.getElementById('role-select'),
            headToHeadMode: document.getElementById('head-to-head-mode'),
            chatMessages: document.getElementById('chat-messages'),
            conversationId: document.getElementById('conversation-id'),
            messageCount: document.getElementById('message-count'),
            lastRole: document.getElementById('last-role'),
            clearBtn: document.getElementById('clear-btn'),
            loadingIndicator: document.getElementById('loading-indicator'),
            taskTimer: document.getElementById('task-timer'),
            timerDisplay: document.getElementById('timer-display'),
            taskTime: document.getElementById('task-time'),
            discordWebhook: document.getElementById('discord-webhook'),
            connectDiscord: document.getElementById('connect-discord')
        };
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.elements.handoffBtn.addEventListener('click', () => this.performHandoff());
        this.elements.clearBtn.addEventListener('click', () => this.clearConversation());
        this.elements.roleSelect.addEventListener('change', () => this.onRoleChange());
        this.elements.connectDiscord.addEventListener('click', () => this.connectDiscord(this.elements.discordWebhook.value));
        this.elements.discordWebhook.value = this.discordWebhook || '';
    }

    async loadRoles() {
        try {
            const response = await fetch('/roles');
            const data = await response.json();
            
            // Update role select with available roles
            this.elements.roleSelect.innerHTML = '';
            data.roles.forEach(role => {
                const option = document.createElement('option');
                option.value = role.id;
                option.textContent = role.name;
                this.elements.roleSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load roles:', error);
            this.addSystemMessage('[ SYSTEM ERROR - FAILED TO LOAD ROLES ]');
        }
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || this.isLoading) return;

        this.setLoading(true);
        this.startTimer();
        this.elements.messageInput.value = '';

        // Add user message to chat
        this.addMessage(message, 'user');
        this.messageCount++;

        try {
            const selectedRole = this.elements.roleSelect.value;
            
            // Handle head-to-head mode
            if (selectedRole === 'head_to_head' || this.elements.headToHeadMode.checked) {
                const selectedHead = prompt('Select starting head (llama, qwen, or gemma):');
                const headMap = {
                    'llama': 'analysis',
                    'qwen': 'code_generation', 
                    'gemma': 'creative_writing'
                };
                
                if (selectedHead && headMap[selectedHead]) {
                    await this.headToHeadChain(message, headMap[selectedHead]);
                    this.messageCount++;
                    this.updateConversationInfo();
                    return;
                }
            }

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: message,
                    role: selectedRole,
                    conversation_id: this.conversationId
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.conversationId = data.conversation_id;
                this.lastRole = data.role;
                
                if (data.mode === 'all_three') {
                    // Handle all-three mode
                    this.addAllThreeResponses(data.all_responses, data);
                } else {
                    // Handle single model response
                    this.lastResponse = data.response;
                    this.addMessage(data.response, 'assistant', {
                        model: data.model,
                        role: data.role,
                        timestamp: data.timestamp,
                        display_name: data.display_name,
                        color: data.color
                    });
                }
                
                // Send to Discord
                await this.sendToDiscord(`**${data.display_name}**: ${data.response}`);
                
                this.messageCount++;
                this.updateConversationInfo();
                this.showHandoffControls();
                
                // Update task time
                if (data.processing_time) {
                    this.updateTaskTime(data.processing_time);
                }
                
                // Add typing effect
                this.typingEffect();
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.addSystemMessage(`[ ERROR: ${error.message} ]`);
        } finally {
            this.setLoading(false);
            this.stopTimer();
        }
    }

    async performHandoff() {
        if (!this.conversationId || !this.lastResponse || this.isLoading) return;

        this.setLoading(true);
        this.hideHandoffControls();

        try {
            const response = await fetch('/handoff', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    current_role: this.lastRole,
                    task_summary: this.lastResponse
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // Add handoff notification
                this.addHandoffMessage(this.lastRole, data.role);
                
                // Add handoff response
                this.addMessage(data.response, 'assistant', {
                    model: data.model,
                    role: data.role,
                    timestamp: data.timestamp,
                    handoff: true
                });
                
                this.lastRole = data.role;
                this.lastResponse = data.response;
                this.messageCount++;
                this.updateConversationInfo();
                
                // Update role selector to show current role
                this.elements.roleSelect.value = data.role;
                
                this.typingEffect();
            } else {
                throw new Error(data.error || 'Handoff failed');
            }
        } catch (error) {
            console.error('Handoff error:', error);
            this.addSystemMessage(`[ HANDOFF ERROR: ${error.message} ]`);
        } finally {
            this.setLoading(false);
        }
    }

    addMessage(content, type, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        let modelInfo = '';
        
        if (type === 'assistant') {
            const modelName = metadata.display_name || this.getModelDisplayName(metadata.model);
            const modelColor = metadata.color || this.getModelColor(metadata.model);
            modelInfo = `
                <div class="flex items-center gap-2 mb-2">
                    <span class="llm-indicator" style="background: rgba(${this.hexToRgb(modelColor)}, 0.2); border: 1px solid ${modelColor}; color: ${modelColor}; box-shadow: 0 0 10px ${modelColor};">${modelName}</span>
                    <span class="role-badge ${metadata.role}">${metadata.role.replace('_', ' ')}</span>
                    ${metadata.handoff ? '<span class="role-badge" style="background: linear-gradient(135deg, #ffff00, #cccc00); color: #000;">HANDOFF</span>' : ''}
                </div>
            `;
        }
        
        messageDiv.innerHTML = `
            ${modelInfo}
            <div class="flex justify-between items-start mb-1">
                <span class="text-xs opacity-60">${type.toUpperCase()} ${timestamp}</span>
            </div>
            <div class="text-sm leading-relaxed">${this.escapeHtml(content)}</div>
        `;
        
        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAllThreeResponses(responses, metadata) {
        // Add a header for all-three mode
        const headerDiv = document.createElement('div');
        headerDiv.className = 'message all-three-header';
        headerDiv.innerHTML = `
            <div class="text-center py-3 mb-4">
                <span class="text-cyber-yellow font-black text-lg animate-pulse">🐉 ALL THREE HEADS RESPONDING 🐉</span>
            </div>
        `;
        this.elements.chatMessages.appendChild(headerDiv);

        // Add each model's response
        Object.entries(responses).forEach(([model, response], index) => {
            setTimeout(() => {
                this.addMessage(response.response, 'assistant', {
                    model: response.model,
                    role: metadata.role,
                    timestamp: metadata.timestamp,
                    display_name: response.display_name,
                    color: response.color,
                    all_three: true
                });
            }, index * 500); // Stagger the appearance
        });

        // Store the last response for handoff (use the first model's response)
        const firstModel = Object.keys(responses)[0];
        this.lastResponse = responses[firstModel].response;
    }

    addHandoffMessage(fromRole, toRole) {
        const handoffDiv = document.createElement('div');
        handoffDiv.className = 'message handoff';
        handoffDiv.innerHTML = `
            <div class="text-center py-2">
                <span class="text-yellow-400 font-bold animate-pulse">
                    [ HANDOFF: ${fromRole.replace('_', ' ').toUpperCase()} → ${toRole.replace('_', ' ').toUpperCase()} ]
                </span>
            </div>
        `;
        
        this.elements.chatMessages.appendChild(handoffDiv);
        this.scrollToBottom();
    }

    addSystemMessage(content) {
        const systemDiv = document.createElement('div');
        systemDiv.className = 'text-center text-cyber-cyan opacity-60 my-2';
        systemDiv.innerHTML = `<p class="animate-pulse-cyan">${content}</p>`;
        
        this.elements.chatMessages.appendChild(systemDiv);
        this.scrollToBottom();
    }

    showHandoffControls() {
        if (this.lastResponse) {
            this.elements.handoffControls.classList.remove('hidden');
            // Add glow effect to handoff button
            this.elements.handoffBtn.classList.add('animate-glow');
        }
    }

    hideHandoffControls() {
        this.elements.handoffControls.classList.add('hidden');
        this.elements.handoffBtn.classList.remove('animate-glow');
    }

    onRoleChange() {
        // Optional: Add visual feedback when role changes
        const selectedRole = this.elements.roleSelect.value;
        this.elements.roleSelect.classList.add('animate-glow');
        setTimeout(() => {
            this.elements.roleSelect.classList.remove('animate-glow');
        }, 1000);
    }

    updateConversationInfo() {
        this.elements.conversationId.textContent = this.conversationId ? 
            this.conversationId.substring(0, 8) + '...' : 'NONE';
        this.elements.messageCount.textContent = this.messageCount;
        this.elements.lastRole.textContent = this.lastRole ? 
            this.lastRole.replace('_', ' ').toUpperCase() : 'NONE';
    }

    startTimer() {
        this.taskStartTime = Date.now();
        this.elements.taskTimer.classList.remove('hidden');
        
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        
        this.timerInterval = setInterval(() => {
            const elapsed = ((Date.now() - this.taskStartTime) / 1000).toFixed(1);
            this.elements.timerDisplay.textContent = `${elapsed}s`;
        }, 100);
    }

    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }

    updateTaskTime(processingTime) {
        this.elements.taskTime.textContent = `${processingTime.toFixed(1)}s`;
    }

    getModelDisplayName(model) {
        const names = {
            'llama3.2:3b': 'LLAMA 3.2',
            'qwen2.5-coder:1.5b': 'QWEN 2.5 CODER',
            'gemma2:2b': 'GEMMA2'
        };
        return names[model] || model;
    }

    getModelColor(model) {
        const colors = {
            'llama3.2:3b': '#00ffff',
            'qwen2.5-coder:1.5b': '#ff0040',
            'gemma2:2b': '#ffff00'
        };
        return colors[model] || '#00ffff';
    }

    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? 
            `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : 
            '0, 255, 255';
    }

    clearConversation() {
        if (confirm('Are you sure you want to clear the conversation?')) {
            this.conversationId = null;
            this.messageCount = 0;
            this.lastRole = null;
            this.lastResponse = null;
            
            // Reset timer
            this.stopTimer();
            this.elements.taskTimer.classList.add('hidden');
            this.elements.taskTime.textContent = '0.0s';
            
            this.elements.chatMessages.innerHTML = `
                <div class="text-center text-cyber-cyan opacity-60">
                    <p class="animate-pulse-cyan">[ GHIDORAH SYSTEM READY - AWAITING INPUT ]</p>
                </div>
            `;
            
            this.updateConversationInfo();
            this.hideHandoffControls();
            
            // Add clear animation
            this.elements.chatMessages.style.animation = 'glitch 0.5s ease-in-out';
            setTimeout(() => {
                this.elements.chatMessages.style.animation = '';
            }, 500);
        }
    }

    setLoading(loading) {
        this.isLoading = loading;
        if (loading) {
            this.elements.loadingIndicator.classList.remove('hidden');
            this.elements.sendBtn.disabled = true;
            this.elements.sendBtn.classList.add('opacity-50');
        } else {
            this.elements.loadingIndicator.classList.add('hidden');
            this.elements.sendBtn.disabled = false;
            this.elements.sendBtn.classList.remove('opacity-50');
        }
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    typingEffect() {
        // Add a subtle typing indicator effect to the last message
        const messages = this.elements.chatMessages.querySelectorAll('.message.assistant');
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const content = lastMessage.querySelector('.text-sm');
            
            // Add cursor animation temporarily
            const cursor = document.createElement('span');
            cursor.className = 'terminal-cursor';
            content.appendChild(cursor);
            
            setTimeout(() => {
                cursor.remove();
            }, 1000);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Add some cyberpunk effects
    addGlitchEffect() {
        document.body.classList.add('glitch');
        setTimeout(() => {
            document.body.classList.remove('glitch');
        }, 300);
    }

    // Initialize with some cyberpunk flair
    loadDiscordSettings() {
        const saved = localStorage.getItem('discord_webhook');
        if (saved) {
            this.discordWebhook = saved;
            this.discordConnected = true;
        }
    }

    async connectDiscord(webhookUrl) {
        try {
            this.discordWebhook = webhookUrl;
            this.discordConnected = true;
            localStorage.setItem('discord_webhook', webhookUrl);
            this.addSystemMessage('[ DISCORD CONNECTED ]');
        } catch (error) {
            this.addSystemMessage(`[ DISCORD ERROR: ${error.message} ]`);
        }
    }

    async sendToDiscord(content) {
        if (!this.discordConnected || !this.discordWebhook) return;
        
        try {
            await fetch(this.discordWebhook, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
        } catch (error) {
            console.error('Discord error:', error);
        }
    }

    async headToHeadChain(message, selectedHead) {
        const headOrder = ['llama3.2:3b', 'qwen2.5-coder:1.5b', 'gemma2:2b'];
        const responses = [];
        
        for (const model of headOrder) {
            this.setLoading(true);
            this.startTimer();
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: message,
                        role: selectedHead,
                        conversation_id: this.conversationId
                    })
                });
                
                const data = await response.json();
                responses.push(data.response);
                
                this.addMessage(data.response, 'assistant', {
                    model: data.model,
                    role: data.role,
                    timestamp: data.timestamp,
                    display_name: data.display_name,
                    color: data.color
                });
                
                // Send to Discord
                await this.sendToDiscord(`**${data.display_name}**: ${data.response}`);
                
                // Pass to next head
                if (responses.length < 3) {
                    message = `Previous response from ${data.display_name}: ${data.response}`;
                }
                
            } catch (error) {
                this.addSystemMessage(`[ ERROR: ${error.message} ]`);
            } finally {
                this.setLoading(false);
                this.stopTimer();
            }
        }
        
        return responses;
    }

    initializeCyberpunkEffects() {
        // Add random glitch effects occasionally
        setInterval(() => {
            if (Math.random() < 0.05) {
                this.addGlitchEffect();
            }
        }, 10000);

        // Add matrix rain effect
        const matrixRain = document.createElement('div');
        matrixRain.className = 'matrix-rain';
        document.body.appendChild(matrixRain);
    }
}

// Initialize the chat application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const chat = new GhidorahChat();
    chat.initializeCyberpunkEffects();
    
    // Add some initial cyberpunk styling
    document.body.classList.add('neon-text');
    
    // Focus on input
    document.getElementById('message-input').focus();
});

// Add some keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to clear conversation
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('clear-btn').click();
    }
    
    // Ctrl/Cmd + H to perform handoff
    if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
        e.preventDefault();
        const handoffBtn = document.getElementById('handoff-btn');
        if (!handoffBtn.classList.contains('hidden')) {
            handoffBtn.click();
        }
    }
    
    // Tab to cycle through roles
    if (e.key === 'Tab' && e.target.id !== 'message-input') {
        e.preventDefault();
        const roleSelect = document.getElementById('role-select');
        const options = roleSelect.options;
        const currentIndex = roleSelect.selectedIndex;
        const nextIndex = (currentIndex + 1) % options.length;
        roleSelect.selectedIndex = nextIndex;
        roleSelect.dispatchEvent(new Event('change'));
    }
});
