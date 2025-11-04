#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本 (单账号版)

使用方法：
在运行环境中设置以下环境变量/Secrets：
设置以下环境变量/Secrets：
- XSERVER_USERNAME：您的 Xserver 登录ID
- XSERVER_PASSWORD：您的 Xserver 密码
- XSERVER_SERVER_ID：您的 Xserver 服务器标识符/客户ID

可选通知：
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, ElementClickInterceptedException, StaleElementReferenceException
import requests
from datetime import datetime

# 导入 webdriver-manager 相关的库
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class XserverRenewal:
    def __init__(self):
        self.username = os.getenv('XSERVER_USERNAME', '').strip()
        self.password = os.getenv('XSERVER_PASSWORD', '').strip()
        self.server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        # 验证所有必要凭证
        if not self.username or not self.password or not self.server_id:
            raise ValueError("登录ID、密码或服务器标识符（XSERVER_SERVER_ID）不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项并自动管理ChromeDriver"""
        chrome_options = Options()
        
        # GitHub Actions环境配置 (无头模式)
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
        # 通用配置：反爬虫检测
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # 自动下载并配置 ChromeDriver
            logger.info("正在自动下载并配置 ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element(self, by, value, timeout=20, clickable=True):
        """等待元素出现或可点击"""
        wait = WebDriverWait(self.driver, timeout)
        if clickable:
            return wait.until(EC.element_to_be_clickable((by, value)))
        return wait.until(EC.presence_of_element_located((by, value)))
    
    def login(self):
        """执行登录流程"""
        logger.info("开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(3)
        
        try:
            # 输入登录信息
            self.wait_for_element(By.NAME, "username").send_keys(self.username)
            self.wait_for_element(By.NAME, "server_identify").send_keys(self.server_id)
            self.wait_for_element(By.NAME, "server_password").send_keys(self.password)
            
            # 点击登录按钮
            self.wait_for_element(By.NAME, "b1").click()
            logger.info("已点击登录按钮")
            
            # 等待跳转并验证登录成功
            WebDriverWait(self.driver, 20).until(
                lambda d: "game/index" in d.current_url
            )
            logger.info("登录成功，已进入游戏面板首页")
            return True
            
        except Exception as e:
            self.driver.save_screenshot("login_error.png")
.save_screenshot("login_error.png")
            raise Exception(f"登录失败: {str(e)}")

    def renew_service(self):
        """执行续期流程"""
        logger.info("开始执行续期流程...")
        time.sleep(5)
        
        try:
            # 步骤1：点击续期入口按钮
            logger.info("查找续期入口按钮...")
            entry_btn = self.wait_for_element(
                By.XPATH, 
                "//a[@href='/xmgame/game/freeplan/extend/input'] or //button[contains(text(), '期限延長')]",
                clickable=True
            )
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("已点击续期入口按钮")
            
            # 等待跳转
            time.sleep(10)
            
            # 步骤2：点击确认按钮
            logger.info("查找确认按钮...")
            confirm_btn = self.wait_for_element(
                By.XPATH,
                "//button[contains(text(), '確認') or contains(text(), 'Confirm')]",
                clickable=True
            )
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            logger.info("已点击确认按钮")
            
            # 验证结果
            time.sleep(5)
            if "更新完了" in self.driver.page_source:
                return "✅ 服务续期成功！"
            elif "更新済み" in self.driver.page_source:
                return "⚠️ 服务已是最新状态，无需续期"
            else:
                return "⚠️ 续期流程已完成，请手动确认结果"

        except Exception as e:
            self.driver.save_screenshot("renewal_error.png")
            return f"❌ 续期失败: {str(e)}"

    def send_notification(self, message):
        """发送Telegram通知"""
        token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        if not token or not chat_id:
            logger.info("Telegram配置未设置，跳过通知")
            return
            
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": f"Xserver续期结果:\n{message}",
                "parse_mode": "HTML"
            }
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}")

    def run(self):
        """执行完整续期流程"""
        try:
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                self.send_notification(result)
                return result
            return "登录失败"
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            self.send_notification(error_msg)
            return error_msg
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    try:
        renewal = XserverRenewal()
        result = renewal.run()
        if "成功" in result or "✅" in result:
            exit(0)
        else:
            exit(1)
    except Exception as e:
        logger.error(f"脚本运行失败: {e}")
        exit(1)
