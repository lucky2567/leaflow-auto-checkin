#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本

使用方法：
在运行环境中设置以下环境变量/Secrets：
1. 单账号模式（推荐）：
   - XSERVER_USERNAME：您的 Xserver 登录ID
   - XSERVER_PASSWORD：您的 Xserver 密码
   - XSERVER_SERVER_ID：您的 Xserver 服务器标识符/客户ID (新增必填项)
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =========================================================================
# Xserver 续期类 (已更新 __init__ 和 login 方法)
# =========================================================================

class XserverRenewal:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
        # 💥 关键更新 1: 读取服务器标识符
        self.server_id = os.getenv('XSERVER_SERVER_ID', self.username).strip()
        
        # 验证所有必要凭证
        if not self.username or not self.password or not self.server_id:
            # 修改错误消息以包含新的必填项
            raise ValueError("登录ID、密码或服务器标识符（XSERVER_SERVER_ID）不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项 (保持不变)"""
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
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except WebDriverException as e:
            logger.error(f"启动Chrome驱动失败，请检查驱动路径或使用WebDriverManager: {e}")
            raise
    
    def wait_for_element_clickable(self, by, value, timeout=20):
        """等待元素可点击 (保持不变)"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=20):
        """等待元素出现 (保持不变)"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def login(self):
        """执行 Xserver 登录流程 (已更新所有元素定位)"""
        logger.info(f"开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(5)
        
        try:
            # 1. 登录 ID (name="username")
            logger.info("查找登录ID输入框 (name='username')...")
            # 💥 关键修改 2: 使用正确的 name="username"
            username_input = self.wait_for_element_clickable(By.NAME, "username", 15)
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info("登录ID输入完成")
            time.sleep(1)

            # 2. 服务器标识符 (name="server_identify")
            logger.info(f"查找服务器标识符输入框 (name='server_identify')，使用值: {self.server_id}...")
            # 💥 关键修改 3: 填充新增的 server_identify 字段
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.clear()
            server_id_input.send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            time.sleep(1)
            
            # 3. 密码 (name="server_password")
            logger.info("查找密码输入框 (name='server_password')...")
            # 💥 关键修改 4: 使用正确的 name="server_password"
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
            
            # 4. 登录按钮 (name="b1")
            logger.info("查找登录按钮 (name='b1')...")
            # 💥 关键修改 5: 使用最稳定的 name="b1" 定位登录按钮
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
            
            # 等待登录完成，跳转到仪表板页面 (URL包含 'manage' 或 'top')
            WebDriverWait(self.driver, 20).until(
                lambda driver: "manage" in driver.current_url or "top" in driver.current_url
            )
            
            current_url = self.driver.current_url
            if "manage" in current_url or "top" in current_url:
                logger.info(f"登录成功，当前URL: {current_url}")
                return True
            else:
                # 增加了更精准的错误提示
                if "認証エラー" in self.driver.page_source or "Error" in self.driver.page_source or "username" in self.driver.current_url:
                     raise Exception("登录失败：登录凭证/服务器标识符错误。")
                raise Exception("登录后未跳转到服务管理页。")
            
        except TimeoutException:
            raise Exception(f"登录页面元素加载超时或登录后未跳转。当前URL: {self.driver.current_url}")
        except NoSuchElementException:
            raise Exception("登录页面元素定位失败，请检查选择器。")
        except Exception as e:
            raise Exception(f"登录失败: {str(e)}")


    def renew_service(self):
        # ... (renew_service 方法保持不变)
        # ⚠️ 注意: 续期操作中的元素定位 (XPATHs) 仍是基于通用猜测，如果登录成功，此方法可能是下一个失败点。
        RENEWAL_PAGE_URL = "https://secure.xserver.ne.jp/xapanel/manage/xmgame/game"
        self.driver.get(RENEWAL_PAGE_URL)
        time.sleep(5) 
        
        # ... (续期操作逻辑保持不变)
        
        try:
            # 2. 查找并点击“延长/更新”按钮 (保持不变)
            logger.info("查找服务列表中的 '升级/延长' 或 '更新' 按钮...")
            renewal_btn = self.wait_for_element_clickable(
                By.XPATH, 
                "//button[contains(text(), '延長') or contains(text(), '更新') or contains(text(), 'Upgrade') or contains(text(), 'Renew')] | //a[contains(text(), '延長') or contains(text(), '更新') or contains(text(), 'Upgrade') or contains(text(), 'Renew')]",
                20
            )
            renewal_btn.click()
            logger.info("已点击续期/延长操作按钮，跳转到确认页...")
            time.sleep(5) 
            
            # 3. 确认续期（保持不变）
            if "更新済み" in self.driver.page_source or "Already Renewed" in self.driver.page_source:
                return "今日已续期"
            
            logger.info("查找最终确认续期按钮...")
            final_confirm_btn = self.wait_for_element_clickable(
                By.XPATH, 
                "//button[contains(text(), '確定') or contains(text(), 'Confirm') or contains(text(), '完了')]",
                20
            )

            if not final_confirm_btn.is_enabled():
                raise Exception("续期确认按钮不可用，可能需要手动选择支付方式或其他操作。")

            final_confirm_btn.click()
            logger.info("已点击最终确认续期按钮。")
            time.sleep(10) 
            
            # 4. 检查最终结果（保持不变）
            if "更新完了" in self.driver.page_source or "Renewal Complete" in self.driver.page_source or "更新されました" in self.driver.page_source:
                return "✅ 服务续期成功！"
            else:
                error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]")
                if error_elements:
                    return f"❌ 续期失败：{error_elements[0].text[:100]}..."
                
                if "manage" in self.driver.current_url:
                    return "⚠️ 续期操作完成，但未找到明确成功消息，请手动检查！"
                
                return "❌ 续期失败：未找到明确结果，可能是页面结构改变或需要额外操作。"

        except TimeoutException:
            return "❌ 续期操作超时，请手动检查服务状态。"
        except Exception as e:
            return f"❌ 续期过程中发生错误: {str(e)}"
    
    def run(self):
        # ... (run 方法保持不变)
        result = "未执行"
        
        try:
            logger.info(f"开始处理账号: {self.username}")
            
            # 1. 登录
            if self.login():
                # 2. 续期
                result = self.renew_service()
                
                info_summary = result 
                
                logger.info(f"续期结果: {result}")
                
                success = "✅" in result or "已续期" in result
                return success, result, info_summary
            else:
                pass
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知错误"
            
        finally:
            if self.driver:
                self.driver.quit()

# =========================================================================
# 多账号管理器 (保持不变，但会隐式读取 XSERVER_SERVER_ID)
# =========================================================================

class MultiAccountManager:
    # ... (所有方法和逻辑保持不变)
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
        
    def load_accounts(self):
        # ... (加载逻辑保持不变)
