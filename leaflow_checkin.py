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
        """执行多步骤续期操作: 1. 点击入口按钮 -> 2. 循环点击确认/执行按钮"""
        
        logger.info("已位于游戏面板首页，开始查找续期入口按钮...")
        time.sleep(5) 
        
        try:
            # 1. 查找并点击主页上的入口按钮 (Step 1: Go to renewal page)
            logger.info("查找主页上引导进入续期流程的入口按钮...")
            
            entry_btn_xpath = "//a[@href='/xmgame/game/freeplan/extend/input']"
            backup_entry_btn_xpath = (
                "//button[contains(text(), '期限延長') or contains(text(), '期限を延長する') or contains(text(), '期限を延長していただく必要がございます') or contains(text(), 'アップグレード・期限延長')] | "
                "//a[contains(text(), '期限延長') or contains(text(), '期限を延長する') or contains(text(), '期限を延長していただく必要がございます') or contains(text(), 'アップグレード・期限延長')]"
            )
            
            try:
                entry_btn = self.wait_for_element_clickable(
                    By.XPATH, 
                    entry_btn_xpath,
                    15 # 首次尝试使用精确的 XPath
                )
            except TimeoutException:
                logger.warning("精确的续期入口按钮定位失败，尝试使用模糊 XPath...")
                entry_btn = self.wait_for_element_clickable(
                    By.XPATH, 
                    backup_entry_btn_xpath,
                    15
                )

            try:
                self.driver.execute_script("arguments[0].click();", entry_btn)
                logger.info("已点击续期入口按钮，使用 JS 强制点击。")
            except Exception:
                entry_btn.click() 
                logger.warning("入口按钮 JS 强制点击失败，尝试标准点击。")
                
            logger.info("已点击续期入口按钮，等待跳转到确认/套餐页面...")
            
            # [修复 1] 移除 time.sleep(15) 和单独的复选框逻辑。
            # 让主循环来处理加载和点击。

            # 2. 循环点击确认/执行按钮 (Step 2/3/...)
            
            # [修复 2] 增加一个短暂的 sleep 确保页面开始加载
            time.sleep(2) 
            try:
                if "更新済み" in self.driver.page_source or "Already Renewed" in self.driver.page_source:
                    return "今日已续期"
            except:
                pass # 忽略页面源检查期间可能发生的错误

            # [修复 3] 将复选框/单选框加入到主点击 XPath 中
            confirm_execute_btn_xpath = (
                "//input[@type='checkbox' or @type='radio'][not(:checked)] | "
                "//button[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '選択') or contains(text(), '確定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する') or contains(text(), '申し込む') or contains(text(), '契約')] | "
                "//a[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '选择') or contains(text(), '确定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する') or contains(text(), '申し込む') or contains(text(), '契約')]"
            )

            logger.info("在跳转后的页面上，循环查找执行或进入下一确认步骤的按钮/选项...")
            
            final_click_count = 0
            max_clicks = 4  # [修复 4] 增加总点击次数 (原为3)，以防需要先点复选框
            
            for i in range(max_clicks):
                
                # **核心重试块: 处理 Stale Element Reference**
                retry_stale = 0
                max_stale_retries = 5 # [修复 5] 增加 Stale 重试次数 (原为3)
                clicked = False
                
                while retry_stale < max_stale_retries:
                    try:
                        # [修复 6] 切换到 wait_for_element_clickable
                        # 这会等待元素出现、可见 *并* 可用
                        current_btn = self.wait_for_element_clickable(
                            By.XPATH, 
                            confirm_execute_btn_xpath,
                            20 # 延长等待时间
                        )
                        
                        # 获取元素信息用于日志
                        btn_info = current_btn.get_attribute('value') or current_btn.text or current_btn.get_attribute('name')
                        btn_info = btn_info.strip().replace('\n', ' ')
                        
                        # **关键: 直接使用 JS 强制点击**
                        self.driver.execute_script("arguments[0].click();", current_btn)
                        logger.info(f"✅ 使用 JS 强制点击成功。元素: {btn_info[:50]}") # 截断过长的文本
                        
                        # 成功点击
                        clicked = True
                        break # 跳出 while 循环
                        
                    except StaleElementReferenceException:
                        retry_stale += 1
                        logger.warning(f"检测到 Stale Element 错误，尝试重新定位并点击... (第 {retry_stale} 次)")
                        # [修复 7] 缩短 Stale 重试等待
                        time.sleep(3) 
                        continue # 进入下一次 while 循环
                    except TimeoutException:
                        # 如果20秒内找不到可点击的按钮
                        logger.warning(f"在第 {i+1} 轮点击中，等待确认按钮/选项超时。")
                        break # 跳出 while 循环
                    except Exception as e:
                        # 捕获其他非 Stale 错误，直接向上抛出
                        raise Exception(f"在定位/点击步骤发生错误: {str(e)}")


                if not clicked:
                    # 如果 while 循环结束但没有点击成功
                    if final_click_count > 0:
                        # 如果之前点击过（例如点了复选框），但现在找不到按钮了，假定流程结束
                        logger.info(f"第 {i + 1} 次点击超时，但之前已点击 {final_click_count} 次，假定流程结束。")
                        return self._check_final_result(final_click_count)
                    else:
                        # 第一次点击就失败(超时)，抛出异常
                        raise TimeoutException("续期执行/确认按钮首次点击尝试失败或超时。")

                final_click_count += 1
                logger.info(f"✅ 第 {final_click_count} 次点击完成。")
                
                # [修复 8] 缩短每次点击后的等待
                time.sleep(5) 
            
            # 3. 检查最终结果
            return self._check_final_result(final_click_count)

        except TimeoutException as te:
            # 如果在任何一个步骤中超时
            return f"❌ 续期操作超时: {str(te)}。请手动检查服务状态，可能按钮文本已变更。"
        except Exception as e:
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

