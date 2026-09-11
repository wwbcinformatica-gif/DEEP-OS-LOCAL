const express = require('express');
const cors = require('cors');
const http = require('http');
const { Server } = require('socket.io');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

app.use(cors());
app.use(express.json());

const PORT = 8010;
const DATA_DIR = path.join(__dirname, 'data');
const CONFIG_FILE = path.join(DATA_DIR, 'chatbot-config.json');
const STORE_FILE = path.join(DATA_DIR, 'chatbot-data.json');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
  } catch (e) {}
  return { provider: 'ollama', ollama_url: 'http://localhost:11434', ollama_model: 'llama3' };
}

function saveConfig(config) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

function loadData() {
  try {
    if (fs.existsSync(STORE_FILE)) return JSON.parse(fs.readFileSync(STORE_FILE, 'utf8'));
  } catch (e) {}
  return { contacts: [], messages: [], campaigns: [] };
}

function saveData(data) {
  fs.writeFileSync(STORE_FILE, JSON.stringify(data, null, 2));
}

// Health check
app.get('/api/chatbot/status', (req, res) => {
  res.json({ status: 'ok', port: PORT, uptime: process.uptime() });
});

// Config
app.get('/api/chatbot/config', (req, res) => {
  res.json(loadConfig());
});

app.post('/api/chatbot/config', (req, res) => {
  saveConfig(req.body);
  res.json({ success: true });
});

// Test provider
app.post('/api/chatbot/test', async (req, res) => {
  const { provider, message } = req.body;
  const config = loadConfig();

  try {
    if (provider === 'ollama') {
      const ollamaRes = await fetch(`${config.ollama_url}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: config.ollama_model, prompt: message, stream: false }),
      });
      const data = await ollamaRes.json();
      res.json({ response: data.response || 'Sem resposta do Ollama' });
    } else if (provider === 'gemini') {
      res.json({ response: 'Gemini configurado - teste com API key no backend' });
    } else if (provider === 'openai') {
      res.json({ response: 'OpenAI configurado - teste com API key no backend' });
    } else {
      res.json({ error: 'Nenhum provider configurado' });
    }
  } catch (e) {
    res.json({ error: `Erro ao conectar: ${e.message}` });
  }
});

// WhatsApp connect (placeholder)
app.post('/api/chatbot/connect', (req, res) => {
  res.json({ status: 'connecting', message: 'WhatsApp connection requires whatsapp-web.js' });
});

// Contacts
app.get('/api/chatbot/contacts', (req, res) => {
  const data = loadData();
  res.json(data.contacts || []);
});

// Messages
app.get('/api/chatbot/messages', (req, res) => {
  const data = loadData();
  res.json(data.messages || []);
});

app.post('/api/chatbot/messages', (req, res) => {
  const data = loadData();
  if (!data.messages) data.messages = [];
  data.messages.push({ ...req.body, id: Date.now().toString(), timestamp: new Date().toISOString() });
  saveData(data);
  res.json({ success: true });
});

// Campaigns
app.get('/api/chatbot/campaigns', (req, res) => {
  const data = loadData();
  res.json(data.campaigns || []);
});

app.post('/api/chatbot/campaigns', (req, res) => {
  const data = loadData();
  if (!data.campaigns) data.campaigns = [];
  data.campaigns.push({ ...req.body, id: Date.now().toString(), created: new Date().toISOString() });
  saveData(data);
  res.json({ success: true });
});

// Socket.IO for real-time
io.on('connection', (socket) => {
  console.log('[ChatBot] Client connected:', socket.id);
  socket.on('disconnect', () => console.log('[ChatBot] Client disconnected:', socket.id));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[ChatBot] Gateway running on http://127.0.0.1:${PORT}`);
  console.log(`[ChatBot] Status: http://127.0.0.1:${PORT}/api/chatbot/status`);
});
