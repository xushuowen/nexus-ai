#!/bin/bash
# ============================================
# Nexus AI — Oracle Cloud Free VM 一鍵部署腳本
# 在 Oracle VM 上執行此腳本即可完成部署
# ============================================

set -e

echo "🚀 Nexus AI Oracle Cloud 部署開始..."

# 1. 系統更新
echo "📦 更新系統..."
sudo apt update && sudo apt upgrade -y

# 2. 安裝 Python 3.12
echo "🐍 安裝 Python 3.12..."
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip git

# 3. Clone 專案
echo "📥 下載 Nexus AI..."
cd ~
if [ -d "nexus-ai" ]; then
    cd nexus-ai
    git pull origin master
else
    git clone https://github.com/xushuowen/nexus-ai.git
    cd nexus-ai
fi

# 4. 建立虛擬環境
echo "🔧 建立 Python 虛擬環境..."
python3.12 -m venv venv
source venv/bin/activate

# 5. 安裝依賴
echo "📦 安裝依賴套件..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. 設定環境變數
echo "🔑 設定環境變數..."
if [ ! -f .env ]; then
    cat > .env << 'ENVEOF'
# === Nexus AI 環境變數 ===
# 請填入你的 API Keys
GROQ_API_KEY=你的_GROQ_KEY
GEMINI_API_KEY=你的_GEMINI_KEY
TELEGRAM_BOT_TOKEN=你的_TELEGRAM_TOKEN
NEXUS_SECRET_KEY=你的_SECRET_KEY

# 伺服器設定
PORT=8000
HOST=0.0.0.0
ENVEOF
    echo "⚠️  請編輯 .env 檔案填入你的 API Keys："
    echo "    nano ~/nexus-ai/.env"
    echo ""
    echo "填完後重新執行此腳本或執行："
    echo "    sudo systemctl restart nexus"
    exit 0
fi

# 載入環境變數
export $(grep -v '^#' .env | xargs)

# 7. 建立 systemd 服務（開機自動啟動）
echo "⚙️  設定系統服務..."
sudo tee /etc/systemd/system/nexus.service > /dev/null << SERVICEEOF
[Unit]
Description=Nexus AI Multi-Agent Assistant
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/nexus-ai
EnvironmentFile=$HOME/nexus-ai/.env
ExecStart=$HOME/nexus-ai/venv/bin/python -m nexus.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

# 8. 啟動服務
echo "🚀 啟動 Nexus AI..."
sudo systemctl daemon-reload
sudo systemctl enable nexus
sudo systemctl start nexus

# 9. 開放防火牆 (Oracle Cloud 需要)
echo "🔓 開放防火牆端口..."
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo apt install -y iptables-persistent
sudo netfilter-persistent save

# 10. 等待啟動
echo "⏳ 等待服務啟動..."
sleep 10

# 11. 驗證
echo ""
echo "============================================"
echo "📊 服務狀態："
sudo systemctl status nexus --no-pager -l | head -20
echo ""
echo "============================================"

# 測試 API
if curl -s http://localhost:8000/api/status | python3.12 -m json.tool 2>/dev/null; then
    echo ""
    echo "✅ Nexus AI 部署成功！"
    echo ""
    echo "📌 重要資訊："
    echo "   API: http://$(curl -s ifconfig.me):8000/api/status"
    echo "   Telegram Bot: 已自動連線"
    echo ""
    echo "📝 常用命令："
    echo "   查看狀態: sudo systemctl status nexus"
    echo "   查看日誌: sudo journalctl -u nexus -f"
    echo "   重啟服務: sudo systemctl restart nexus"
    echo "   停止服務: sudo systemctl stop nexus"
    echo "   更新程式: cd ~/nexus-ai && git pull && sudo systemctl restart nexus"
else
    echo "⚠️  服務可能還在啟動中，請稍後檢查："
    echo "   sudo journalctl -u nexus -f"
fi
