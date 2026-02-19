# Oracle Cloud 免費 VM 部署指南

## 1. 註冊帳號
1. 前往 https://www.oracle.com/cloud/free/
2. 點「Start for free」
3. Region 選 **Japan East (Tokyo)** 或 **South Korea (Chuncheon)**
4. 需要信用卡驗證（不會扣款）

## 2. 建立 VM
1. 登入 Oracle Cloud Console
2. 點「Create a VM instance」
3. 設定：
   - **Name**: `nexus-ai`
   - **Image**: Ubuntu 22.04（或 24.04）
   - **Shape**: 點「Change shape」→ 選 **Ampere** → **VM.Standard.A1.Flex**
     - OCPU: **4**（免費上限）
     - Memory: **24 GB**（免費上限）
   - **SSH Key**: 下載或上傳你的 SSH key
4. 點「Create」

## 3. 設定安全規則（開放 8000 端口）
1. 進入 VM 詳情頁 → 點 Subnet 連結
2. 點 Default Security List
3. 點「Add Ingress Rules」：
   - Source CIDR: `0.0.0.0/0`
   - Destination Port: `8000`
4. 儲存

## 4. 連線到 VM
```bash
ssh -i your_key.pem ubuntu@你的VM公開IP
```

## 5. 一鍵部署
```bash
# 下載部署腳本
curl -sL https://raw.githubusercontent.com/xushuowen/nexus-ai/master/deploy/oracle_setup.sh -o setup.sh
chmod +x setup.sh
./setup.sh
```

## 6. 填入 API Keys
```bash
nano ~/nexus-ai/.env
```
填入：
- `GROQ_API_KEY=你的key`
- `GEMINI_API_KEY=你的key`
- `TELEGRAM_BOT_TOKEN=你的token`
- `NEXUS_SECRET_KEY=隨便一組密碼`

然後重新執行：
```bash
./setup.sh
```

## 7. 完成！
- Telegram Bot 24/7 運作
- 查看日誌: `sudo journalctl -u nexus -f`
- 更新: `cd ~/nexus-ai && git pull && sudo systemctl restart nexus`

## 費用
**$0** — Oracle Always Free Tier 永久免費，不會自動升級收費。
