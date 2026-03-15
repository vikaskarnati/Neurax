document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatWindow = document.getElementById('chat-window');
    const navLinks = document.querySelectorAll('.nav-link');
    const overlay = document.getElementById('overlay');
    const overlayTitle = document.getElementById('overlay-title');
    const overlayBody = document.getElementById('overlay-body');
    const closeBtn = document.getElementById('close-btn');
    const newChatBtn = document.querySelector('.new-chat-btn');
    const voiceBtn = document.getElementById('voice-input-btn');
    const chatList = document.getElementById('chat-list');
    const modeIndicator = document.getElementById('mode-indicator');
    const queryModeBtns = document.querySelectorAll('.query-mode-btn');
    const stopBtn = document.getElementById('stop-btn');
    const imageInputBtn = document.getElementById('image-input-btn');
    const imageInput = document.getElementById('image-input');

    // Hospital Finder Elements
    const hospitalSearchForm = document.getElementById('hospital-search-form');
    const locationInput = document.getElementById('location-input');
    const searchHospitalsBtn = document.getElementById('search-hospitals-btn');
    const useCurrentLocationBtn = document.getElementById('use-current-location-btn');

    // Appointment Modal Elements
    const appointmentModal = document.getElementById('appointment-modal');
    const appointmentCloseBtn = document.getElementById('appointment-close-btn');
    const appointmentForm = document.getElementById('appointment-form');
    const appointmentSuccess = document.getElementById('appointment-success');
    const myAppointmentsBtn = document.getElementById('my-appointments-btn');
    const myAppointmentsModal = document.getElementById('my-appointments-modal');
    const myAppointmentsCloseBtn = document.getElementById('my-appointments-close-btn');
    const appointmentsContainer = document.getElementById('appointments-container');

    let chats = [];           // array of { session_id, label, messages[] }
    let currentChat = [];     // messages in the active view
    let currentQueryType = 'general';
    let isStreaming = false;
    let streamController = null;
    let selectedImage = null;
    let selectedHospital = null;

    // ─────────────────────────────────────────────────────────────────────
    // PERSISTENT USER ID  — stored in localStorage so it never changes
    // ─────────────────────────────────────────────────────────────────────
    function getOrCreateUserId() {
        let uid = localStorage.getItem('medimind_user_id');
        if (!uid) {
            uid = "user_" + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('medimind_user_id', uid);
            console.log('✅ New user ID created:', uid);
        } else {
            console.log('✅ Loaded existing user ID:', uid);
        }
        return uid;
    }
    const user_id = getOrCreateUserId();

    // ─────────────────────────────────────────────────────────────────────
    // SESSION ID  — a new session per browser tab/visit, saved in sessionStorage
    // Each "New Chat" also generates a fresh session_id
    // ─────────────────────────────────────────────────────────────────────
    // Always generate a brand-new session on every page load
    // This means every reload = fresh chat window, history goes to sidebar only
    function generateNewSessionId() {
        const sid = "session_" + Math.random().toString(36).substr(2, 12);
        sessionStorage.setItem('medimind_session_id', sid);
        return sid;
    }
    let current_session_id = generateNewSessionId();

    // Query type endpoints
    const queryEndpoints = {
        'general':        { url: 'http://127.0.0.1:5000/chat',                 label: '💬 General Chat Mode',           placeholder: 'Type your message...' },
        'general_health': { url: 'http://127.0.0.1:5000/chat/general-health',  label: '🏃 General Health Query Mode',   placeholder: 'Ask about wellness, nutrition, exercise...' },
        'medication':     { url: 'http://127.0.0.1:5000/chat/medication',       label: '💊 Medication Information Mode', placeholder: 'Ask about any medication...' },
        'symptoms':       { url: 'http://127.0.0.1:5000/chat/symptoms',         label: '🩺 Symptom Checker Mode',        placeholder: 'Describe your symptoms...' },
        'hospital_finder':{ url: 'http://127.0.0.1:5000/find-hospitals',        label: '🏥 Hospital Finder Mode',        placeholder: 'Enter location...' }
    };

    // ─────────────────────────────────────────────────────────────────────
    // LOAD ALL HISTORY FROM DATABASE ON PAGE LOAD
    // ─────────────────────────────────────────────────────────────────────
    function loadAllHistory() {
        chatWindow.innerHTML = `
            <div class="message bot-message">
                <div class="avatar"><img src="https://api.dicebear.com/7.x/bottts/svg?seed=medical" alt="Bot"></div>
                <div class="message-content">
                    <span style="opacity:0.6">⏳ Loading your conversations...</span>
                </div>
            </div>`;

        fetch(`http://127.0.0.1:5000/history/${user_id}`)
            .then(res => {
                if (!res.ok) throw new Error('Network error');
                return res.json();
            })
            .then(data => {
                chatWindow.innerHTML = '';
                chatList.innerHTML = ''; // clear sidebar
                chats = [];

                if (data.status === 'success' && data.messages && data.messages.length > 0) {
                    console.log(`✅ Retrieved ${data.total} messages from database`);

                    // ── Put ALL history into the sidebar only — never in chat window ──
                    // Group all messages by session_id for sidebar
                    const sessionMap = {};
                    data.messages.forEach(msg => {
                        const sid = msg.session_id || 'default';
                        if (!sessionMap[sid]) sessionMap[sid] = [];
                        sessionMap[sid].push(msg);
                    });

                    // Build sidebar entries from sessions returned by backend
                    if (data.sessions && data.sessions.length > 0) {
                        data.sessions.forEach((session, index) => {
                            const sessionMessages = sessionMap[session.session_id] || [];
                            chats.push({
                                session_id: session.session_id,
                                label: session.first_message || `Chat ${index + 1}`,
                                messages: sessionMessages
                            });
                            addSessionToSidebar(session, index, sessionMessages);
                        });
                    } else {
                        // Fallback: single group for all messages (old schema, all session_id='default')
                        const allMessages = data.messages;
                        chats.push({ session_id: 'default', label: 'Previous conversations', messages: allMessages });
                        addSessionToSidebar({ session_id: 'default', timestamp: '' }, 0, allMessages);
                    }

                    // ── Chat window starts FRESH — just a welcome back message ──
                    appendMessage('👋 Welcome back! Your previous chats are in the sidebar. How can I help you today?', 'bot');

                } else {
                    // No history at all — fresh user
                    appendMessage('👋 Hello! I\'m your MediMind assistant. How can I help you today?', 'bot');
                }

                chatWindow.scrollTop = chatWindow.scrollHeight;
            })
            .catch(err => {
                console.error('❌ Failed to load history:', err);
                chatWindow.innerHTML = '';
                appendMessage('👋 Hello! I\'m your MediMind assistant. How can I help you today?', 'bot');
            });
    }

    // Render an array of message objects into the chat window
    function renderMessages(messages) {
        messages.forEach(msg => {
            appendMessage(msg.message, msg.sender);
            // Also track in currentChat
            currentChat.push({ sender: msg.sender, text: msg.message });
        });
    }

    // Load a specific session's messages when clicked in sidebar
    function loadSession(sessionIndex) {
        const session = chats[sessionIndex];
        if (!session) return;

        chatWindow.innerHTML = '';
        currentChat = [];

        // Show a header for the session
        const header = document.createElement('div');
        header.style.cssText = 'text-align:center;padding:10px;font-size:12px;color:rgba(139,92,246,0.8);border-bottom:1px dashed rgba(139,92,246,0.2);margin-bottom:10px;';
        header.textContent = `📂 Session: ${session.label.substring(0, 40)}`;
        chatWindow.appendChild(header);

        session.messages.forEach(msg => {
            appendMessage(msg.message, msg.sender);
            currentChat.push({ sender: msg.sender, text: msg.message });
        });

        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // Add a session entry to the sidebar chat list
    function addSessionToSidebar(session, index, messages) {
        const li = document.createElement('li');

        // Build a meaningful label from the first user message
        const firstUserMsg = messages.find(m => m.sender === 'user');
        const label = firstUserMsg
            ? firstUserMsg.message.substring(0, 35) + (firstUserMsg.message.length > 35 ? '...' : '')
            : `Chat ${index + 1}`;

        const msgCount = messages.length;
        const dateStr = session.timestamp
            ? new Date(session.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
            : '';

        li.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:6px;">
                <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;">${label}</span>
                <span style="font-size:10px;opacity:0.5;flex-shrink:0;">${dateStr}</span>
            </div>
            <div style="font-size:11px;opacity:0.45;margin-top:2px;">${msgCount} messages</div>
        `;
        li.title = label;
        li.addEventListener('click', () => loadSession(index));
        chatList.appendChild(li);
    }

    // Add a visual divider between old history and new messages
    function appendSessionDivider(label) {
        const divider = document.createElement('div');
        divider.style.cssText = `
            text-align: center;
            color: rgba(139,92,246,0.5);
            font-size: 11px;
            padding: 8px 0 4px 0;
            border-top: 1px dashed rgba(139,92,246,0.2);
            margin: 8px 0;
            letter-spacing: 1px;
        `;
        divider.textContent = `── ${label} ──`;
        chatWindow.appendChild(divider);
    }

    // ─────────────────────────────────────────────────────────────────────
    // MODE MANAGEMENT
    // ─────────────────────────────────────────────────────────────────────
    function updateMode(mode) {
        currentQueryType = mode;
        const modeInfo = queryEndpoints[mode];
        modeIndicator.textContent = modeInfo.label;
        chatInput.placeholder = modeInfo.placeholder;

        if (mode === 'hospital_finder') {
            hospitalSearchForm.style.display = 'flex';
            chatForm.style.display = 'none';
            locationInput.focus();
        } else {
            hospitalSearchForm.style.display = 'none';
            chatForm.style.display = 'flex';
            chatInput.focus();
        }

        queryModeBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));

        const modeMessages = {
            'general':        'Switched to General Chat mode. Ask me anything!',
            'general_health': 'Switched to General Health Query mode. Ask me about wellness, nutrition, exercise!',
            'medication':     'Switched to Medication Information mode. Ask me about any medication!',
            'symptoms':       'Switched to Symptom Checker mode. Describe your symptoms!',
            'hospital_finder':'Switched to Hospital Finder mode. Enter a location to find nearby hospitals!'
        };

        if (currentChat.length > 0) {
            appendMessage(modeMessages[mode], 'bot');
        }
    }

    queryModeBtns.forEach(btn => btn.addEventListener('click', () => updateMode(btn.dataset.mode)));

    // ─────────────────────────────────────────────────────────────────────
    // NEW CHAT — creates a fresh session ID
    // ─────────────────────────────────────────────────────────────────────
    newChatBtn.addEventListener('click', () => {
        // Save current chat to chats array before clearing
        if (currentChat.length > 0) {
            const existingIndex = chats.findIndex(c => c.session_id === current_session_id);
            if (existingIndex === -1) {
                const firstUserMsg = currentChat.find(m => m.sender === 'user');
                const label = firstUserMsg
                    ? firstUserMsg.text.substring(0, 35)
                    : `Chat ${chats.length + 1}`;
                chats.push({
                    session_id: current_session_id,
                    label,
                    messages: currentChat.map(m => ({ sender: m.sender, message: m.text, query_type: 'general', timestamp: '', session_id: current_session_id }))
                });
                addSessionToSidebar({ session_id: current_session_id, timestamp: new Date().toISOString() }, chats.length - 1, chats[chats.length - 1].messages);
            }
        }

        // Generate a brand new session ID
        current_session_id = "session_" + Math.random().toString(36).substr(2, 12);
        sessionStorage.setItem('medimind_session_id', current_session_id);

        currentChat = [];
        currentQueryType = 'general';
        chatWindow.innerHTML = '';
        updateMode('general');
        appendMessage('👋 Hello! I\'m your MediMind assistant. How can I help you today?', 'bot');
        console.log('✅ New session started:', current_session_id);
    });

    // ─────────────────────────────────────────────────────────────────────
    // HOSPITAL FINDER
    // ─────────────────────────────────────────────────────────────────────
    searchHospitalsBtn.addEventListener('click', () => {
        const location = locationInput.value.trim();
        if (!location) { alert('Please enter a location'); return; }
        findHospitals(location);
    });

    locationInput.addEventListener('keypress', e => { if (e.key === 'Enter') searchHospitalsBtn.click(); });

    useCurrentLocationBtn.addEventListener('click', () => {
        if (!navigator.geolocation) { alert('Geolocation is not supported by your browser'); return; }
        useCurrentLocationBtn.disabled = true;
        useCurrentLocationBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Getting location...';
        navigator.geolocation.getCurrentPosition(
            pos => {
                findHospitals(`${pos.coords.latitude},${pos.coords.longitude}`);
                useCurrentLocationBtn.disabled = false;
                useCurrentLocationBtn.innerHTML = '<i class="fas fa-map-marker-alt"></i> My Location';
            },
            () => {
                alert('Unable to get your location. Please enter it manually.');
                useCurrentLocationBtn.disabled = false;
                useCurrentLocationBtn.innerHTML = '<i class="fas fa-map-marker-alt"></i> My Location';
            }
        );
    });

    function findHospitals(location) {
        searchHospitalsBtn.disabled = true;
        searchHospitalsBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Searching...';

        fetch('http://127.0.0.1:5000/find-hospitals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ location, user_id, radius: 5000, session_id: current_session_id })
        })
        .then(res => res.json())
        .then(data => {
            searchHospitalsBtn.disabled = false;
            searchHospitalsBtn.innerHTML = '<i class="fas fa-search"></i> Search';
            if (data.status === 'success') {
                appendMessage(`🔍 Searching hospitals near ${location}...`, 'user');
                displayHospitals(data.hospitals, data.location);
            } else {
                appendMessage(`❌ Error: ${data.error}`, 'bot');
            }
        })
        .catch(err => {
            searchHospitalsBtn.disabled = false;
            searchHospitalsBtn.innerHTML = '<i class="fas fa-search"></i> Search';
            appendMessage('❌ Error: Could not connect to hospital finder service.', 'bot');
            console.error(err);
        });
    }

    function displayHospitals(hospitals, location) {
        if (!hospitals.length) {
            appendMessage(`😕 No hospitals found near ${location}. Try a different location.`, 'bot');
            return;
        }
        const hospitalHtml = `
            <div style="margin-top:10px;">
                <p style="margin-bottom:15px;"><strong>✅ Found ${hospitals.length} hospitals near ${location}:</strong></p>
                ${hospitals.map((h, i) => `
                    <div class="hospital-card">
                        <div class="hospital-name">🏥 ${h.name}</div>
                        <div class="hospital-address"><i class="fas fa-map-marker-alt"></i> ${h.address}</div>
                        ${h.rating ? `<div class="hospital-rating"><i class="fas fa-star"></i> ${h.rating}/5.0 (${h.rating_count || 0} reviews)</div>` : ''}
                        ${h.open_now !== undefined ? `<div class="hospital-status ${h.open_now ? 'open' : 'closed'}">${h.open_now ? '✓ Open Now' : '✗ Currently Closed'}</div>` : ''}
                        <div class="hospital-actions">
                            <button class="hospital-book-btn" onclick="window.hospitalBookClick(${i}, event)">
                                <i class="fas fa-calendar"></i> Book Appointment
                            </button>
                            <button class="hospital-directions-btn" onclick="window.open('https://www.google.com/maps?q=${h.lat},${h.lng}')">
                                <i class="fas fa-directions"></i> Directions
                            </button>
                        </div>
                    </div>`).join('')}
            </div>`;

        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', 'bot-message');
        const avatar = document.createElement('div');
        avatar.classList.add('avatar');
        const img = document.createElement('img');
        img.src = 'https://api.dicebear.com/7.x/bottts/svg?seed=medical';
        img.alt = 'Bot';
        avatar.appendChild(img);
        msgDiv.appendChild(avatar);
        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        contentDiv.innerHTML = hospitalHtml;
        msgDiv.appendChild(contentDiv);
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        currentChat.push({ sender: 'bot', text: `Found ${hospitals.length} hospitals near ${location}` });
        window.hospitalsList = hospitals;
    }

    window.hospitalBookClick = function(index, event) {
        event.preventDefault();
        if (!window.hospitalsList || !window.hospitalsList[index]) {
            alert('Hospital information not available. Please search again.');
            return;
        }
        openAppointmentModal(window.hospitalsList[index]);
    };

    // ─────────────────────────────────────────────────────────────────────
    // APPOINTMENT MODAL
    // ─────────────────────────────────────────────────────────────────────
    function openAppointmentModal(hospital) {
        selectedHospital = hospital;
        const infoDisplay = document.getElementById('hospital-info-display');
        const nameEl = document.getElementById('modal-hospital-name');
        const addrEl = document.getElementById('modal-hospital-address');
        if (infoDisplay) { infoDisplay.style.display = 'block'; nameEl.textContent = hospital.name; addrEl.textContent = hospital.address; }
        const f = id => document.getElementById(id);
        if (f('hospital-name-hidden'))    f('hospital-name-hidden').value    = hospital.name;
        if (f('hospital-address-hidden')) f('hospital-address-hidden').value = hospital.address;
        if (f('hospital-lat-hidden'))     f('hospital-lat-hidden').value     = hospital.lat;
        if (f('hospital-lng-hidden'))     f('hospital-lng-hidden').value     = hospital.lng;
        appointmentForm.reset();
        appointmentSuccess.classList.remove('show');
        appointmentModal.classList.remove('hidden');
    }

    appointmentForm.insertAdjacentHTML('afterbegin', `
        <input type="hidden" id="hospital-name-hidden" name="hospital_name">
        <input type="hidden" id="hospital-address-hidden" name="hospital_address">
        <input type="hidden" id="hospital-lat-hidden" name="hospital_lat">
        <input type="hidden" id="hospital-lng-hidden" name="hospital_lng">
    `);

    appointmentCloseBtn.addEventListener('click', () => appointmentModal.classList.add('hidden'));

    appointmentForm.addEventListener('submit', e => {
        e.preventDefault();
        const g = id => document.getElementById(id);
        const appointmentData = {
            user_id,
            hospital_name:    g('hospital-name-hidden').value,
            hospital_address: g('hospital-address-hidden').value,
            hospital_lat:     parseFloat(g('hospital-lat-hidden').value),
            hospital_lng:     parseFloat(g('hospital-lng-hidden').value),
            appointment_date: g('appointment-date').value,
            appointment_time: g('appointment-time').value,
            patient_name:     g('patient-name').value,
            patient_email:    g('patient-email').value,
            patient_phone:    g('patient-phone').value,
            patient_age:      g('patient-age').value ? parseInt(g('patient-age').value) : null,
            patient_gender:   g('patient-gender').value,
            symptoms:         g('symptoms').value
        };

        const submitBtn = appointmentForm.querySelector('.appointment-submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

        fetch('http://127.0.0.1:5000/request-appointment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(appointmentData)
        })
        .then(res => res.json())
        .then(data => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check"></i> Request Appointment';
            if (data.status === 'success') {
                appointmentSuccess.classList.add('show');
                setTimeout(() => {
                    appointmentModal.classList.add('hidden');
                    appendMessage(`✅ Appointment request submitted!\n\n📋 Confirmation #: ${data.confirmation_number}\n🏥 ${data.hospital}\n📅 ${data.date} at ${data.time}\n\nYou will receive a confirmation email shortly.`, 'bot');
                }, 2000);
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(err => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check"></i> Request Appointment';
            alert('Error requesting appointment: ' + err.message);
        });
    });

    myAppointmentsBtn.addEventListener('click', () => {
        myAppointmentsModal.classList.remove('hidden');
        loadUserAppointments();
    });
    myAppointmentsCloseBtn.addEventListener('click', () => myAppointmentsModal.classList.add('hidden'));

    function loadUserAppointments() {
        appointmentsContainer.innerHTML = '<p style="text-align:center;"><i class="fas fa-spinner fa-spin"></i> Loading appointments...</p>';
        fetch(`http://127.0.0.1:5000/my-appointments/${user_id}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.appointments.length > 0) {
                    appointmentsContainer.innerHTML = data.appointments.map(apt => `
                        <div class="appointment-item ${apt.status}">
                            <div class="appointment-item-header">
                                <div class="appointment-item-title">${apt.hospital_name}</div>
                                <span class="appointment-status-badge status-${apt.status}">${apt.status.toUpperCase()}</span>
                            </div>
                            <div class="appointment-item-details">
                                <p><strong>📅 Date:</strong> ${apt.appointment_date}</p>
                                <p><strong>🕐 Time:</strong> ${apt.appointment_time}</p>
                                <p><strong>👤 Name:</strong> ${apt.patient_name}</p>
                                <p><strong>#️⃣ Confirmation:</strong> ${apt.confirmation_number}</p>
                                <p style="font-size:12px;color:#94a3b8;">Requested: ${new Date(apt.requested_at).toLocaleDateString()}</p>
                            </div>
                        </div>`).join('');
                } else {
                    appointmentsContainer.innerHTML = '<p style="text-align:center;color:#64748b;">No appointments found. Book one now!</p>';
                }
            })
            .catch(() => {
                appointmentsContainer.innerHTML = '<p style="text-align:center;color:#ef4444;">Error loading appointments</p>';
            });
    }

    // ─────────────────────────────────────────────────────────────────────
    // appendMessage — renders a single message bubble
    // ─────────────────────────────────────────────────────────────────────
    function appendMessage(text, sender, imageSrc = null) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');

        const avatar = document.createElement('div');
        avatar.classList.add('avatar');
        const img = document.createElement('img');
        img.src = sender === 'user'
            ? 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'
            : 'https://api.dicebear.com/7.x/bottts/svg?seed=medical';
        img.alt = sender;
        avatar.appendChild(img);
        msgDiv.appendChild(avatar);

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');

        if (imageSrc) {
            const imageEl = document.createElement('img');
            imageEl.src = imageSrc;
            imageEl.className = 'image-preview';
            imageEl.style.cssText = 'display:block;margin-bottom:10px;';
            contentDiv.appendChild(imageEl);
        }

        const textEl = document.createElement('p');
        textEl.innerHTML = text.replace(/\n/g, '<br>');
        contentDiv.appendChild(textEl);

        msgDiv.appendChild(contentDiv);
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        return textEl;
    }

    function renderChat() {
        chatWindow.innerHTML = '';
        currentChat.forEach(msg => appendMessage(msg.text, msg.sender));
    }

    // ─────────────────────────────────────────────────────────────────────
    // STREAMING BOT RESPONSE — sends session_id with every request
    // ─────────────────────────────────────────────────────────────────────
    function simulateBotResponse(userQuery, imageData = null) {
        const endpoint = queryEndpoints[currentQueryType].url;
        isStreaming = true;
        stopBtn.classList.add('visible');

        const requestBody = {
            message: userQuery || 'Please analyze this image',
            user_id,
            session_id: current_session_id  // ← key fix: links message to session in DB
        };
        if (imageData) {
            requestBody.image = imageData.data;
            requestBody.image_name = imageData.name;
        }

        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        })
        .then(response => {
            if (!response.body) throw new Error('ReadableStream not supported.');
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            const botParagraph = appendMessage('', 'bot');

            streamController = { stopped: false, reader };

            function readChunk() {
                if (streamController.stopped) {
                    reader.cancel();
                    botParagraph.innerHTML += ' <i style="color:#ef4444;">[Stopped]</i>';
                    currentChat.push({ sender: 'bot', text: botParagraph.innerHTML });
                    isStreaming = false;
                    stopBtn.classList.remove('visible');
                    return;
                }
                reader.read().then(({ done, value }) => {
                    if (done) {
                        currentChat.push({ sender: 'bot', text: botParagraph.innerHTML });
                        isStreaming = false;
                        stopBtn.classList.remove('visible');
                        return;
                    }
                    const chunkText = decoder.decode(value, { stream: true });
                    let i = 0;

                    function typeChar() {
                        if (streamController.stopped) {
                            reader.cancel();
                            botParagraph.innerHTML += ' <i style="color:#ef4444;">[Stopped]</i>';
                            currentChat.push({ sender: 'bot', text: botParagraph.innerHTML });
                            isStreaming = false;
                            stopBtn.classList.remove('visible');
                            return;
                        }
                        if (i < chunkText.length) {
                            const char = chunkText.charAt(i);
                            botParagraph.innerHTML += (char === '\n') ? '<br>' : char;
                            chatWindow.scrollTop = chatWindow.scrollHeight;
                            i++;
                            const delay = ['.', '!', '?'].includes(chunkText.charAt(i - 1)) ? 80 : 20;
                            setTimeout(typeChar, delay);
                        } else {
                            readChunk();
                        }
                    }
                    typeChar();
                });
            }
            readChunk();
        })
        .catch(err => {
            appendMessage('⚠️ Error: Could not connect to backend.', 'bot');
            console.error(err);
            isStreaming = false;
            stopBtn.classList.remove('visible');
        });
    }

    stopBtn.addEventListener('click', () => {
        if (isStreaming && streamController) streamController.stopped = true;
    });

    // ─────────────────────────────────────────────────────────────────────
    // IMAGE INPUT
    // ─────────────────────────────────────────────────────────────────────
    imageInputBtn.addEventListener('click', () => imageInput.click());

    imageInput.addEventListener('change', e => {
        const file = e.target.files[0];
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = event => {
                selectedImage = { data: event.target.result, name: file.name, type: file.type };
                showImagePreview(event.target.result);
            };
            reader.readAsDataURL(file);
        }
    });

    function showImagePreview(imageSrc) {
        const existing = document.querySelector('.image-preview-container');
        if (existing) existing.remove();

        const previewContainer = document.createElement('div');
        previewContainer.className = 'image-preview-container';
        previewContainer.style.cssText = 'position:absolute;bottom:80px;left:20px;';

        const img = document.createElement('img');
        img.src = imageSrc;
        img.className = 'image-preview';

        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-image-btn';
        removeBtn.innerHTML = '×';
        removeBtn.onclick = () => {
            selectedImage = null;
            previewContainer.remove();
            imageInput.value = '';
        };

        previewContainer.appendChild(img);
        previewContainer.appendChild(removeBtn);
        document.getElementById('chat-form').appendChild(previewContainer);
    }

    // ─────────────────────────────────────────────────────────────────────
    // FORM SUBMIT
    // ─────────────────────────────────────────────────────────────────────
    chatForm.addEventListener('submit', e => {
        e.preventDefault();
        const userMessage = chatInput.value.trim();
        if (!userMessage && !selectedImage) return;

        const displayText = userMessage || '📷 [Image sent]';
        appendMessage(displayText, 'user', selectedImage ? selectedImage.data : null);
        currentChat.push({ sender: 'user', text: displayText, image: selectedImage ? selectedImage.data : null });

        simulateBotResponse(userMessage, selectedImage);

        chatInput.value = '';
        selectedImage = null;
        imageInput.value = '';
        const preview = document.querySelector('.image-preview-container');
        if (preview) preview.remove();
    });

    // ─────────────────────────────────────────────────────────────────────
    // VOICE INPUT
    // ─────────────────────────────────────────────────────────────────────
    voiceBtn.addEventListener('click', () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert('Voice input not supported in this browser. Please use Chrome, Edge, or Safari.');
            return;
        }
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        voiceBtn.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
        voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Listening...';

        recognition.onresult = event => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            if (transcript.trim()) {
                chatInput.value = transcript;
                chatForm.dispatchEvent(new Event('submit'));
            }
        };
        recognition.onerror = event => {
            console.error('Speech recognition error:', event.error);
            alert('Voice recognition error: ' + event.error);
            voiceBtn.style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
            voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        };
        recognition.onend = () => {
            voiceBtn.style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
            voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        };
        try {
            recognition.start();
        } catch (err) {
            alert('Could not start voice recognition: ' + err.message);
            voiceBtn.style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
            voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        }
    });

    // ─────────────────────────────────────────────────────────────────────
    // OVERLAY / INFO SECTIONS
    // ─────────────────────────────────────────────────────────────────────
    const sectionContent = {
        about: {
            title: 'About Our Medical Chatbot',
            content: `
                <p>
                    Our AI-powered Medical Chatbot is designed to provide accessible healthcare information 
                    and support to users 24/7. We combine cutting-edge artificial intelligence with medical 
                    expertise to deliver accurate, reliable health guidance.
                </p>
                <p>
                    <strong>🎯 Our Mission:</strong> To make healthcare information accessible to everyone, 
                    anytime, anywhere.
                </p>
                <p>
                    <strong>⚕️ Our Vision:</strong> Empowering individuals to make informed decisions 
                    about their health through intelligent, compassionate AI assistance.
                </p>
                <div class="step-box">
                    <h3>Why Choose Us?</h3>
                    <ul>
                        <li><strong>Evidence-Based:</strong> All information is backed by medical research</li>
                        <li><strong>Accessible:</strong> Available 24/7 in multiple languages</li>
                        <li><strong>Secure:</strong> Your privacy is our top priority</li>
                        <li><strong>User-Friendly:</strong> Simple interface for everyone</li>
                    </ul>
                </div>
            `
        },
        features: {
            title: 'Features',
            content: `
                <div class="feature-grid">
                    <div class="feature-card">
                        <div class="feature-icon">🩺</div>
                        <h3>Symptom Checker</h3>
                        <p>Analyze your symptoms and get preliminary guidance</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">💊</div>
                        <h3>Medication Info</h3>
                        <p>Learn about medications, dosages, and side effects</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🏥</div>
                        <h3>Hospital Finder</h3>
                        <p>Find nearby hospitals with ratings and contact info</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">📅</div>
                        <h3>Book Appointments</h3>
                        <p>Request appointments at hospitals near you</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🔒</div>
                        <h3>Privacy First</h3>
                        <p>Your data is encrypted and completely confidential</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">⚡</div>
                        <h3>24/7 Availability</h3>
                        <p>Get instant responses anytime, day or night</p>
                    </div>
                </div>
            `
        },
        'how-it-works': {
            title: 'How It Works',
            content: `
                <p>
                    Our chatbot uses advanced natural language processing to understand your health queries 
                    and provide accurate information. Here's how it works:
                </p>
                <div class="step-box">
                    <h3>Step-by-Step Process</h3>
                    <p><strong>1️⃣ Ask Your Question:</strong> Type your health-related query in natural language</p>
                    <p><strong>2️⃣ AI Analysis:</strong> Our AI processes your question using medical knowledge bases</p>
                    <p><strong>3️⃣ Instant Response:</strong> Receive accurate, evidence-based information instantly</p>
                    <p><strong>4️⃣ Book Appointment:</strong> Find hospitals and book appointments with ease</p>
                </div>
                <div class="step-box" style="background: #fef3c7; border-left-color: #eab308;">
                    <p><strong>⚠️ Important Disclaimer:</strong> This chatbot provides information only and is not a substitute 
                    for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for medical concerns.</p>
                </div>
                <h3>Appointment Booking Process</h3>
                <ul>
                    <li><strong>Find Hospitals:</strong> Use Hospital Finder to locate nearby medical facilities</li>
                    <li><strong>Select Hospital:</strong> Choose the hospital you want to book</li>
                    <li><strong>Fill Details:</strong> Enter your information and preferred date/time</li>
                    <li><strong>Submit Request:</strong> Send your appointment request</li>
                    <li><strong>Get Confirmation:</strong> Receive confirmation via email once approved</li>
                </ul>
            `
        },
        impact: {
            title: 'Our Impact',
            content: `
                <p>
                    Since our launch, we've made significant strides in improving healthcare accessibility:
                </p>
                <div class="feature-grid">
                    <div class="feature-card">
                        <div class="feature-icon">👥</div>
                        <h3>100K+ Users</h3>
                        <p>Served across 50+ countries</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">💬</div>
                        <h3>1M+ Conversations</h3>
                        <p>Health queries answered</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">⭐</div>
                        <h3>4.8/5 Rating</h3>
                        <p>User satisfaction score</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🌟</div>
                        <h3>95% Accuracy</h3>
                        <p>Information reliability rate</p>
                    </div>
                </div>
                <p style="margin-top: 25px;">
                    <strong>💚 Making a Difference:</strong> We've helped reduce unnecessary ER visits, 
                    improved medication adherence, and empowered people to make better health decisions.
                </p>
                <p>
                    Our chatbot has been recognized by healthcare professionals and continues to improve 
                    through user feedback and medical research.
                </p>
            `
        },
        contact: {
            title: 'Contact Us',
            content: `
                <p>
                    We'd love to hear from you! Reach out for support, partnerships, or feedback.
                </p>
                <div class="contact-info">
                    <div class="contact-item">
                        <i class="fas fa-envelope"></i>
                        <div>
                            <strong>Email:</strong><br>
                            karnativikas1612@gmail.com<br>
                            <small>Response time: 24 hours</small>
                        </div>
                    </div>
                    <div class="contact-item">
                        <i class="fas fa-phone"></i>
                        <div>
                            <strong>Phone:</strong><br>
                            +91 9390553060<br>
                            <small>Available: Mon-Fri, 9AM-6PM EST</small>
                        </div>
                    </div>
                    <div class="contact-item">
                        <i class="fas fa-map-marker-alt"></i>
                        <div>
                            <strong>Address:</strong><br>
                            kandlakoya, Medchal District<br>
                            Hyderabad, Telangana, India - 501401
                        </div>
                    </div>
                    <div class="contact-item">
                        <i class="fas fa-clock"></i>
                        <div>
                            <strong>Support Hours:</strong><br>
                            24/7 Chat Support Available<br>
                            <small>Phone: Mon-Fri, 9AM-6PM PST</small>
                        </div>
                    </div>
                </div>
                <div style="margin-top: 25px; text-align: center;">
                    <p style="margin-bottom: 15px;"><strong>Follow Us:</strong></p>
                    <div style="font-size: 28px; display: flex; justify-content: center; gap: 20px;">
                        <i class="fab fa-twitter" style="color: #1DA1F2; cursor: pointer;"></i>
                        <i class="fab fa-facebook" style="color: #4267B2; cursor: pointer;"></i>
                        <i class="fab fa-linkedin" style="color: #0077B5; cursor: pointer;"></i>
                        <i class="fab fa-instagram" style="color: #E4405F; cursor: pointer;"></i>
                    </div>
                </div>
            `
        }
    };

    navLinks.forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const data = sectionContent[link.dataset.section];
            if (data) {
                overlayTitle.textContent = data.title;
                overlayBody.innerHTML = data.content;
                overlay.classList.remove('hidden');
            }
        });
    });

    closeBtn.addEventListener('click', () => overlay.classList.add('hidden'));
    overlay.addEventListener('click', e => { if (e.target.id === 'overlay') overlay.classList.add('hidden'); });
    appointmentModal.addEventListener('click', e => { if (e.target.id === 'appointment-modal') appointmentModal.classList.add('hidden'); });
    myAppointmentsModal.addEventListener('click', e => { if (e.target.id === 'my-appointments-modal') myAppointmentsModal.classList.add('hidden'); });


    // ─────────────────────────────────────────────────────────────────────
    // PATIENT SEARCH
    // ─────────────────────────────────────────────────────────────────────
    const patientSearchBtn      = document.getElementById('patient-search-btn');
    const patientSearchModal    = document.getElementById('patient-search-modal');
    const patientSearchCloseBtn = document.getElementById('patient-search-close-btn');
    const patientSearchInput    = document.getElementById('patient-search-input');
    const patientSearchSubmit   = document.getElementById('patient-search-submit-btn');
    const patientSearchResults  = document.getElementById('patient-search-results');
    const patientSearchStatus   = document.getElementById('patient-search-status');

    // Open modal
    patientSearchBtn.addEventListener('click', () => {
        patientSearchModal.classList.remove('hidden');
        patientSearchInput.focus();
    });

    // Close modal
    patientSearchCloseBtn.addEventListener('click', () => patientSearchModal.classList.add('hidden'));
    patientSearchModal.addEventListener('click', e => {
        if (e.target.id === 'patient-search-modal') patientSearchModal.classList.add('hidden');
    });

    // Trigger search on Enter key
    patientSearchInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') patientSearchSubmit.click();
    });

    // Search button click
    patientSearchSubmit.addEventListener('click', () => {
        const name = patientSearchInput.value.trim();
        if (!name) {
            patientSearchStatus.textContent = '⚠️ Please enter a patient name.';
            patientSearchStatus.style.color = '#f59e0b';
            return;
        }
        runPatientSearch(name);
    });

    function runPatientSearch(name) {
        patientSearchStatus.textContent = '⏳ Searching...';
        patientSearchStatus.style.color = '#94a3b8';
        patientSearchResults.innerHTML = '<p style="text-align:center;padding:20px 0;color:#64748b;">Loading...</p>';
        patientSearchSubmit.disabled = true;

        fetch(`http://127.0.0.1:5000/search-patient?name=${encodeURIComponent(name)}`)
            .then(res => res.json())
            .then(data => {
                patientSearchSubmit.disabled = false;

                if (data.status === 'error') {
                    patientSearchStatus.textContent = '❌ ' + data.message;
                    patientSearchStatus.style.color = '#ef4444';
                    patientSearchResults.innerHTML = '';
                    return;
                }

                if (data.found === 0) {
                    patientSearchStatus.textContent = data.message || 'No patients found.';
                    patientSearchStatus.style.color = '#f59e0b';
                    patientSearchResults.innerHTML = `
                        <div style="text-align:center;padding:30px 0;">
                            <div style="font-size:48px;margin-bottom:12px;">🔍</div>
                            <p style="color:#64748b;">No patient found matching "<strong>${name}</strong>".</p>
                            <p style="color:#94a3b8;font-size:13px;">Try a partial name or check the spelling.</p>
                        </div>`;
                    return;
                }

                patientSearchStatus.textContent = `✅ Found ${data.found} patient(s) matching "${name}"`;
                patientSearchStatus.style.color = '#10b981';
                renderPatientResults(data.patients, data.source);
            })
            .catch(err => {
                patientSearchSubmit.disabled = false;
                patientSearchStatus.textContent = '❌ Could not connect to server.';
                patientSearchStatus.style.color = '#ef4444';
                patientSearchResults.innerHTML = '';
                console.error(err);
            });
    }

    function renderPatientResults(patients, source) {
        if (source === 'patients_table') {
            renderFromPatientsTable(patients);
        } else {
            renderFromAppointmentsTable(patients);
        }
    }

    // ── Render from Patients + Visits + Doctors + Hospitals + MedicalRecords ──
    function renderFromPatientsTable(patients) {
        patientSearchResults.innerHTML = patients.map(p => `
            <div style="background:rgba(139,92,246,0.05);border:1px solid rgba(139,92,246,0.2);
                        border-radius:12px;padding:20px;margin-bottom:16px;">

                <!-- Patient Header -->
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;
                            padding-bottom:12px;border-bottom:1px solid rgba(139,92,246,0.15);">
                    <div style="width:44px;height:44px;border-radius:50%;
                                background:linear-gradient(135deg,#667eea,#764ba2);
                                display:flex;align-items:center;justify-content:center;font-size:20px;">👤</div>
                    <div style="flex:1;">
                        <div style="font-weight:700;font-size:16px;">${p.patient_name}</div>
                        <div style="font-size:12px;color:#94a3b8;">
                            ${p.phone ? '📞 ' + p.phone : ''}
                            ${p.date_of_birth ? ' · DOB: ' + p.date_of_birth : ''}
                        </div>
                    </div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;">
                        ${p.gender ? `<span style="background:rgba(99,102,241,0.15);padding:3px 10px;border-radius:20px;font-size:12px;">${p.gender}</span>` : ''}
                        <span style="background:rgba(16,185,129,0.15);color:#10b981;padding:3px 10px;border-radius:20px;font-size:12px;">${p.total_visits} visit(s)</span>
                    </div>
                </div>

                ${p.extra_data ? `
                <div style="background:rgba(99,102,241,0.08);border-radius:8px;padding:10px 14px;margin-bottom:14px;font-size:12px;color:#94a3b8;">
                    <strong style="color:#a78bfa;">📦 Extra Data:</strong> ${JSON.stringify(p.extra_data)}
                </div>` : ''}

                <!-- Visits -->
                <div style="font-size:13px;font-weight:600;color:#a78bfa;margin-bottom:10px;">🏥 Visit History</div>

                ${p.visits.length === 0 ? '<p style="color:#64748b;font-size:13px;">No visits recorded.</p>' :
                  p.visits.map(v => `
                    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                                border-left:3px solid #6366f1;border-radius:8px;padding:14px;margin-bottom:10px;">

                        <!-- Visit Header -->
                        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:8px;">
                            <div>
                                <div style="font-weight:600;font-size:13px;">
                                    🏥 ${v.hospital_name || 'Unknown Hospital'}
                                    ${v.hospital_city ? '<span style="font-weight:400;color:#94a3b8;"> · ' + v.hospital_city + '</span>' : ''}
                                </div>
                                ${v.hospital_district ? `<div style="font-size:11px;color:#64748b;">📍 ${v.hospital_district}</div>` : ''}
                                ${v.hospital_contact  ? `<div style="font-size:11px;color:#64748b;">📞 ${v.hospital_contact}</div>`  : ''}
                            </div>
                            <span style="font-size:12px;color:#94a3b8;">📅 ${v.visit_date}</span>
                        </div>

                        <!-- Doctor -->
                        ${v.doctor_name ? `
                        <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;
                                    background:rgba(139,92,246,0.08);border-radius:6px;padding:6px 10px;">
                            <span style="font-size:14px;">👨‍⚕️</span>
                            <div>
                                <span style="font-size:13px;font-weight:600;">${v.doctor_name}</span>
                                ${v.specialization ? `<span style="font-size:11px;color:#94a3b8;"> · ${v.specialization}</span>` : ''}
                            </div>
                        </div>` : ''}

                        <!-- Notes -->
                        ${v.notes ? `<div style="font-size:12px;color:#a78bfa;margin-bottom:8px;">📝 ${v.notes}</div>` : ''}

                        <!-- Extra visit data -->
                        ${v.visit_extra ? `<div style="font-size:11px;color:#64748b;margin-bottom:8px;">📦 ${JSON.stringify(v.visit_extra)}</div>` : ''}

                        <!-- Medical Records -->
                        ${v.medical_records.length > 0 ? `
                        <div style="margin-top:8px;border-top:1px solid rgba(255,255,255,0.06);padding-top:8px;">
                            <div style="font-size:12px;font-weight:600;color:#06b6d4;margin-bottom:6px;">
                                🧾 Medical Records (${v.medical_records.length})
                            </div>
                            ${v.medical_records.map(r => `
                                <div style="background:rgba(6,182,212,0.05);border:1px solid rgba(6,182,212,0.15);
                                            border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:12px;">
                                    <span style="color:#06b6d4;font-weight:600;">${r.record_type || 'Record'}</span>
                                    <span style="color:#64748b;float:right;">${r.created_at ? r.created_at.substring(0,10) : ''}</span>
                                    <div style="margin-top:4px;color:#94a3b8;word-break:break-all;">
                                        ${typeof r.data === 'object' ? JSON.stringify(r.data) : r.data}
                                    </div>
                                </div>
                            `).join('')}
                        </div>` : ''}
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    // ── Render fallback from appointments table ──────────────────────────────
    function renderFromAppointmentsTable(patients) {
        const statusColors = { confirmed: '#10b981', pending: '#f59e0b', rejected: '#ef4444' };
        const statusIcons  = { confirmed: '✓', pending: '⏳', rejected: '✗' };

        patientSearchResults.innerHTML = `
            <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);
                        border-radius:8px;padding:10px 14px;margin-bottom:14px;font-size:12px;color:#f59e0b;">
                ⚠️ Showing results from the appointments table.
                The full Patients/Visits database has not been set up yet.
            </div>` +
        patients.map(p => `
            <div style="background:rgba(139,92,246,0.05);border:1px solid rgba(139,92,246,0.2);
                        border-radius:12px;padding:20px;margin-bottom:16px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;
                            padding-bottom:12px;border-bottom:1px solid rgba(139,92,246,0.15);">
                    <div style="width:44px;height:44px;border-radius:50%;
                                background:linear-gradient(135deg,#667eea,#764ba2);
                                display:flex;align-items:center;justify-content:center;font-size:20px;">👤</div>
                    <div style="flex:1;">
                        <div style="font-weight:700;font-size:16px;">${p.patient_name}</div>
                        <div style="font-size:12px;color:#94a3b8;">
                            ${p.patient_email || ''} ${p.patient_phone ? ' · ' + p.patient_phone : ''}
                        </div>
                    </div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;">
                        ${p.patient_age    ? `<span style="background:rgba(99,102,241,0.15);padding:3px 10px;border-radius:20px;font-size:12px;">Age: ${p.patient_age}</span>` : ''}
                        ${p.patient_gender ? `<span style="background:rgba(99,102,241,0.15);padding:3px 10px;border-radius:20px;font-size:12px;">${p.patient_gender}</span>` : ''}
                    </div>
                </div>
                <div style="font-size:13px;font-weight:600;color:#a78bfa;margin-bottom:10px;">
                    📋 Appointments (${p.appointments.length})
                </div>
                ${p.appointments.map(apt => `
                    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
                                border-left:3px solid ${statusColors[apt.status] || '#6366f1'};
                                border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap;">
                            <div>
                                <div style="font-weight:600;font-size:13px;">🏥 ${apt.hospital_name}</div>
                                ${apt.hospital_address ? `<div style="font-size:11px;color:#94a3b8;margin-top:2px;">📍 ${apt.hospital_address}</div>` : ''}
                            </div>
                            <span style="background:${statusColors[apt.status] || '#6366f1'}22;
                                         color:${statusColors[apt.status] || '#6366f1'};
                                         padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">
                                ${statusIcons[apt.status] || '•'} ${apt.status.toUpperCase()}
                            </span>
                        </div>
                        <div style="display:flex;gap:16px;margin-top:8px;font-size:12px;color:#94a3b8;flex-wrap:wrap;">
                            <span>📅 ${apt.appointment_date}</span>
                            <span>🕐 ${apt.appointment_time}</span>
                            <span style="color:#64748b;">#${apt.confirmation_number}</span>
                        </div>
                        ${apt.symptoms ? `<div style="margin-top:6px;font-size:12px;color:#a78bfa;">🩺 ${apt.symptoms}</div>` : ''}
                    </div>
                `).join('')}
            </div>
        `).join('');
    }

    // ─────────────────────────────────────────────────────────────────────
    // INIT
    // ─────────────────────────────────────────────────────────────────────
    loadAllHistory();

    console.log('✅ MediMind Chatbot loaded');
    console.log('✅ User ID:', user_id);
    console.log('✅ Session ID:', current_session_id);
});