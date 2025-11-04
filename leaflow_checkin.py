#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本 (严格三步流程版)
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import requests
from datetime import datetime
import os.path

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class XserverRenewal:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        if not self.username or not self.password or not self.server_id:
            raise ValueError("登录ID、密码或服务器标识符（XSERVER_SERVER_ID）不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动"""
        chrome_options = Options()
        
        # 无头模式配置
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            
        # 反爬虫配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            logger.info("正在配置 ChromeDriver...")
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功。")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element_clickable(self, by, value, timeout=30):
        """等待元素可点击（延长超时时间）"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def login(self):
        """登录流程"""
        logger.info(f"开始登录 Xserver 面板")
        
        self.driver.get("https://secure.xserver.ne.jp/xapanel/login/xmgame/game")
        time.sleep(5)
        
        try:
            # 输入登录信息
            self.wait_for_element_clickable(By.NAME, "username", 20).send_keys(self.username)
            self.wait_for_element_clickable(By.NAME, "server_identify", 20).send_keys(self.server_id)
            self.wait_for_element_clickable(By.NAME, "server_password", 20).send_keys(self.password)
            
            # 点击登录按钮
            self.wait_for_element_clickable(By.NAME, "b1", 15).click()
            logger.info("已点击登录按钮")
            
            # 等待跳转并验证登录成功
            WebDriverWait(self.driver, 30).until(
                lambda d: "game/index" in d.current_url or "管理" in d.page_source
            )
            logger.info("登录成功，进入游戏面板首页")
            return True
            
        except Exception as e:
            raise Exception(f"登录失败: {str(e)}")


    def renew_service(self):
        """严格三步续期流程"""
        try:
            # ======================== 步骤1：首页点击"アップグレード・期限延長" ========================
            logger.info("步骤1/3：查找首页续期入口按钮...")
            
            # 精确匹配首页绿色续期入口按钮
            entry_btn = self.wait_for_element_clickable(
                By.XPATH, "//a[contains(text(), 'アップグレード・期限延長')]", 30
            )
            
            # 强制滚动并点击
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", entry_btn)
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("✅ 已点击首页'アップグレード・期限延長'按钮")
            
            # 等待续期页加载（验证URL包含"extend"）
            WebDriverWait(self.driver, 30).until(
                lambda d: "extend" in d.current_url
            )
            time.sleep(5)  # 稳定页面
            logger.info("已跳转到续期页面")

            # ======================== 步骤2：续期页点击绿色"期限を延長する" ========================
            logger.info("步骤2/3：查找续期页绿色按钮...")
            
            # 精确匹配绿色"期限を延長する"按钮
            green_renew_btn = self.wait_for_element_clickable(
                By.XPATH, "//button[contains(text(), '期限を延長する')]", 30
            )
            
            # 强制滚动并点击
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", green_renew_btn)
            self.driver.execute_script("arguments[0].click();", green_renew_btn)
            logger.info("✅ 已点击绿色'期限を延長する'按钮")
            
            # 等待确认页加载
            WebDriverWait(self.driver, 30).until(
                lambda d: "confirm" in d.current_url or "check" in d.current_url
            )
            time.sleep(5)  # 稳定页面
            logger.info("已跳转到确认页面")

            # ======================== 步骤3：确认页点击最终提交按钮 ========================
            logger.info("步骤3/3：查找确认页提交按钮...")
            
            # 匹配确认页最终按钮（如"確認画面に進む"或"延長する"）
            final_confirm_btn = self.wait_for_element_clickable(
                By.XPATH, "//button[contains(text(), '確認画面に進む') or contains(text(), '延長する')]", 30
            )
            
            # 强制滚动并点击
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", final_confirm_btn)
            self.driver.execute_script("arguments[0].click();", final_confirm_btn)
            logger.info("✅ 已点击确认页最终提交按钮")
            
            # 验证续期成功
            WebDriverWait(self.driver, 30).until(
                lambda d: "更新完了" in d.page_source or "Renewal Complete" in d.page_source
            )
            return "✅ 服务续期成功！"

        except TimeoutException as te:
            return f"❌ 续期超时：未找到关键按钮 - {str(te)}"
        except Exception as e:
            return f"❌ 续期失败: {str(e)}"


    def run(self):
        """执行完整流程"""
        try:
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                return "✅" in result, result
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        finally:
            if self.driver:
                self.driver.quit()


class MultiAccountManager:
    """多账号管理器"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        """加载账号配置"""
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        
        if single_username and single_password:
            return [{'username': single_username, 'password': single_password}]
            
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            return [{'username': u.strip(), 'password': p.strip()} 
                    for u, p in [pair.split(':') for pair in accounts_str.split(',')]]
            
        raise ValueError("未找到有效的账号配置")
    
    def send_notification(self, results):
        """发送Telegram通知"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
            
        message = "🛠️ Xserver 自动续期结果\n"
        for username, success, result in results:
            status = "✅" if success else "❌"
            message += f"{status} {username[:3]}***: {result}\n"
        
        requests.post(
            f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
            data={"chat_id": self.telegram_chat_id, "text": message},
            timeout=10
        )
    
    def run_all(self):
        """运行所有账号续期"""
        results = []
        for account in self.accounts:
            try:
                renewal = XserverRenewal(account['username'], account['password'])
                success, result = renewal.run()
                results.append((account['username'], success, result))
            except Exception as e:
                results.append((account['username'], False, str(e)))
        
        self.send_notification(results)
        return all(r[1] for r in results), results


if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        success, results = manager.run_all()
        if not success:
            logger.error("部分账号续期失败")
            exit(1)
        logger.info("所有账号续期成功")
    except Exception as e:
        logger.error(f"脚本运行失败: {e}")
        exit(1)
