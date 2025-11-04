#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本（单账号版）

使用方法：
在运行环境中设置以下环境变量/Secrets：
1. 必选配置：
    - XSERVER_USERNAME：您的 Xserver 登录ID
    - XSERVER_PASSWORD：您的 Xserver 密码
    - XSERVER_SERVER_ID：您的 Xserver 服务器标识符/客户ID
2. 可选通知：
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import requests
from datetime import datetime
import os.path

# 导入 webdriver-manager 相关的库
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =========================================================================
# Xserver 续期类
# =========================================================================

class XserverRenewal:
    def __init__(self, username, password, server_id):
        self.username = username
        self.password = password
        self.server_id = server_id
        
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
            
            driver_path_returned = ChromeDriverManager().install()
            logger.info(f"WebDriverManager 返回的路径: {driver_path_returned}")
            
            # 兼容处理：尝试构造正确的驱动可执行文件路径
            parent_dir = os.path.dirname(driver_path_returned)
            base_dir = os.path.dirname(parent_dir)
            final_driver_path = os.path.join(base_dir, 'chromedriver-linux64', 'chromedriver')
            
            if not os.path.exists(final_driver_path):
                 final_driver_path = driver_path_returned # 否则使用原始返回路径

            logger.info(f"尝试的最终驱动路径: {final_driver_path}")
            
            if not os.path.exists(final_driver_path):
                 raise FileNotFoundError(f"致命错误：未找到预期的驱动文件。")

            # 赋予执行权限
            os.chmod(final_driver_path, 0o755)

            # 使用构造的正确路径初始化 Service
            service = Service(final_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功。")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element_clickable(self, by, value, timeout=20):
        """等待元素可点击"""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def wait_for_element_present(self, by, value, timeout=20):
        """等待元素出现"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def login(self):
        """执行 Xserver 登录流程 (包含中间页处理)"""
        logger.info(f"开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(5)
        
        try:
            # 1. 登录 ID (name="username")
            username_input = self.wait_for_element_clickable(By.NAME, "username", 15)
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info("登录ID输入完成")
            time.sleep(1)

            # 2. 服务器标识符 (name="server_identify")
            logger.info(f"查找服务器标识符输入框，使用值: {self.server_id}...")
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.clear()
            server_id_input.send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            time.sleep(1)
            
            # 3. 密码 (name="server_password")
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.clear()
            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
            
            # 4. 登录按钮 (name="b1")
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
            
            # 等待跳转到任何新页面
            WebDriverWait(self.driver, 20).until(
                lambda driver: "username" not in driver.current_url
            )
            time.sleep(5)

            current_url = self.driver.current_url
            
            # 新的成功判断逻辑：检查页面上是否存在跳转到服务管理的按钮/链接
            try:
                # 尝试找到一个明确指示登录成功的元素 (例如，一个管理按钮/链接)
                manage_link = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(text(), '管理') or contains(text(), 'Manage')] | //button[contains(text(), '管理') or contains(text(), 'Manage')]"
                )
                logger.info(f"登录成功，当前URL: {current_url}。已找到管理链接。")
                
                # 必须点击这个管理链接才能进入续费页面
                manage_link.click()
                
                # 强制等待 10 秒，等待页面跳转和稳定
                logger.info("已点击管理链接，等待页面跳转和稳定 (10秒)...")
                time.sleep(10)
                
                current_url_after_click = self.driver.current_url
                if "authority" in current_url_after_click or "index" in current_url_after_click:
                    logger.info(f"页面跳转稳定，当前URL: {current_url_after_click}。认为登录步骤完成。")
                    return True
                else:
                    raise Exception(f"点击管理链接后跳转失败或页面异常。当前URL: {current_url_after_click}")
                
            except NoSuchElementException:
                # 如果找不到管理链接，则检查是否停留在错误页面
                if "認証エラー" in self.driver.page_source or "Error" in self.driver.page_source or "username" in self.driver.current_url:
                    raise Exception("登录失败：登录凭证/服务器标识符错误。")
                
                # 如果找到了主页但没有管理链接，也认为成功（可能直接在主页）
                if "game/index" in self.driver.current_url:
                    logger.info("登录成功，直接进入游戏面板主页，跳过管理链接点击。")
                    return True

                raise Exception(f"登录成功，但未找到预期的服务管理链接。当前URL: {current_url}")
            
        except TimeoutException:
            raise Exception(f"登录页面元素加载超时或登录后未跳转。当前URL: {self.driver.current_url}")
        except NoSuchElementException:
            raise Exception("登录页面元素定位失败，请检查选择器。")
        except Exception as e:
            raise Exception(f"登录失败: {str(e)}")

    def _check_final_result(self, final_click_count):
        """内部方法：检查最终页面的续期结果"""
        if "更新完了" in self.driver.page_source or "Renewal Complete" in self.driver.page_source or "更新されました" in self.driver.page_source:
            return "✅ 服务续期成功！"
        else:
            error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]")
            if error_elements:
                error_text = error_elements[0].text
                return f"❌ 续期失败：{error_text[:200] if len(error_text) > 200 else error_text}"
            
            return f"❌ 续期失败：未找到明确结果，共点击 {final_click_count} 次。请手动检查页面。"

    def renew_service(self):
        """执行多步骤续期操作：1. 点击入口按钮 -> 2. 循环点击确认/执行按钮"""
        
        logger.info("已位于游戏面板首页，开始查找续期入口按钮...")
        time.sleep(5)
        
        try:
            # 1. 查找并点击主页上的入口按钮 (Step 1: Go to renewal page)
            logger.info("查找主页上引导进入续期流程的入口按钮...")
            
            # 使用最精确的 XPath 定位“期限を延長する”按钮
            entry_btn_xpath = "//a[@href='/xmgame/game/freeplan/extend/input']"

            # 备选 XPath 
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

            # 使用 JS 强制点击入口按钮
            try:
                self.driver.execute_script("arguments[0].click();", entry_btn)
                logger.info("已点击续期入口按钮，使用 JS 强制点击。")
            except Exception:
                # 备用点击
                entry_btn.click()
                logger.warning("入口按钮 JS 强制点击失败，尝试标准点击。")
                
            logger.info("已点击续期入口按钮，等待跳转到确认/套餐页面...")
            
            # 增加超长硬等待，等待页面DOM彻底稳定 (15秒)
            time.sleep(15)
            logger.info("已完成 15 秒硬等待，开始尝试点击确认按钮...")
            
            # 处理复选框/单选框
            try:
                # 查找所有隐藏的或可见的、未被选中的复选框/单选框
                checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' or @type='radio']")
                for cb in checkboxes:
                    # 尝试点击任何未被选中的元素，假定它们是同意条款或套餐选择
                    if not cb.is_selected():
                        self.driver.execute_script("arguments[0].click();", cb)
                        logger.info(f"⚡ 强制点击了一个未选中的复选框/单选框 (Name: {cb.get_attribute('name')})")
                        time.sleep(1) # 每次点击后等待1秒，以防DOM再次刷新
            except Exception as e:
                logger.warning(f"尝试强制点击复选框/单选框时出现次要错误: {e}")

            # 2. 循环点击确认/执行按钮 (Step 2/3/...)
            
            # 检查是否已经续期 (在新页面上检查)
            if "更新済み" in self.driver.page_source or "Already Renewed" in self.driver.page_source:
                return "今日已续期"
            
            # 最终执行按钮/中间确认按钮 - 包含所有可能性
            confirm_execute_btn_xpath = (
                "//button[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '選択') or contains(text(), '確定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する') or contains(text(), '申し込む') or contains(text(), '契約')] | "
                "//a[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '选择') or contains(text(), '确定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する') or contains(text(), '申し込む') or contains(text(), '契約')]"
            )

            logger.info("在跳转后的页面上，循环查找执行或进入下一确认步骤的按钮...")
            
            final_click_count = 0
            max_clicks = 3  # 最多尝试点击三次
            
            for i in range(max_clicks):
                # 核心重试块：处理 Stale Element Reference
                retry_stale = 0
                max_stale_retries = 3
                clicked = False
                current_btn = None
                
                while retry_stale < max_stale_retries:
                    try:
                        # 使用 wait_for_element_present (存在即可)
                        current_btn = self.wait_for_element_present(
                            By.XPATH, 
                            confirm_execute_btn_xpath,
                            20 # 延长等待时间
                        )
                        
                        # 确保元素可用
                        if not current_btn.is_enabled():
                            raise Exception("找到的确认按钮不可用，流程中断。")

                        # 关键：直接使用 JS 强制点击
                        self.driver.execute_script("arguments[0].click();", current_btn)
                        logger.info(f"✅ 使用 JS 强制点击成功。按钮文本: {current_btn.text}")
                        
                        clicked = True
                        break # 跳出 while 循环
                        
                    except StaleElementReferenceException:
                        retry_stale += 1
                        logger.warning(f"检测到 Stale Element 错误，尝试重新定位并点击... (第 {retry_stale} 次)")
                        time.sleep(5)
                        continue # 进入下一次 while 循环
                    except TimeoutException:
                        break # 定位超时，退出 while 循环
                    except Exception as e:
                        raise Exception(f"在定位/点击步骤发生错误: {str(e)}")

                if not clicked:
                    if final_click_count > 0:
                        logger.info(f"第 {i + 1} 次点击失败，但之前已点击 {final_click_count} 次，假定流程结束。")
                        return self._check_final_result(final_click_count)
                    else:
                        raise TimeoutException("续期执行/确认按钮首次点击尝试失败或超时。")

                final_click_count += 1
                logger.info(f"✅ 第 {final_click_count} 次点击完成。")
                time.sleep(8) # 每次点击后增加等待时间
            
            # 3. 检查最终结果
            return self._check_final_result(final_click_count)

        except TimeoutException as te:
            return f"❌ 续期操作超时：{str(te)}。请手动检查服务状态，可能按钮文本已变更。"
        except Exception as e:
            return f"❌ 续期过程中发生错误: {str(e)}"

    def run(self):
        """执行单个账号的完整续期流程"""
        result = "未执行"
        
        try:
            logger.info(f"开始处理账号: {self.username[:3] + '***'}")
            
            # 1. 登录
            if self.login():
                # 2. 续期
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                
                success = "✅" in result or "已续期" in result
                return success, result
            else:
                return False, "登录未成功"
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        finally:
            if self.driver:
                self.driver.quit()


# 发送Telegram通知
def send_telegram_notification(result, username):
    """发送续期结果到Telegram"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    if not bot_token or not chat_id:
        logger.info("Telegram配置未设置，跳过通知")
        return
    
    try:
        current_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        masked_username = username[:3] + "***" + username[-4:] if len(username) > 7 else username
        
        message = f"🛠️ Xserver 自动续期通知\n"
        message += f"📅 执行时间：{current_date}\n"
        message += f"账号：{masked_username}\n"
        message += f"结果：{result}\n"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Telegram通知发送失败: {response.text}")
            
    except Exception as e:
        logger.error(f"发送Telegram通知时出错: {e}")


# 主入口
if __name__ == "__main__":
    try:
        # 读取环境变量
        username = os.getenv('XSERVER_USERNAME', '').strip()
        password = os.getenv('XSERVER_PASSWORD', '').strip()
        server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        # 验证环境变量
        if not all([username, password, server_id]):
            raise ValueError("请确保设置了所有必要的环境变量：XSERVER_USERNAME, XSERVER_PASSWORD, XSERVER_SERVER_ID")
        
        # 执行续期
        renewal = XserverRenewal(username, password, server_id)
        success, result = renewal.run()
        
        # 发送通知
        send_telegram_notification(result, username)
        
        if not success:
            logger.error("续期失败，请检查日志")
            exit(1)
        else:
            logger.info("续期流程完成，一切正常")
            
    except ValueError as ve:
        logger.error(f"配置错误: {ve}")
        exit(1)
    except Exception as e:
        logger.error(f"脚本运行错误: {e}")
        exit(1)
