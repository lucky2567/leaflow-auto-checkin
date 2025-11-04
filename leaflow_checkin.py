#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本

使用方法:
在运行环境中设置以下环境变量/Secrets:
1. 单账号模式(推荐):
    - XSERVER_USERNAME: 您的 Xserver 登录ID
    - XSERVER_PASSWORD: 您的 Xserver 密码
    - XSERVER_SERVER_ID: 您的 Xserver 服务器标识符/客户ID (新增必填项)
2. 多账号模式(次选):
    - XSERVER_ACCOUNTS: ID1:Pass1,ID2:Pass2,... (逗号分隔)

可选通知:
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
        
        # 从环境变量读取服务器标识符
        self.server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        # 验证所有必要凭证
        if not self.username or not self.password or not self.server_id:
            raise ValueError("登录ID、密码或服务器标识符(XSERVER_SERVER_ID)不能为空")
        
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
            
        # 通用配置: 反爬虫检测
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # 自动下载并配置 ChromeDriver
            logger.info("正在自动下载并配置 ChromeDriver...")
            
            driver_path_returned = ChromeDriverManager().install()
            logger.info(f"WebDriverManager 返回的路径: {driver_path_returned}")
            
            # 兼容处理: 尝试构造正确的驱动可执行文件路径
            parent_dir = os.path.dirname(driver_path_returned) 
            base_dir = os.path.dirname(parent_dir) 
            final_driver_path = os.path.join(base_dir, 'chromedriver-linux64', 'chromedriver')
            
            if not os.path.exists(final_driver_path):
                 final_driver_path = driver_path_returned

            logger.info(f"尝试的最终驱动路径: {final_driver_path}")
            
            if not os.path.exists(final_driver_path):
                 raise FileNotFoundError(f"致命错误: 未找到预期的驱动文件。")

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
            
            # 检查是否登录成功
            try:
                manage_link = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(text(), '管理') or contains(text(), 'Manage')] | //button[contains(text(), '管理') or contains(text(), 'Manage')]"
                )
                logger.info(f"登录成功，当前URL: {current_url}。已找到管理链接。")
                
                manage_link.click()
                logger.info("已点击管理链接，等待页面跳转和稳定 (10秒)...")
                time.sleep(10) 
                
                current_url_after_click = self.driver.current_url
                if "authority" in current_url_after_click or "index" in current_url_after_click:
                    logger.info(f"页面跳转稳定，当前URL: {current_url_after_click}。认为登录步骤完成。")
                    return True
                else:
                    raise Exception(f"点击管理链接后跳转失败或页面异常。当前URL: {current_url_after_click}")
                
            except NoSuchElementException:
                if "認証エラー" in self.driver.page_source or "Error" in self.driver.page_source or "username" in self.driver.current_url:
                    raise Exception("登录失败: 登录凭证/服务器标识符错误。")
                
                if "game/index" in self.driver.current_url:
                    logger.info("登录成功，直接进入游戏面板主页，跳过管理链接点击。")
                    return True

                raise Exception(f"登录成功，但未找到预期的服务管理链接。当前URL: {current_url}")
            
        except TimeoutException:
            self._save_screenshot("login_timeout")
            raise Exception(f"登录页面元素加载超时或登录后未跳转。当前URL: {self.driver.current_url}")
        except NoSuchElementException:
            self._save_screenshot("login_element_not_found")
            raise Exception("登录页面元素定位失败，请检查选择器。")
        except Exception as e:
            self._save_screenshot("login_error")
            raise Exception(f"登录失败: {str(e)}")

    def _check_success(self):
        """检查续期是否成功"""
        success_phrases = ["更新完了", "Renewal Complete", "更新されました"]
        return any(phrase in self.driver.page_source for phrase in success_phrases)

    def _check_final_result(self, final_click_count):
        """内部方法: 检查最终页面的续期结果"""
        if self._check_success():
            return "✅ 服务续期成功！"
        else:
            error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]")
            if error_elements:
                error_text = error_elements[0].text
                return f"❌ 续期失败: {error_text[:200] if len(error_text) > 200 else error_text}"
            
            return f"❌ 续期失败: 未找到明确结果，共点击 {final_click_count} 次。请手动检查页面。"

    def renew_service(self):
        """执行多步骤续期操作: 1. 点击入口按钮 -> 2. 循环点击确认/执行按钮 (增强版)"""
        
        logger.info("已位于游戏面板首页，开始查找续期入口按钮...")
        time.sleep(5)
        
        try:
            # 1. 查找并点击主页上的入口按钮
            logger.info("查找主页上引导进入续期流程的入口按钮...")
            
            # 更精确的定位策略
            entry_btn_selectors = [
                ("xpath", "//a[@href='/xmgame/game/freeplan/extend/input']"),  # 精确匹配
                ("xpath", "//a[contains(@href, 'extend')]"),  # 模糊匹配
                ("xpath", "//button[contains(text(), '期限延長')]"),  # 按钮文本
                ("xpath", "//a[contains(text(), '期限延長')]")  # 链接文本
            ]
            
            entry_btn = None
            for by, selector in entry_btn_selectors:
                try:
                    entry_btn = self.wait_for_element_clickable(by, selector, 10)
                    break
                except TimeoutException:
                    continue
                    
            if not entry_btn:
                raise NoSuchElementException("无法定位续期入口按钮")
                
            # 使用JS点击确保可靠性
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("已点击续期入口按钮")
            
            # 2. 等待页面跳转完成
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda d: "extend" in d.current_url.lower() or "renew" in d.current_url.lower()
                )
                logger.info("已跳转到续期页面")
            except TimeoutException:
                logger.warning("页面跳转超时，但继续执行")

            # 3. 增强的重试机制
            max_attempts = 5
            click_count = 0
            
            # 可能的确认按钮文本
            confirm_btn_texts = [
                '延長手続きを行う', '確認画面に進む', '次へ', '次に進む',
                '選択', '確定', '完了', '更新', '更新する', '申し込む', '契約'
            ]
            
            for attempt in range(max_attempts):
                try:
                    # 先尝试处理可能存在的复选框
                    try:
                        checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' or @type='radio']")
                        for cb in checkboxes:
                            if not cb.is_selected():
                                self.driver.execute_script("arguments[0].click();", cb)
                                logger.info("已勾选复选框")
                                time.sleep(1)
                    except Exception as e:
                        logger.warning(f"处理复选框时出错: {e}")

                    # 尝试定位确认按钮
                    confirm_btn = None
                    for text in confirm_btn_texts:
                        try:
                            confirm_btn = self.wait_for_element_clickable(
                                By.XPATH,
                                f"//button[contains(text(), '{text}')] | //a[contains(text(), '{text}')]",
                                10
                            )
                            break
                        except TimeoutException:
                            continue
                            
                    if not confirm_btn:
                        raise NoSuchElementException("无法定位确认按钮")

                    # 确保按钮可见并点击
                    self.driver.execute_script("arguments[0].scrollIntoView();", confirm_btn)
                    self.driver.execute_script("arguments[0].click();", confirm_btn)
                    click_count += 1
                    logger.info(f"✅ 第 {click_count} 次点击成功")
                    
                    # 检查是否已完成
                    if self._check_success():
                        return "✅ 服务续期成功！"
                    
                    time.sleep(5)  # 每次点击后等待
                    
                except StaleElementReferenceException:
                    logger.warning(f"元素状态失效，重试中... (尝试 {attempt + 1}/{max_attempts})")
                    time.sleep(3)
                    continue
                except Exception as e:
                    logger.warning(f"点击时发生错误: {str(e)}，重试中...")
                    time.sleep(3)
                    continue
            
            # 最终结果检查
            return self._check_final_result(click_count)

        except TimeoutException as te:
            self._save_screenshot("renewal_timeout")
            return f"❌ 续期操作超时: {str(te)}"
        except Exception as e:
            self._save_screenshot("renewal_error")
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

class MultiAccountManager:
    """多账号管理器 - 适配 Xserver"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        """从环境变量加载多账号信息"""
        accounts = []
        logger.info("开始加载 XSERVER 账号配置...")
        
        # 方法1: 逗号分隔多账号格式 (XSERVER_ACCOUNTS)
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            try:
                account_pairs = [pair.strip() for pair in accounts_str.split(',')]
                for i, pair in enumerate(account_pairs):
                    if ':' in pair:
                        username, password = pair.split(':', 1)
                        if username.strip() and password.strip():
                            accounts.append({'username': username.strip(), 'password': password.strip()})
                            logger.info(f"成功添加第 {i+1} 个账号 (来自 XSERVER_ACCOUNTS)")
            except Exception as e:
                logger.error(f"解析 XSERVER_ACCOUNTS 配置失败: {e}")
                
        if accounts: return accounts

        # 方法2: 单账号格式 (XSERVER_USERNAME 和 XSERVER_PASSWORD)
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        
        if single_username and single_password:
            accounts.append({'username': single_username, 'password': single_password})
            logger.info("加载了单个账号配置 (来自 XSERVER_USERNAME/PASSWORD)")
            return accounts
        
        # 失败处理
        logger.error("未找到有效的 XSERVER 账号配置")
        logger.error("请设置 XSERVER_USERNAME/XSERVER_PASSWORD/XSERVER_SERVER_ID 或 XSERVER_ACCOUNTS 环境变量。")
        raise ValueError("未找到有效的 XSERVER 账号配置")
    
    def send_notification(self, results):
        """发送汇总通知到Telegram - 续期专用模板"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("Telegram配置未设置，跳过通知")
            return
        
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            total_count = len(results)
            current_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            message = f"🛠️ Xserver 自动续期通知\n"
            message += f"📊 成功: {success_count}/{total_count}\n"
            message += f"📅 执行时间: {current_date}\n\n"
            
            for username, success, result, _ in results:
                masked_username = username[:3] + "***" + username[-4:]
                
                status = "✅" if success else "❌"
                message += f"账号: {masked_username}\n"
                message += f"{status} 续期结果: {result}\n\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Telegram通知发送失败: {response.text}")
                
        except Exception as e:
            logger.error(f"发送Telegram通知时出错: {e}")
    
    def run_all(self):
        """运行所有账号的续期流程"""
        if not self.accounts:
            logger.error("无账号可处理，退出。")
            return False, []
            
        logger.info(f"开始执行 {len(self.accounts)} 个账号的续期任务")
        results = []
        
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"处理第 {i}/{len(self.accounts)} 个账号 ({account['username'][:3] + '***'})")
            
            try:
                os.environ['XSERVER_SERVER_ID'] = os.getenv('XSERVER_SERVER_ID', '')
                renewal = XserverRenewal(account['username'], account['password']) 
                success, result, info_summary = renewal.run() 
                results.append((account['username'], success, result, info_summary))
                
                if i < len(self.accounts):
                    wait_time = 10 
                    logger.info(f"等待{wait_time}秒后处理下一个账号...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                error_msg = f"处理账号时发生致命异常: {str(e)}"
                logger.error(error_msg)
                results.append((account['username'], False, error_msg, "未知"))
                
        self.send_notification(results)
        
        success_count = sum(1 for _, success, _, _ in results if success)
        return success_count == len(self.accounts), results

if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        if not manager.accounts:
            logger.error("没有账号需要处理。")
        else:
            success, results = manager.run_all()
            if not success:
                logger.error("部分或全部账号续期失败，请检查日志和通知。")
                exit(1)
            else:
                logger.info("所有账号续期完成，流程成功。")
                
    except ValueError as ve: 
        logger.error(f"致命配置错误: {ve}")
        exit(1)
    except Exception as e:
        logger.error(f"脚本运行时发生未捕获的全局错误: {e}")
        exit(1)
