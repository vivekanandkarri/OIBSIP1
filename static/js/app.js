// PyVoice Assistant Frontend Controller

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const chatHistory = document.getElementById('chat-history');
    const commandInput = document.getElementById('command-input');
    const textSubmitBtn = document.getElementById('text-submit-btn');
    const micTriggerBtn = document.getElementById('mic-trigger-btn');
    const micStatus = document.getElementById('mic-status');
    const clearConsoleBtn = document.getElementById('clear-console-btn');
    
    const lastIntentVal = document.getElementById('last-intent');
    const entitiesVal = document.getElementById('extracted-entities');
    const thermostatVal = document.getElementById('thermostat-val');
    
    // Status Indicator
    const connectionIndicator = document.getElementById('connection-indicator');
    const connectionText = document.getElementById('connection-text');

    // Weather widget
    const weatherTemp = document.getElementById('weather-temp');
    const weatherCity = document.getElementById('weather-city');
    const weatherCond = document.getElementById('weather-cond');

    // Connection mode
    let isStandaloneMode = false;
    
    // Mock devices database for Standalone Mode
    const localDevices = {
        light: {
            "living room": "off",
            "bedroom": "off"
        },
        thermostat: {
            temperature: 22
        }
    };

    // Speech Recognition Web API (for browser input)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isBrowserMicActive = false;

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            isBrowserMicActive = true;
            micTriggerBtn.classList.add('active');
            micStatus.textContent = "Listening...";
        };

        recognition.onspeechend = () => {
            recognition.stop();
        };

        recognition.onend = () => {
            isBrowserMicActive = false;
            micTriggerBtn.classList.remove('active');
            micStatus.textContent = "Click to speak";
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            addMessageToConsole(transcript, 'user');
            processCommand(transcript);
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            micStatus.textContent = `Error: ${event.error}`;
            addMessageToConsole(`[Browser Mic Error: ${event.error}]`, 'system');
        };
    } else {
        micStatus.textContent = "Voice input unsupported";
        micTriggerBtn.disabled = true;
        micTriggerBtn.style.opacity = '0.5';
    }

    // Connect to Server Status Loop
    checkConnection();
    setInterval(checkConnection, 5000);

    // Event Listeners
    textSubmitBtn.addEventListener('click', submitTextCommand);
    commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            submitTextCommand();
        }
    });

    micTriggerBtn.addEventListener('click', () => {
        if (isBrowserMicActive) {
            recognition.stop();
        } else {
            if (isStandaloneMode) {
                if (recognition) recognition.start();
            } else {
                fetch('/api/status')
                    .then(res => res.json())
                    .then(data => {
                        if (data.server_mic_active) {
                            micStatus.textContent = "Server microphone listening...";
                        } else if (recognition) {
                            recognition.start();
                        }
                    })
                    .catch(() => {
                        if (recognition) recognition.start();
                    });
            }
        }
    });

    clearConsoleBtn.addEventListener('click', () => {
        chatHistory.innerHTML = '';
        addMessageToConsole("Console cleared. I am ready for instructions.", 'system');
    });

    // Helper functions
    function submitTextCommand() {
        const text = commandInput.value.trim();
        if (!text) return;

        addMessageToConsole(text, 'user');
        commandInput.value = '';
        processCommand(text);
    }

    function addMessageToConsole(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender);

        const bubble = document.createElement('div');
        bubble.classList.add('message-bubble');
        bubble.textContent = text;

        const timeSpan = document.createElement('span');
        timeSpan.classList.add('message-time');
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msgDiv.appendChild(bubble);
        msgDiv.appendChild(timeSpan);
        
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function processCommand(command) {
        // Show indicator that Nova is thinking
        const thinkingDiv = document.createElement('div');
        thinkingDiv.classList.add('message', 'assistant', 'thinking');
        thinkingDiv.innerHTML = '<div class="message-bubble"><i class="fa-solid fa-circle-notch fa-spin"></i> Nova is processing...</div>';
        chatHistory.appendChild(thinkingDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        if (isStandaloneMode) {
            // Run Client-Side Mock NLP Intent matching
            setTimeout(() => {
                thinkingDiv.remove();
                const result = runLocalNLP(command);
                addMessageToConsole(result.response, 'assistant');
                speakResponse(result.response);
                
                lastIntentVal.textContent = result.nlp.intent;
                entitiesVal.textContent = JSON.stringify(result.nlp.entities, null, 2);
                
                // Update local switches states
                updateWidgetsFromLocalState();
            }, 800);
        } else {
            // Query Flask Backend server
            fetch('/api/command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ command: command })
            })
            .then(res => res.json())
            .then(data => {
                thinkingDiv.remove();
                addMessageToConsole(data.response, 'assistant');
                speakResponse(data.response);

                if (data.nlp) {
                    lastIntentVal.textContent = data.nlp.intent || '-';
                    entitiesVal.textContent = JSON.stringify(data.nlp.entities, null, 2);
                    if (data.nlp.intent === 'smart_home') {
                        setTimeout(checkConnection, 500);
                    }
                    if (data.nlp.intent === 'weather') {
                        loadWeather();
                    }
                }
            })
            .catch(err => {
                thinkingDiv.remove();
                console.warn("Backend server not responding. Entering Standalone Browser Mode.");
                isStandaloneMode = true;
                processCommand(command); // Retry locally
            });
        }
    }

    function speakResponse(text) {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            const voices = window.speechSynthesis.getVoices();
            if (voices.length > 0) {
                const preferredVoice = voices.find(v => v.lang.includes('en') && (v.name.includes('Google') || v.name.includes('Natural')));
                if (preferredVoice) utterance.voice = preferredVoice;
            }
            window.speechSynthesis.speak(utterance);
        }
    }

    function checkConnection() {
        if (isStandaloneMode) {
            connectionIndicator.className = "status-indicator online";
            connectionText.textContent = "Standalone Mode (Browser)";
            updateWidgetsFromLocalState();
            return;
        }

        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                connectionIndicator.className = "status-indicator online";
                connectionText.textContent = "Connected";
                
                if (data.devices) {
                    document.getElementById('device-living-room-lights').checked = data.devices.light["living room"] === 'on';
                    document.getElementById('device-bedroom-lights').checked = data.devices.light["bedroom"] === 'on';
                    document.getElementById('thermostat-slider').value = data.devices.thermostat.temperature;
                    thermostatVal.textContent = `${data.devices.thermostat.temperature}°C`;
                }
            })
            .catch(() => {
                // If endpoint unreachable, toggle Standalone mode
                isStandaloneMode = true;
                connectionIndicator.className = "status-indicator online";
                connectionText.textContent = "Standalone Mode (Browser)";
                addMessageToConsole("[Server Offline - Switched to local Standalone Mode]", 'system');
                updateWidgetsFromLocalState();
                loadWeather();
            });
    }

    function loadWeather() {
        if (isStandaloneMode) {
            weatherTemp.textContent = "28°C";
            weatherCity.textContent = "Hyderabad";
            weatherCond.textContent = "Partly Cloudy (Mock)";
            return;
        }

        fetch('/api/weather')
            .then(res => res.json())
            .then(data => {
                weatherTemp.textContent = `${data.temp}°C`;
                weatherCity.textContent = data.city;
                weatherCond.textContent = data.condition;
            })
            .catch(() => {
                weatherTemp.textContent = "28°C";
                weatherCity.textContent = "Hyderabad";
                weatherCond.textContent = "Partly Cloudy";
            });
    }

    // Triggered on widget manual switch toggles
    window.toggleDevice = function(type, device, isChecked) {
        const action = isChecked ? 'turn_on' : 'turn_off';
        
        if (isStandaloneMode) {
            localDevices.light[device] = isChecked ? 'on' : 'off';
            addMessageToConsole(`I have turned the ${device} light ${isChecked ? 'on' : 'off'}.`, 'assistant');
            speakResponse(`I have turned the ${device} light ${isChecked ? 'on' : 'off'}.`);
            updateWidgetsFromLocalState();
            return;
        }

        fetch('/api/devices/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: type, device: device, action: action })
        })
        .then(res => res.json())
        .then(data => {
            addMessageToConsole(data.message, 'system');
        });
    };

    window.updateThermostatDisplay = function(val) {
        thermostatVal.textContent = `${val}°C`;
    };

    window.setThermostat = function(val) {
        if (isStandaloneMode) {
            localDevices.thermostat.temperature = parseInt(val);
            addMessageToConsole(`I've set the thermostat to ${val} degrees Celsius.`, 'assistant');
            speakResponse(`I've set the thermostat to ${val} degrees Celsius.`);
            updateWidgetsFromLocalState();
            return;
        }

        fetch('/api/devices/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'thermostat', action: 'set', value: parseInt(val) })
        })
        .then(res => res.json())
        .then(data => {
            addMessageToConsole(data.message, 'system');
        });
    };

    function updateWidgetsFromLocalState() {
        document.getElementById('device-living-room-lights').checked = localDevices.light["living room"] === 'on';
        document.getElementById('device-bedroom-lights').checked = localDevices.light["bedroom"] === 'on';
        document.getElementById('thermostat-slider').value = localDevices.thermostat.temperature;
        thermostatVal.textContent = `${localDevices.thermostat.temperature}°C`;
    }

    // =================================================================
    // Local NLP Mock Engine for Standalone Browser Mode
    // =================================================================
    function runLocalNLP(command) {
        const text = command.toLowerCase().trim();
        let intent = "unknown";
        let entities = {};
        let response = "I'm sorry, I couldn't understand that command in standalone mode.";

        // Greet
        if (/\b(hello|hi|hey|greetings|morning)\b/.test(text)) {
            intent = "greet";
            response = "Hello! I am Nova, your client-side voice assistant. How can I help you today?";
        }
        // Farewell
        else if (/\b(goodbye|bye|exit|stop|shutdown)\b/.test(text)) {
            intent = "farewell";
            response = "Goodbye! Hope you have a wonderful day.";
        }
        // Weather
        else if (/\b(weather|temperature|forecast|climate)\b/.test(text)) {
            intent = "weather";
            let city = "Hyderabad";
            const match = /\b(?:in|at|for)\b\s+([a-zA-Z\s]+)$/.exec(text);
            if (match) city = match[1].trim().replace(/\b\w/g, c => c.toUpperCase());
            entities.city = city;
            
            response = `It's currently 28 degrees Celsius and clear sky in ${city}. The 3-day forecast is: tomorrow 29 degrees and sunny, the day after 27 degrees and cloudy, and in three days 28 degrees with light showers.`;
        }
        // Reminders
        else if (/\b(remind|reminder|alarm|timer)\b/.test(text)) {
            intent = "set_reminder";
            let note = "timer finished";
            let timeExpr = "in 10 seconds";
            
            const noteMatch = /remind\s+(?:me\s+)?to\s+(.*?)(?:\bin\b|\bat\b|\bon\b|$)/.exec(text);
            if (noteMatch) note = noteMatch[1].trim();
            
            const timeMatch = /in\s+(\d+)\s+(seconds|second|minutes|minute)/.exec(text);
            let durationMs = 10000; // default 10s
            if (timeMatch) {
                timeExpr = timeMatch[0];
                const amt = parseInt(timeMatch[1]);
                const unit = timeMatch[2];
                if (unit.startsWith("minute")) durationMs = amt * 60 * 1000;
                else durationMs = amt * 1000;
            }
            
            entities.reminder_note = note;
            entities.time_expression = timeExpr;
            
            // Set browser timeout
            setTimeout(() => {
                addMessageToConsole(`Reminder alert: ${note}`, 'assistant');
                speakResponse(`Reminder alert: ${note}`);
            }, durationMs);

            response = `I have set a client-side reminder to ${note} ${timeExpr}.`;
        }
        // Smart Home
        else if (/\b(light|lights|switch|thermostat|ac|heating|turn on|turn off)\b/.test(text)) {
            intent = "smart_home";
            
            let action = "status";
            if (/\b(turn on|on|activate)\b/.test(text)) action = "turn_on";
            else if (/\b(turn off|off|deactivate)\b/.test(text)) action = "turn_off";
            else if (/\b(set)\b/.test(text)) action = "set";

            let device = "light";
            if (/\b(thermostat|ac|heating)\b/.test(text)) device = "thermostat";
            
            entities.device_type = device;
            entities.device_action = action;

            if (device === "light") {
                let target = "living room";
                if (/\b(bedroom)\b/.test(text)) target = "bedroom";
                
                if (action === "turn_on") {
                    localDevices.light[target] = "on";
                    response = `I have turned the ${target} light on.`;
                } else if (action === "turn_off") {
                    localDevices.light[target] = "off";
                    response = `I have turned the ${target} light off.`;
                } else {
                    response = `The living room light is ${localDevices.light["living room"]}, and the bedroom light is ${localDevices.light["bedroom"]}.`;
                }
            } else {
                // Thermostat
                if (action === "set") {
                    const tempMatch = /\bto\s+(\d+)\b/.exec(text);
                    if (tempMatch) {
                        const val = parseInt(tempMatch[1]);
                        localDevices.thermostat.temperature = val;
                        entities.device_value = val;
                        response = `I have set the thermostat to ${val} degrees.`;
                    } else {
                        response = "What temperature would you like me to set the thermostat to?";
                    }
                } else {
                    response = `The thermostat is currently set to ${localDevices.thermostat.temperature} degrees Celsius.`;
                }
            }
        }
        // Email
        else if (/\b(email|mail)\b/.test(text)) {
            intent = "send_email";
            let name = "Rahul";
            const nameMatch = /\b(?:email|mail|to)\b\s+([a-zA-Z]+)/.exec(text);
            if (nameMatch && !["email", "mail", "send", "to"].includes(nameMatch[1])) {
                name = nameMatch[1].trim().replace(/\b\w/g, c => c.toUpperCase());
            }
            entities.recipient_name = name;
            entities.subject = "Project details";
            
            response = `Mock mode active. I have simulated drafting and sending an email to ${name} with subject "Project details" successfully.`;
        }
        // General Knowledge
        else if (/\b(who|what|where|why|how|define|search|wikipedia|info)\b/.test(text)) {
            intent = "general_knowledge";
            let query = "Python programming";
            const qMatch = /\b(?:about|search|wikipedia|who is|what is|define)\b\s+(.*)$/.exec(text);
            if (qMatch) query = qMatch[1].trim();
            entities.query = query;

            if (text.includes("sky") && text.includes("blue")) {
                response = "The sky is blue because the Earth's atmosphere scatters sunlight in all directions, and blue light is scattered more than other colors because it travels as shorter, smaller waves. This is called Rayleigh scattering.";
            } else if (text.includes("meaning") && text.includes("life")) {
                response = "The meaning of life is a subjective question, but many suggest it is to seek happiness, connection, and learning. In fiction, Douglas Adams famously wrote that the answer is 42.";
            } else {
                response = `I looked up "${query}" in standalone mode. It's a fascinating topic, but since I'm running client-side, I don't have Wikipedia or OpenAI active.`;
            }
        }
        // Roll dice
        else if (/\b(roll a dice|roll dice|roll die|cast dice)\b/.test(text)) {
            intent = "roll_dice";
            const res = Math.floor(Math.random() * 6) + 1;
            response = `I rolled a dice and got a ${res}.`;
        }
        // Flip coin
        else if (/\b(flip a coin|toss a coin|flip coin|toss coin)\b/.test(text)) {
            intent = "flip_coin";
            const res = Math.random() < 0.5 ? "heads" : "tails";
            response = `I flipped a coin and it landed on ${res}.`;
        }

        return {
            response: response,
            nlp: {
                intent: intent,
                entities: entities
            }
        };
    }
});
