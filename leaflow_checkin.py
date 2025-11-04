#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本（针对确认按钮优化版）

使用方法：
在运行环境中设置以下环境变量/Secrets：
1. 单账号模式（推荐）：
    - XSERVER_USERNAME：您的 Xserver 登录ID
    - XSERVER_PASSWORD：您的 Xserver 密码
    - XSERVER_SERVER_ID：您的 Xserver 服务器标识符/客户ID (必填项)
2. 多账号模式（次选）：
    - XSERVER_ACCOUNTS：ID1:Pass1,ID2:Pass2,... (逗号分隔)

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
import os.path

# 导入 webdriver-manager 相关的库
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
        """设置Chrome驱动选项"""
        chrome_options = Options()
        
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功")
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element_clickable(self, by, value, timeout=20):
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def _save_screenshot(self, prefix):
        """保存截图用于调试"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"已保存截图: {filename}")
        except Exception as e:
            logger.error(f"保存截图失败: {e}")
    
    def login(self):
        """执行 Xserver 登录流程"""
        logger.info(f"开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(5)
        
        try:
            # 1. 登录 ID
            username_input = self.wait_for_element_clickable(By.NAME, "username", 15)
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info("登录ID输入完成")
            time.sleep(1)

            # 2. 服务器标识符
            logger.info(f"输入服务器标识符: {self.server_id}")
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.clear()
            server_id_input.send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            time.sleep(1)
            
            # 3. 密码
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
            
            # 4. 登录按钮
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
            
            # 等待跳转
            WebDriverWait(self.driver, 20).until(
                lambda driver: "username" not in driver.current_url
            )
            time.sleep(5)

            # 检查登录成功
            try:
                manage_link = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(text(), '管理')] | //button[contains(text(), '管理')]"
                )
                logger.info("登录成功，点击管理链接...")
                manage_link.click()
                time.sleep(10)
                return True
            except NoSuchElementException:
                if "game/index" in self.driver.current_url:
                    logger.info("登录成功，直接进入主页")
                    return True
                raise Exception("登录成功但未找到管理链接")
            
        except Exception as e:
            self._save_screenshot("login_error")
            raise Exception(f"登录失败: {str(e)}")

    def _check_final_result(self):
        """检查续期结果（优化版）"""
        current_url = self.driver.current_url
        
        # 主要判断条件：到达确认页面即视为成功
        if "confirm" in current_url.lower() or "extend/input" in current_url:
            return "✅ 服务续期成功！已到达确认页面"
        
        # 检查成功关键词
        success_phrases = ["更新完了", "Renewal Complete", "更新されました"]
        if any(phrase in self.driver.page_source for phrase in success_phrases):
            return "✅ 服务续期成功！"
        
        # 检查错误信息
        error_elements = self.driver.find_elements(
            By.XPATH, 
            "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]"
        )
        if error_elements:
            error_text = error_elements[0].text[:200]
            return f"❌ 续期失败：{error_text}"
        
        return f"❌ 续期失败：未找到明确结果。当前URL: {current_url}"

    def renew_service(self):
        """执行续期操作（针对确认按钮优化）"""
        logger.info("开始续期流程...")
        time.sleep(5)
        
        try:
            # 1. 查找并点击续期入口按钮
            entry_btn_selectors = [
                "//a[contains(@href, 'extend')]",
                "//button[contains(., '延長')]",
                "//a[contains(., '延長')]"
            ]
            
            entry_btn = None
            for selector in entry_btn_selectors:
                try:
                    entry_btn = self.wait_for_element_clickable(By.XPATH, selector, 10)
                    break
                except TimeoutException:
                    continue
                    
            if not entry_btn:
                raise NoSuchElementException("无法定位续期入口按钮")
                
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("已点击续期入口按钮")
            
            # 2. 等待进入续期页面
            WebDriverWait(self.driver, 20).until(
                lambda d: "extend" in d.current_url.lower()
            )
            logger.info(f"已进入续期页面: {self.driver.current_url}")
            self._save_screenshot("renewal_page")
            
            # 3. 直接定位并点击确认按钮（核心修改）
            confirm_btn_selectors = [
                "//button[contains(., '確認画面に進む')]",  # 精确匹配确认按钮
                "//button[contains(., '確認')]",  # 模糊匹配确认按钮
                "//a[contains(., '確認')]"  # 链接形式的确认按钮
            ]
            
            confirm_btn = None
            for selector in confirm_btn_selectors:
                try:
                    confirm_btn = self.wait_for_element_clickable(By.XPATH, selector, 15)
                    break
                except TimeoutException:
                    continue
                    
            if not confirm_btn:
                raise NoSuchElementException("无法定位确认按钮")
                
            # 确保按钮可见并点击
            self.driver.execute_script("arguments[0].scrollIntoView();", confirm_btn)
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            logger.info("✅ 已点击确认按钮")
            
            # 4. 检查结果
            time.sleep(5)  # 等待页面跳转
            return self._check_final_result()

        except TimeoutException as te:
            self._save_screenshot("renewal_timeout")
            return f"❌ 续期操作超时: {str(te)}"
        except Exception as e:
            self._save_screenshot("renewal_error")
            return f"❌ 续期过程中发生错误: {str(e)}"
    
    def run(self):
        """执行单个账号的完整续期流程"""
        try:
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                return "✅" in result, result, ""
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, ""
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
        """从环境变量加载账号信息"""
        accounts = []
        
        # 单账号模式
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        if single_username and single_password:
            accounts.append({'username': single_username, 'password': single_password})
            return accounts
            
        # 多账号模式
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            for pair in accounts_str.split(','):
                if ':' in pair:
                    username, password = pair.split(':', 1)
                    if username.strip() and password.strip():
                        accounts.append({'username': username.strip(), 'password': password.strip()})
        
        if not accounts:
            raise ValueError("未找到有效的账号配置")
        return accounts
    
    def send_notification(self, results):
        """发送通知"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
            
        message = "🛠️ Xserver 续期结果\n"
        for username, success, result, _ in results:
            status = "✅" if success else "❌"
            message += f"\n账号: {username[:3]}***\n{status} {result}"
            
        requests.post(
            f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
            data={"chat_id": self.telegram_chat_id, "text": message}
        )
    
    def run_all(self):
        """运行所有账号"""
        results = []
        for account in self.accounts:
            renewal = XserverRenewal(account['username'], account['password'])
            results.append((account['username'], *renewal.run()))
            time.sleep(5)
            
        self.send_notification(results)
        success_count = sum(1 for _, success, _, _ in results if success)
        return success_count == len(self.accounts), results

if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        success, _ = manager.run_all()
        exit(0 if success else 1)
    except Exception as e:
        logger.error(f"脚本运行失败: {str(e)}")
        exit(1)
