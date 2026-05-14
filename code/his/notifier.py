import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json
import os

class DingTalkNotifier:
    def __init__(self, webhook_url=None, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret
        
        # 如果初始化没传，尝试从 null.txt 加载
        if not self.webhook_url:
            self._load_config()

    def _load_config(self):
        """从 null.txt 解析配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'null.txt')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if 'ddpushurl=' in line:
                            self.webhook_url = line.split('ddpushurl=')[1].strip()
                        if 'ddsecret=' in line:
                            self.secret = line.split('ddsecret=')[1].strip()
        except Exception as e:
            print(f"加载配置失败: {e}")

    def _get_sign_url(self):
        """生成带签名的最终 webhook URL"""
        if not self.secret:
            return self.webhook_url
            
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def send_markdown(self, title, text):
        """发送 Markdown 格式的消息 (支持超长消息自动拆分)"""
        if not self.webhook_url:
            print("错误: 未找到钉钉 Webhook URL")
            return
            
        url = self._get_sign_url()
        headers = {'Content-Type': 'application/json'}
        
        # 钉钉单条限制约 20000 字节，此处取保守值 15000 字符进行切分
        limit = 15000
        chunks = [text[i:i+limit] for i in range(0, len(text), limit)]
        
        for idx, chunk in enumerate(chunks):
            current_title = f"{title} (Part {idx+1})" if len(chunks) > 1 else title
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": current_title,
                    "text": chunk
                }
            }
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
                response.raise_for_status()
                res_json = response.json()
                if res_json.get('errcode') == 0:
                    print(f"钉钉推送成功！(第 {idx+1}/{len(chunks)} 部分)")
                else:
                    print(f"钉钉推送返回错误: {res_json}")
            except Exception as e:
                print(f"钉钉推送失败: {e}")

if __name__ == "__main__":
    # 独立测试逻辑
    notifier = DingTalkNotifier()
    notifier.send_markdown("推送测试", "### 🤖 机器人连接成功\n- 状态: 正常\n- 时间: " + time.strftime("%H:%M:%S"))
