#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本 (优化版)

主要改进：
1. 增强续期按钮定位逻辑，支持更多可能的文本和属性组合
2. 优化等待策略，减少硬编码的 sleep，改用动态等待
3. 增加页面状态检查和错误恢复机制
4. 改进 Stale Element 处理逻辑
5. 添加详细的调试日志和截图功能
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
        """设置Chrome驱动选项并自动管理ChromeDriver"""
        chrome_options = Options()
        
        # GitHub Actions环境配置
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
        # 反爬虫检测配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            logger.info("正在自动下载并配置 ChromeDriver...")
            driver_path_returned = ChromeDriverManager().install()
            
            # 兼容处理驱动路径
            parent_dir = os.path.dirname(driver_path_returned)
            final_driver_path = os.path.join(parent_dir, 'chromedriver')
            
            if not os.path.exists(final_driver_path):
                final_driver_path = driver_path_returned

            os.chmod(final_driver_path, 0o755)
            service = Service(final_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功。")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def save_debug_screenshot(self, prefix="debug"):
        """保存调试截图"""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            with open(filename, "wb") as f:
                f.write(screenshot)
            logger.info(f"已保存调试截图: {filename}")
            return filename
        except Exception as e:
            logger.warning(f"保存截图失败: {e}")
            return None
    
    def wait_for_element_clickable(self, by, value, timeout=30):
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=30):
        """等待元素出现"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def safe_click(self, element, description=""):
        """安全的元素点击方法，处理各种异常情况"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self.driver.execute_script("arguments[0].click();", element)
            logger.info(f"成功点击元素: {description}")
            return True
        except ElementClickInterceptedException:
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                self.driver.execute_script("arguments[0].click();", element)
                logger.info(f"通过滚动修复后点击成功: {description}")
                return True
            except Exception as e:
                logger.warning(f"点击元素失败: {description} - {str(e)}")
                self.save_debug_screenshot("click_failed")
                return False
        except Exception as e:
            logger.warning(f"点击元素失败: {description} - {str(e)}")
            self.save_debug_screenshot("click_failed")
            return False
    
    def login(self):
        """增强版登录流程"""
        logger.info(f"开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        
        try:
            # 1. 登录ID
            username_input = self.wait_for_element_clickable(By.NAME, "username", 20)
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info("登录ID输入完成")
            
            # 2. 服务器标识符
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.clear()
            server_id_input.send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            
            # 3. 密码
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            
            # 4. 登录按钮
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            if not self.safe_click(login_btn, "登录按钮"):
                raise Exception("无法点击登录按钮")
            
            # 等待登录完成
            WebDriverWait(self.driver, 30).until(
                lambda driver: "username" not in driver.current_url
            )
            
            # 检查登录成功
            try:
                manage_link = self.wait_for_element_clickable(
                    By.XPATH, 
                    "//a[contains(text(), '管理') or contains(text(), 'Manage')] | //button[contains(text(), '管理') or contains(text(), 'Manage')]",
                    20
                )
                if not self.safe_click(manage_link, "管理链接"):
                    raise Exception("无法点击管理链接")
                
                # 等待管理页面加载
                WebDriverWait(self.driver, 30).until(
                    lambda driver: "authority" in driver.current_url or "index" in driver.current_url
                )
                logger.info("登录和管理页面跳转成功")
                return True
                
            except Exception as e:
                if "認証エラー" in self.driver.page_source:
                    raise Exception("登录失败：凭证错误")
                raise Exception(f"登录后处理失败: {str(e)}")
                
        except Exception as e:
            self.save_debug_screenshot("login_failed")
            raise Exception(f"登录过程出错: {str(e)}")

    def renew_service(self):
        """增强版续期流程"""
        logger.info("开始续期流程")
        self.save_debug_screenshot("before_renewal")
        
        try:
            # 1. 查找续期入口按钮
            entry_btn_xpaths = [
                "//a[contains(@href, 'extend') or contains(@href, 'renew')]",
                "//button[contains(text(), '延長') or contains(text(), '更新')]",
                "//a[contains(text(), '延長') or contains(text(), '更新')]",
                "//*[contains(@class, 'extend') or contains(@class, 'renew')]"
            ]
            
            entry_btn = None
            for xpath in entry_btn_xpaths:
                try:
                    entry_btn = self.wait_for_element_clickable(By.XPATH, xpath, 15)
                    break
                except:
                    continue
            
            if not entry_btn:
                raise Exception("找不到续期入口按钮")
            
            if not self.safe_click(entry_btn, "续期入口按钮"):
                raise Exception("无法点击续期入口按钮")
            
            # 2. 处理可能的多步骤确认流程
            confirm_btn_xpaths = [
                "//button[contains(text(), '確認') or contains(text(), 'Confirm')]",
                "//a[contains(text(), '確認') or contains(text(), 'Confirm')]",
                "//button[contains(text(), '次へ') or contains(text(), 'Next')]",
                "//input[@type='submit' and contains(@value, '確認')]"
            ]
            
            max_steps = 3
            for step in range(max_steps):
                self.save_debug_screenshot(f"renewal_step_{step}")
                
                # 检查是否已完成
                if "完了" in self.driver.page_source or "Complete" in self.driver.page_source:
                    return "✅ 续期成功"
                
                # 尝试点击各种可能的确认按钮
                clicked = False
                for xpath in confirm_btn_xpaths:
                    try:
                        btn = self.wait_for_element_present(By.XPATH, xpath, 10)
                        if self.safe_click(btn, f"步骤{step}确认按钮"):
                            clicked = True
                            time.sleep(3)  # 等待页面响应
                            break
                    except:
                        continue
                
                if not clicked:
                    if step > 0:  # 如果已经成功点击过至少一次
                        return self._check_final_result()
                    else:
                        raise Exception("无法找到有效的确认按钮")
            
            return self._check_final_result()
            
        except Exception as e:
            self.save_debug_screenshot("renewal_failed")
            return f"❌ 续期失败: {str(e)}"
    
    def _check_final_result(self):
        """检查最终续期结果"""
        if "完了" in self.driver.page_source or "Complete" in self.driver.page_source:
            return "✅ 续期成功"
        elif "エラー" in self.driver.page_source or "Error" in self.driver.page_source:
            error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error')]")
            if error_elements:
                return f"❌ 续期失败: {error_elements[0].text[:100]}"
        return "❌ 续期失败: 未知原因"

    def run(self):
        """执行完整流程"""
        result = "未执行"
        try:
            logger.info(f"处理账号: {self.username[:3]}***")
            
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                success = "✅" in result or "成功" in result
                return success, result, result
                
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "错误"
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
        accounts = []
        logger.info("加载账号配置...")
        
        # 多账号模式
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            try:
                for pair in accounts_str.split(','):
                    if ':' in pair:
                        username, password = pair.split(':', 1)
                        accounts.append({'username': username.strip(), 'password': password.strip()})
            except Exception as e:
                logger.error(f"解析多账号配置失败: {e}")
        
        # 单账号模式
        if not accounts:
            username = os.getenv('XSERVER_USERNAME', '').strip()
            password = os.getenv('XSERVER_PASSWORD', '').strip()
            if username and password:
                accounts.append({'username': username, 'password': password})
        
        if not accounts:
            raise ValueError("未找到有效的账号配置")
        return accounts
    
    def send_notification(self, results):
        """发送通知"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
            
        message = "🔄 Xserver 续期结果:\n"
        for username, success, result, _ in results:
            status = "✅" if success else "❌"
            message += f"{status} {username[:3]}***: {result}\n"
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                data={"chat_id": self.telegram_chat_id, "text": message},
                timeout=10
            )
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
    
    def run_all(self):
        """运行所有账号"""
        results = []
        for account in self.accounts:
            try:
                renewal = XserverRenewal(account['username'], account['password'])
                success, result, info = renewal.run()
                results.append((account['username'], success, result, info))
            except Exception as e:
                results.append((account['username'], False, str(e), "异常"))
                logger.error(f"处理账号 {account['username'][:3]}*** 失败: {e}")
        
        self.send_notification(results)
        return all(r[1] for r in results), results

if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        success, results = manager.run_all()
        if not success:
            logger.error("部分账号处理失败")
            exit(1)
        logger.info("所有账号处理完成")
    except Exception as e:
        logger.error(f"脚本运行失败: {e}")
        exit(1)
