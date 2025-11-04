#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本（单账号版）
"""

import os
import time
import logging
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, ElementNotInteractableException
)
import requests
from datetime import datetime

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class XserverRenewal:
    def __init__(self, username, password, server_id):
        self.username = username
        self.password = password
        self.server_id = server_id
        
        if not all([self.username, self.password, self.server_id]):
            raise ValueError("登录ID、密码或服务器标识符不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动（彻底修复路径问题）"""
        chrome_options = Options()
        
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--remote-debugging-port=9222')
            
        # 反爬虫配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            logger.info("正在配置 ChromeDriver...")
            
            # 核心修复：获取驱动缓存目录，直接查找可执行文件
            driver_cache_dir = ChromeDriverManager().install()
            # 向上追溯找到真正的驱动目录（排除文件路径）
            while not os.path.isdir(driver_cache_dir):
                driver_cache_dir = os.path.dirname(driver_cache_dir)
            
            # 递归查找所有chromedriver可执行文件
            chromedriver_paths = glob.glob(os.path.join(driver_cache_dir, '**', 'chromedriver'), recursive=True)
            # 筛选出可执行的文件
            valid_driver_paths = [path for path in chromedriver_paths if os.path.isfile(path) and os.access(path, os.X_OK)]
            
            if not valid_driver_paths:
                raise FileNotFoundError(f"在缓存目录中未找到可执行的chromedriver: {driver_cache_dir}")
            
            # 使用第一个有效路径
            driver_path = valid_driver_paths[0]
            logger.info(f"找到可执行的ChromeDriver: {driver_path}")

            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            logger.info("Chrome 驱动启动成功")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element_clickable(self, by, value, timeout=30):
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=30):
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def login(self):
        """执行登录流程"""
        logger.info("开始登录 Xserver 面板")
        self.driver.get("https://secure.xserver.ne.jp/xapanel/login/xmgame/game")
        time.sleep(3)
        
        try:
            # 输入登录信息
            self.wait_for_element_clickable(By.NAME, "username").send_keys(self.username)
            logger.info("登录ID输入完成")
            time.sleep(1)
            
            self.wait_for_element_clickable(By.NAME, "server_identify").send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            time.sleep(1)
            
            self.wait_for_element_clickable(By.NAME, "server_password").send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
            
            # 点击登录按钮
            self.wait_for_element_clickable(By.NAME, "b1").click()
            logger.info("已点击登录按钮")
            
            # 等待登录跳转
            WebDriverWait(self.driver, 30).until(
                lambda d: "login" not in d.current_url.lower()
            )
            time.sleep(5)

            # 处理管理链接点击
            try:
                manage_link = self.driver.find_element(
                    By.XPATH, "//a[contains(text(), '管理')] | //button[contains(text(), '管理')]"
                )
                self.driver.execute_script("arguments[0].click();", manage_link)
                logger.info("已点击管理链接，等待页面加载")
                time.sleep(8)
                return True
                
            except NoSuchElementException:
                if "game/index" in self.driver.current_url:
                    logger.info("已在游戏面板主页，无需点击管理链接")
                    return True
                raise Exception("登录后未找到管理页面入口")
            
        except Exception as e:
            raise Exception(f"登录失败: {str(e)}")

    def _check_final_result(self):
        """检查续期结果"""
        page_source = self.driver.page_source
        if any(msg in page_source for msg in ["更新完了", "Renewal Complete", "更新されました"]):
            return "✅ 服务续期成功！"
        if any(msg in page_source for msg in ["更新済み", "Already Renewed"]):
            return "✅ 今日已续期"
            
        # 查找错误信息
        error_elements = self.driver.find_elements(
            By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert') or contains(text(), 'エラー')]"
        )
        if error_elements:
            return f"❌ 续期失败：{error_elements[0].text[:200]}"
        
        return "❌ 续期失败：未找到明确结果，请手动检查"

    def renew_service(self):
        """执行续期操作"""
        logger.info("开始查找续期入口按钮")
        time.sleep(5)
        
        try:
            # 1. 查找续期入口按钮
            entry_xpaths = [
                "//a[@href='/xmgame/game/freeplan/extend/input']",
                "//a[contains(@href, 'extend') and contains(text(), '延長')]",
                "//button[contains(text(), '期限延長') or contains(text(), '延長手続き')]",
                "//a[contains(text(), '無料延長') or contains(text(), '期間延長')]"
            ]
            
            entry_btn = None
            for xpath in entry_xpaths:
                try:
                    entry_btn = self.wait_for_element_clickable(By.XPATH, xpath, 10)
                    break
                except TimeoutException:
                    continue
            
            if not entry_btn:
                raise Exception("未找到续期入口按钮，请检查页面结构")
            
            # 点击入口按钮
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("已点击续期入口按钮，等待页面跳转")
            time.sleep(10)

            # 2. 处理续期确认按钮
            confirm_xpaths = [
                "//button[contains(text(), '延長手続きを行う')]",
                "//button[contains(text(), '確認画面に進む') or contains(text(), '次へ')]",
                "//input[@type='submit' and contains(@value, '延長')]",
                "//a[contains(text(), '延長を確定') or contains(text(), '最終確認')]",
                "//button[contains(text(), '更新する') or contains(text(), '申し込む')]"
            ]
            
            # 最多尝试5次点击
            for attempt in range(5):
                try:
                    confirm_btn = None
                    for xpath in confirm_xpaths:
                        try:
                            confirm_btn = self.wait_for_element_clickable(By.XPATH, xpath, 15)
                            break
                        except TimeoutException:
                            continue
                    
                    if not confirm_btn:
                        time.sleep(5)
                        continue
                    
                    self.driver.execute_script("arguments[0].click();", confirm_btn)
                    logger.info(f"第 {attempt+1} 次点击确认按钮成功")
                    time.sleep(8)
                    
                except (StaleElementReferenceException, ElementNotInteractableException):
                    logger.warning(f"第 {attempt+1} 次点击失败，重试中...")
                    time.sleep(5)
                    continue
            
            # 3. 检查最终结果
            return self._check_final_result()

        except TimeoutException:
            return "❌ 续期超时：未找到确认按钮，请检查按钮定位表达式"
        except Exception as e:
            return f"❌ 续期失败：{str(e)}"

    def run(self):
        """执行完整续期流程"""
        try:
            logger.info(f"开始处理账号: {self.username[:3] + '***'}")
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                return "✅" in result or "已续期" in result, result
            return False, "登录失败"
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        finally:
            if self.driver:
                self.driver.quit()


def send_telegram_notification(result, username):
    """发送Telegram通知"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    if not bot_token or not chat_id:
        return
    
    try:
        message = (f"🛠️ Xserver 续期通知\n"
                   f"📅 {datetime.now().strftime('%Y/%m/%d %H:%M')}\n"
                   f"账号: {username[:3] + '***'}\n"
                   f"结果: {result}")
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=10
        )
    except Exception as e:
        logger.error(f"Telegram通知失败: {e}")


if __name__ == "__main__":
    try:
        # 读取环境变量
        username = os.getenv('XSERVER_USERNAME', '').strip()
        password = os.getenv('XSERVER_PASSWORD', '').strip()
        server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        if not all([username, password, server_id]):
            raise ValueError("请设置所有必要的环境变量")
        
        # 执行续期
        renewal = XserverRenewal(username, password, server_id)
        success, result = renewal.run()
        send_telegram_notification(result, username)
        
        if not success:
            logger.error("续期失败")
            exit(1)
        logger.info("续期成功")
        
    except Exception as e:
        logger.error(f"脚本错误: {e}")
        exit(1)
