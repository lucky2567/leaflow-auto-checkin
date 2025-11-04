#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本

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

# =========================================================================
# Xserver 续期类
# =========================================================================

class XserverRenewal:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
        # 从环境变量读取服务器标识符
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
            
            driver_path_returned = ChromeDriverManager().install()
            logger.info(f"WebDriverManager 返回的路径: {driver_path_returned}")
            
            # 兼容处理：尝试构造正确的驱动可执行文件路径
            parent_dir = os.path.dirname(driver_path_returned) 
            base_dir = os.path.dirname(parent_dir) 
            final_driver_path = os.path.join(base_dir, 'chromedriver-linux64', 'chromedriver')
            
            if not os.path.exists(final_driver_path):
                 final_driver_path = driver_path_returned

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
            self._save_screenshot("login_timeout")
            raise Exception(f"登录页面元素加载超时或登录后未跳转。当前URL: {self.driver.current_url}")
        except NoSuchElementException:
            self._save_screenshot("login_element_not_found")
            raise Exception("登录页面元素定位失败，请检查选择器。")
        except Exception as e:
            self._save_screenshot("login_error")
            raise Exception(f"登录失败: {str(e)}")


    def _check_final_result(self, final_click_count):
        """内部方法：检查最终页面的续期结果（根据页面截图优化）"""
        current_url = self.driver.current_url
        
        # 1. 检查是否到达"确认页面"（根据需求，到达此页面即视为成功）
        if "confirm" in current_url.lower() or "check" in current_url.lower() or "extend/input" in current_url:
            logger.info(f"已到达续期确认页面！当前URL: {current_url}")
            return "✅ 服务续期成功！已到达确认页面"
        
        # 2. 检查是否有成功关键词
        if "更新完了" in self.driver.page_source or "Renewal Complete" in self.driver.page_source or "更新されました" in self.driver.page_source:
            return "✅ 服务续期成功！"
        
        # 3. 检查是否有返回/完成按钮（表示流程已结束）
        try:
            if self.driver.find_elements(By.XPATH, "//button[contains(text(), '返回') or contains(text(), '戻る') or contains(text(), '完了')]"):
                logger.info("检测到返回/完成按钮，流程已结束")
                return "✅ 服务续期成功！流程已完成"
        except Exception as e:
            logger.warning(f"检查返回按钮时出错: {e}")
        
        # 4. 检查错误信息
        error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]")
        if error_elements:
            error_text = "\n".join([el.text for el in error_elements[:3]])
            return f"❌ 续期失败：{error_text[:300]}"
        
        return f"❌ 续期失败：未找到明确结果（点击{final_click_count}次）。当前URL: {current_url}"

    def renew_service(self):
        """执行多步骤续期操作（根据页面截图优化）"""
        logger.info("已位于游戏面板首页，开始查找续期入口按钮...")
        time.sleep(5) 
        
        try:
            # 1. 查找并点击主页上的续期入口按钮（根据截图中的"アップグレード・期限延長"按钮）
            logger.info("查找主页上引导进入续期流程的入口按钮...")
            
            # **根据截图优化：匹配"アップグレード・期限延長"按钮**
            entry_btn_xpath = "//a[contains(text(), 'アップグレード・期限延長') or @href='/xmgame/game/freeplan/extend/input']"
            backup_entry_btn_xpath = "//button[contains(text(), '期限延長') or contains(text(), '期限を延長する')]"
            
            try:
                entry_btn = self.wait_for_element_clickable(By.XPATH, entry_btn_xpath, 15)
            except TimeoutException:
                logger.warning("精确的续期入口按钮定位失败，尝试使用备用XPath...")
                entry_btn = self.wait_for_element_clickable(By.XPATH, backup_entry_btn_xpath, 15)

            # 使用 JS 强制点击入口按钮
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("已点击续期入口按钮，使用 JS 强制点击。")
            
            # 等待页面跳转（根据截图中的续期页面URL特征）
            WebDriverWait(self.driver, 20).until(
                lambda d: "freeplan/extend" in d.current_url or "extend/input" in d.current_url
            )
            logger.info(f"已跳转到续期页面，当前URL: {self.driver.current_url}")
            self._save_screenshot("renewal_page_loaded")
            
            # 2. 处理续期页面（根据截图中的"+72時間延長"按钮）
            logger.info("开始处理续期页面，查找延长期限按钮...")
            
            # **根据截图优化：匹配"+72時間延長"按钮**
            extend_btn_xpath = "//button[contains(text(), '+72時間延長') or contains(text(), '延長期間')]"
            confirm_btn_xpath = "//button[contains(text(), '確認画面に進む') or contains(text(), '次へ')]"
            
            try:
                # 先尝试直接点击延长期限按钮
                extend_btn = self.wait_for_element_clickable(By.XPATH, extend_btn_xpath, 15)
                self.driver.execute_script("arguments[0].scrollIntoView();", extend_btn)
                self.driver.execute_script("arguments[0].click();", extend_btn)
                logger.info("已点击+72時間延長按钮")
                time.sleep(3)
            except TimeoutException:
                logger.warning("未找到+72時間延長按钮，直接查找确认按钮...")
            
            # 3. 循环点击确认按钮，直到到达确认页面
            max_clicks = 3
            final_click_count = 0
            confirm_buttons_clicked = False
            
            for attempt in range(max_clicks):
                try:
                    # **根据截图优化：匹配"確認画面に進む"按钮**
                    confirm_btn = self.wait_for_element_clickable(By.XPATH, confirm_btn_xpath, 15)
                    self.driver.execute_script("arguments[0].scrollIntoView();", confirm_btn)
                    self.driver.execute_script("arguments[0].click();", confirm_btn)
                    final_click_count += 1
                    logger.info(f"✅ 第 {final_click_count} 次点击确认按钮：{confirm_btn.text}")
                    confirm_buttons_clicked = True
                    
                    # 点击后检查是否到达确认页面（核心优化点）
                    time.sleep(5)
                    result = self._check_final_result(final_click_count)
                    if "✅" in result:
                        return result
                    
                except StaleElementReferenceException:
                    logger.warning(f"检测到Stale Element错误，重试中... (第 {attempt + 1} 次)")
                    time.sleep(5)
                    continue
                except TimeoutException:
                    logger.warning(f"第 {attempt + 1} 次确认按钮定位超时")
                    break
                except Exception as e:
                    logger.error(f"点击确认按钮时出错: {e}")
                    self._save_screenshot(f"confirm_error_attempt_{attempt}")
                    break
            
            if not confirm_buttons_clicked:
                raise TimeoutException("未找到或未点击任何确认按钮")
            
            # 最终检查结果
            self._save_screenshot("renewal_final_page")
            return self._check_final_result(final_click_count)

        except TimeoutException as te:
            self._save_screenshot("renewal_timeout")
            return f"❌ 续期操作超时：{str(te)}。当前URL: {self.driver.current_url}"
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
                
                logger.info(f"续期结果: {result}")
                
                success = "✅" in result or "已续期" in result
                return success, result, ""
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, ""
            
        finally:
            if self.driver:
                self.driver.quit()

# =========================================================================
# 多账号管理器
# =========================================================================

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
                raise
                
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
            message += f"📅 执行时间：{current_date}\n\n"
            
            for username, success, result, _ in results:
                masked_username = username[:3] + "***" + username[-4:] if len(username) > 7 else username
                status = "✅" if success else "❌"
                message += f"账号：{masked_username}\n"
                message += f"{status} 续期结果：{result}\n\n"
            
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
                self._save_screenshot(f"account_fatal_error_{i}")
                
        self.send_notification(results)
        
        success_count = sum(1 for _, success, _, _ in results if success)
        return success_count == len(results), results


# =========================================================================
# 主入口点
# =========================================================================

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
