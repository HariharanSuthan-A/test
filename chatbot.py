from flask import Flask, request, jsonify, render_template_string, session
from flask_session import Session
import ollama
import uuid
import time
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# In-memory chat history storage (replace with database in production)
chat_history = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CodeMind AI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --background: #0f172a;
            --surface: #1e293b;
            --text: #f8fafc;
            --border: #334155;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--background);
            color: var(--text);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .logo {
            font-weight: 600;
            color: var(--primary);
        }

        .chat-history {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .message {
            max-width: 70%;
            padding: 1rem;
            border-radius: 1rem;
            animation: fadeIn 0.3s ease-in;
        }

        .user-message {
            background: var(--primary);
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }

        .bot-message {
            background: var(--surface);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }

        .typing-indicator {
            display: none;
            padding: 1rem;
            align-items: center;
            gap: 0.5rem;
            color: #94a3b8;
        }

        .dot-flashing {
            position: relative;
            width: 8px;
            height: 8px;
            border-radius: 4px;
            background-color: #94a3b8;
            animation: dotFlashing 1s infinite linear;
        }

        .input-container {
            padding: 1.5rem;
            border-top: 1px solid var(--border);
            background: var(--surface);
        }

        .input-wrapper {
            display: flex;
            gap: 0.5rem;
            max-width: 800px;
            margin: 0 auto;
        }

        input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border);
            border-radius: 0.5rem;
            background: var(--background);
            color: var(--text);
            outline: none;
        }

        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            background: var(--primary);
            color: white;
            cursor: pointer;
            transition: background 0.2s;
        }

        button:hover {
            background: var(--primary-hover);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes dotFlashing {
            0% { background-color: #94a3b8; }
            50%, 100% { background-color: rgba(148, 163, 184, 0.2); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-header">
            <div class="logo">CodeMind AI</div>
        </div>
        
        <div class="chat-history" id="chatHistory"></div>
        
        <div class="typing-indicator" id="typingIndicator">
            <div class="dot-flashing"></div>
            <span>Generating response...</span>
        </div>

        <div class="input-container">
            <div class="input-wrapper">
                <input type="text" id="userInput" placeholder="Ask me anything about programming..." />
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>

    <script>
        const chatHistory = document.getElementById('chatHistory');
        const userInput = document.getElementById('userInput');
        const typingIndicator = document.getElementById('typingIndicator');
        let sessionId = localStorage.getItem('sessionId') || '${str(uuid.uuid4())}';

        function addMessage(text, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            messageDiv.textContent = text;
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            addMessage(message, true);
            userInput.value = '';
            typingIndicator.style.display = 'flex';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Session-ID': sessionId
                    },
                    body: JSON.stringify({ message })
                });

                const data = await response.json();
                addMessage(data.response, false);
                localStorage.setItem('sessionId', sessionId);
            } catch (error) {
                addMessage('Connection error. Please try again.', false);
            } finally {
                typingIndicator.style.display = 'none';
            }
        }

        // Load previous chat history
        window.addEventListener('load', async () => {
            try {
                const response = await fetch(`/history?sessionId=${sessionId}`);
                const history = await response.json();
                history.forEach(msg => {
                    addMessage(msg.content, msg.role === 'user');
                });
            } catch (error) {
                console.error('Error loading history:', error);
            }
        });

        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        session_id = request.headers.get('X-Session-ID', str(uuid.uuid4()))
        data = request.get_json()
        
        # Store user message
        if session_id not in chat_history:
            chat_history[session_id] = []
        chat_history[session_id].append({
            'role': 'user',
            'content': data['message'],
            'timestamp': time.time()
        })

        # Generate response
        response = ollama.generate(
            model="gemma3:1b",
            prompt=data['message'],
            stream=False
        )

        # Store bot response
        chat_history[session_id].append({
            'role': 'assistant',
            'content': response['response'],
            'timestamp': time.time()
        })

        return jsonify({'response': response['response']})

    except Exception as e:
        return jsonify({'response': f"Error: {str(e)}"}), 500

@app.route('/history')
def get_history():
    session_id = request.args.get('sessionId')
    return jsonify(chat_history.get(session_id, []))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)