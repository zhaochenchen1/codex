import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json
from code.longtou.config import Config
from code.longtou.logger import setup_logger

logger = setup_logger(__name__)

class DingTalkNotifier:
    """钉钉推送管理类"""
    
    def __init__(self):
        self.webhook_url = Config.DINGTALK_WEBHOOK
        self.secret = Config.DINGTALK_SECRET

    def _get_sign_url(self):
        if not self.secret:
            return self.webhook_url
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def send_report(self, title, content):
        """发送 Markdown 报告"""
        if not self.webhook_url:
            logger.error("未配置钉钉 Webhook")
            return
            
        url = self._get_sign_url()
        headers = {'Content-Type': 'application/json'}
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
            if resp.json().get('errcode') == 0:
                logger.info("钉钉推送成功")
            else:
                logger.error(f"钉钉推送失败: {resp.text}")
        except Exception as e:
            logger.error(f"推送异常: {e}")
