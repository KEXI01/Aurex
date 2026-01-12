<h1 align="center">🎶 OPUS — uv Asynced + Music Bot</h1>

<p align="center">
  <a href="https://github.com/KEXI01/Aurex/stargazers"><img src="https://img.shields.io/github/stars/KEXI01/Aurex?style=for-the-badge&color=yellow" /></a>
  <a href="https://github.com/KEXI01/Aurex/fork"><img src="https://img.shields.io/github/forks/KEXI01/Aurex?style=for-the-badge&color=orange" /></a>
  <a href="https://github.com/KEXI01/Aurex/graphs/contributors"><img src="https://img.shields.io/github/contributors/KEXI01/Aurex?style=for-the-badge&color=blueviolet" /></a>
  <a href="https://github.com/KEXI01/Aurex"><img src="https://img.shields.io/badge/pyrofork-2.3.69-ff3366?style=for-the-badge&logo=telegram&logoColor=white" /></a>
  <a href="https://www.mongodb.com/"><img src="https://img.shields.io/badge/MongoDB-Enabled-success?style=for-the-badge&logo=mongodb&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/License-GPL-blue?style=for-the-badge" /></a>
</p>

---

### 🪩 Overview
**Opus** is a next-generation **asynchronous Telegram Music Bot** powered by **pyrotgfork v2.2.16**, **uvloop**, and **yt-dlp**.  
It delivers high-quality music streaming in Telegram voice chats with MongoDB persistence, advanced caching, and a modular async design.  
Fully deployable on **Heroku**, **Render**, **Railway**, **Koyeb**, **Docker**, or any **VPS**.

---

### ✨ Core Features
- ⚡ **Asynced + Uvlooped event loop (blazing-fast performance)**
- 🎧 **Voice Chat Music Streaming (Py-TGCalls + NTGCalls)**
- 🔍 **YouTube Search via youtube-search-python 1.6.6+master**
- 📦 **Queue & Youtube Music Playlist Management**
- 🧠 **MongoDB User & Group Tracking For Sudoers**
- 🕹️ **Inline Keyboard Controls**
- 🧰 **CLI Drivers for Media Forwarding to Telegram**
- 🐳 **Docker / VPS Ready**
- 💬 **Supports up to 5 String Sessions**

---

### ⚙️ Environment Variables
Create your `.env` file (`vi .env`) and fill:

```bash
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
MONGO_DB_URI=mongodb+srv://your_mongo_connection
LOGGER_ID=-1001234567890
OWNER_ID=123456789
STRING_SESSION=session_1,session_2,session_3,session_4,session_5
API_URL=https://api.example.com
```

---

### 🧩 Project Structure
```
Aurex/
├── src/                  # Core async modules
├── strings/              # Localized responses
├── config.py             # Env loader
├── drivers.py            # CLI media forwarder
├── drivers2.py           # Legacy version
├── requirements.txt      # Dependencies
├── Dockerfile            # Container setup
├── .env                  # Example vars
└── start                 # Bash launcher
```

---

### 💻 Installation

#### • VPS / Local Setup
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip ffmpeg -y
git clone https://github.com/KEXI01/Aurex
cd Aurex
pip install -U pip wheel setuptools
pip install -r requirements.txt
vi .env   # Fill environment vars
bash start
```

#### • Docker
```bash
docker build -t aurex .
docker run --env-file .env aurex
```

#### • Heroku / Render / Railway / Koyeb
- Add all `.env` vars in your platform’s environment config.
- Deploy directly — Aurex auto-runs via `bash start`.

---

### 🧠 Tech Stack
- **Python 3.10+**
- **pyrotgfork v2.2.16**
- **yt-dlp (master)**
- **Py-TGCalls 1.2.9 / NTGCalls 1.1.2**
- **uvloop / asyncio**
- **MongoDB (motor)**
- **aiofiles / aiohttp / httpx[http2]**
- **Flask / Flask-RESTful**
- **BeautifulSoup4 / Pillow / Psutil / Rich / Watchdog / Orjson**

---

### 📸 Preview
<p align="center">
  <img src="https://te.legra.ph/file/ea1d8e42aurex1.jpg" width="280" />
  <img src="https://te.legra.ph/file/34a1c57aurex2.jpg" width="280" />
  <img src="https://te.legra.ph/file/7f2b83aurex3.jpg" width="280" />
</p>

---

### 👥 Contributors
<a href="https://github.com/KEXI01/Aurex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=KEXI01/Aurex" />
</a>

- **[K Σ X ! (KEXI01)](https://github.com/KEXI01)** — Lead Developer  
- **[BillaSpace (Prakhar Shukla)](https://github.com/BillaSpace)** — Core Contributor  

---

### 💜 Special Thanks
Special appreciation to the **[Yukki Music Bot](https://github.com/TeamYukki)** project and its developers — Aurex’s async architecture was inspired and evolved from their open-source work.

---

### 🧾 License
Licensed under the **GNU General Public License (GPL)**.  
You are free to modify and distribute the code under GPL terms.

---

<p align="center">
  <b>🚀 Fast • Modular • Asynchronous — Built on pyrotgfork + uvloop</b>
</p>
