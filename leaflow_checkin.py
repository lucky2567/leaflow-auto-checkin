#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本

功能：
1. 登录 Xserver 游戏面板。
2. 自动完成免费套餐的续期流程（アップグレード・期限延長 -> 期限を延長する -> 確認画面に進む -> 更新実行）。
3. 包含强大的稳定性措施，如 JS 强制点击、硬等待、元素 Stale 重试，以及 ChromeDriver 路径兼容性修复。
4. 支持通过 Telegram 发送通知（可选）。

使用方法：
在运行环境中设置以下环境变量/Secrets：
- XSERVER_USERNAME：您的 Xserver 登录ID
- XSERVER_PASSWORD：您的 Xserver 密码
- XSERVER_SERVER_ID：您的 Xserver 服务器标识符/客户ID (必填项)

可选通知：
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import time
import logging
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import requests
from datetime import datetime
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
            raise ValueError("登录ID、密码或服务器标识符（XSERVER_SERVER_ID）未设置")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项并自动管理ChromeDriver，包含路径兼容性修复"""
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
            logger.info("正在自动下载并配置 ChromeDriver...")
            
            # 1. 使用 ChromeDriverManager 下载驱动
            # 返回值 driver_path_returned 是驱动文件在缓存中的路径，但可能指向一个目录或错误的文件
            driver_path_returned = ChromeDriverManager().install()
            
            # 2. 路径修正逻辑：解决 [Errno 8] Exec format error 和路径解析错误
            final_driver_path = None
            
            if os.path.isfile(driver_path_returned) and 'chromedriver' in driver_path_returned:
                # 理想情况：返回的就是可执行文件路径
                final_driver_path = driver_path_returned
            else:
                # 非理想情况：尝试在子文件夹中找到实际的 'chromedriver' 可执行文件
                base_dir = os.path.dirname(driver_path_returned) 
                
                # 遍历所有子目录，查找名为 'chromedriver' 的文件
                for root, dirs, files in os.walk(base_dir):
                    if 'chromedriver' in files:
                        final_driver_path = os.path.join(root, 'chromedriver')
                        break
                
                # 如果没找到，退回到原始路径
                if not final_driver_path:
                    final_driver_path = driver_path_returned 

            logger.info(f"最终驱动路径: {final_driver_path}")
            
            if not os.path.exists(final_driver_path):
                 raise FileNotFoundError(f"致命错误：未找到预期的驱动文件在 {final_driver_path}")

            # 3. 赋予执行权限 (解决权限或格式错误)
            os.chmod(final_driver_path, 0o755) 
            logger.info("已赋予驱动文件执行权限 (0755)。")

            # 4. 使用构造的正确路径初始化 Service
            service = Service(final_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功。")
            
        except Exception as e:
            logger.error(f"驱动初始化失败: {e}")
            raise
    
    # 以下为辅助函数（未修改）
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
        """执行 Xserver 登录流程"""
        logger.info(f"开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(5)
        
        try:
            # 1. 登录 ID (name="username")
            username_input = self.wait_for_element_clickable(By.NAME, "username", 15)
            username_input.send_keys(self.username)
            
            # 2. サーバー識別子 (name="server_identify")
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.send_keys(self.server_id)
            
            # 3. 密码 (name="server_password")
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.send_keys(self.password)
            
            # 4. 登录按钮 (name="b1")
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            login_btn.click()
            logger.info("已点击登录按钮")
            
            # 成功后的跳转等待
            WebDriverWait(self.driver, 20).until(
                lambda driver: "username" not in driver.current_url
            )
            time.sleep(5) 

            # 登录成功后的页面检查
            if "game/index" in self.driver.current_url or "authority" in self.driver.current_url:
                logger.info("登录成功。已到达游戏面板或管理页面。")
                
                # 登录后的管理页面/首页链接的点击处理
                try:
                    manage_link = self.driver.find_element(
                        By.XPATH, 
                        "//a[contains(text(), 'ゲームパネルへ') or contains(text(), '管理') or contains(text(), 'Manage') or contains(text(), '服务管理')]"
                    )
                    manage_link.click()
                    time.sleep(10)
                    logger.info("已点击管理链接。")
                except NoSuchElementException:
                    logger.info("未找到管理链接。假设已在正确的页面上。")
                
                return True
            else:
                if "認証エラー" in self.driver.page_source or "Error" in self.driver.page_source:
                    raise Exception("登录失败：身份验证信息或服务器标识符可能错误。")
                raise Exception(f"登录成功后发生意外页面跳转。当前URL: {self.driver.current_url}")
            
        except TimeoutException:
            raise Exception(f"登录页面元素加载超时。")
        except Exception as e:
            raise Exception(f"登录过程中发生错误: {str(e)}")


    def _check_final_result(self, final_click_count):
        """检查最终页面的续期结果"""
        # '更新完了', 'Renewal Complete', '更新されました' 的任意一个出现则视为成功
        if "更新完了" in self.driver.page_source or "Renewal Complete" in self.driver.page_source or "更新されました" in self.driver.page_source:
            return "✅ 服务更新成功！"
        else:
            # 搜索错误消息
            error_elements = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert-danger')]")
            if error_elements:
                error_text = error_elements[0].text
                return f"❌ 更新失败：{error_text[:200] if len(error_text) > 200 else error_text}"
            
            return f"❌ 更新失败：未找到明确结果。总共点击了 {final_click_count} 次。请手动检查页面状态。"

    def renew_service(self):
        """执行多步骤续期操作"""
        
        logger.info("开始搜索续期入口按钮...")
        time.sleep(5) 
        
        try:
            # 1. 查找并点击主页上的入口按钮 (Step 1)
            # 按钮文本: 'アップグレード・期限延長'
            entry_btn_xpath = (
                "//a[@href='/xmgame/game/freeplan/extend/input'] | "
                "//button[contains(text(), 'アップグレード・期限延長')] | "
                "//a[contains(text(), 'アップグレード・期限延長')]"
            )
            
            entry_btn = self.wait_for_element_clickable(By.XPATH, entry_btn_xpath, 15)

            # JS 强制点击入口按钮
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("✅ 已点击续期入口按钮。")
                
            logger.info("等待跳转到套餐比较/确认页面...")
            
            # **DOM安定のための超長硬待ち (15秒)**
            time.sleep(15) 
            logger.info("15秒硬等待完成。尝试进行下一步点击...")
            
            
            # --- 强制点击复选框/单选框 ---
            try:
                # 强制选择所有未选中的复选框/单选框（可能是同意条款或默认套餐选择）
                checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox' or @type='radio']")
                for cb in checkboxes:
                    if not cb.is_selected():
                        self.driver.execute_script("arguments[0].click();", cb)
                        logger.info(f"⚡ 强制点击了未选中的复选框/单选框 (Name: {cb.get_attribute('name')})")
                        time.sleep(1) 
            except Exception as e:
                logger.warning(f"尝试强制点击复选框/单选框时发生轻微错误: {e}")
            # ----------------------------------------------------------------------


            # 2. 循环点击确认/执行按钮 (Step 2/3/4)
            
            # 检查是否已续期
            if "更新済み" in self.driver.page_source or "Already Renewed" in self.driver.page_source:
                return "今天已续期"
            
            # 包含所有步骤中的关键按钮文本:
            # Step 2: '期限を延長する'
            # Step 3: '確認画面に進む'
            # Step 4: '更新実行' (根据 HTML formaction="/xmgame/game/freeplan/extend/exec" 预测)
            confirm_execute_btn_xpath = (
                "//button[contains(text(), '期限を延長する') or contains(text(), '確認画面に進む') or contains(text(), '更新実行') or contains(text(), '延長手続きを行う') or contains(text(), '次へ') or contains(text(), '確定') or contains(text(), '更新')] | "
                "//a[contains(text(), '期限を延長する') or contains(text(), '確認画面に進む') or contains(text(), '更新実行') or contains(text(), '延長手続きを行う') or contains(text(), '次へ') or contains(text(), '確定') or contains(text(), '更新')]"
            )

            logger.info("在跳转后的页面上，重复搜索并点击执行或下一步确认按钮...")
            
            final_click_count = 0
            max_clicks = 4  # 最多尝试点击 4 次 (入口点击后还有 3 步)
            
            for i in range(max_clicks):
                
                retry_stale = 0
                max_stale_retries = 3
                clicked = False
                
                # 处理 Stale Element Reference Exception 的重试逻辑
                while retry_stale < max_stale_retries:
                    try:
                        # 总是重新定位元素 (Stale 规避)
                        current_btn = self.wait_for_element_present(
                            By.XPATH, 
                            confirm_execute_btn_xpath,
                            20 
                        )
                        
                        # 检查按钮是否可用
                        if not current_btn.is_enabled() or current_btn.get_attribute("class").endswith("btn--loading"):
                            raise Exception("找到的确认按钮不可用或正在加载。")

                        # **核心操作：JS强制点击**
                        self.driver.execute_script("arguments[0].click();", current_btn)
                        logger.info(f"✅ JS强制点击成功。按钮文本: {current_btn.text}")
                        
                        clicked = True
                        break 
                        
                    except StaleElementReferenceException:
                        retry_stale += 1
                        logger.warning(f"检测到 Stale Element 错误。尝试重新定位并点击... (第 {retry_stale} 次)")
                        time.sleep(5) 
                        continue 
                    except TimeoutException:
                        # 如果定位超时，退出 while 循环，进入后面的检查
                        break
                    except Exception as e:
                        # 其他错误直接抛出
                        raise Exception(f"点击过程中发生错误: {str(e)}")


                if not clicked:
                    # 如果未点击成功
                    if final_click_count > 0:
                        logger.info(f"第 {i + 1} 次点击失败。假设之前的点击已完成流程。")
                        return self._check_final_result(final_click_count)
                    else:
                        raise TimeoutException("续行/确认按钮的点击失败或超时。")

                final_click_count += 1
                logger.info(f"✅ 第 {final_click_count} 次点击完成。")
                
                # 每次点击后增加等待时间
                time.sleep(8) 
            
            # 3. 检查最终结果
            return self._check_final_result(final_click_count)

        except TimeoutException as te:
            return f"❌ 更新操作超时：{str(te)}。请手动确认服务状态。"
        except Exception as e:
            return f"❌ 更新过程中发生错误: {str(e)}"

    
    def run(self):
        """执行单个账号的完整续期流程"""
        result = "未执行"
        
        try:
            logger.info(f"开始处理账号: {self.username[:3] + '***'}")
            
            if self.login():
                result = self.renew_service()
                
                info_summary = result 
                logger.info(f"更新结果: {result}")
                
                success = "✅" in result or "已续期" in result
                return success, result, info_summary
            else:
                return False, "登录步骤失败", "登录失败"
                
        except Exception as e:
            error_msg = f"自动更新失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知错误"
            
        finally:
            if self.driver:
                self.driver.quit()

# =========================================================================
# 多账号管理器 (执行入口点)
# =========================================================================

class MultiAccountManager:
    """多账号管理器 - 适配 Xserver"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.server_id = os.getenv('XSERVER_SERVER_ID', '').strip() # 所有账号共用的服务器ID
        self.accounts = self.load_accounts()
        
        if not self.server_id:
            raise ValueError("必需的环境变量 XSERVER_SERVER_ID 未设置。")

    
    def load_accounts(self):
        """从环境变量加载账号信息"""
        accounts = []

        # 单账号设置 (XSERVER_USERNAME 和 XSERVER_PASSWORD)
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        
        if single_username and single_password:
            accounts.append({'username': single_username, 'password': single_password})
        
        if not accounts:
            raise ValueError("未找到有效的 XSERVER 账号设置。")
            
        return accounts
    
    def send_notification(self, results):
        """发送通知到Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("未设置 Telegram 配置。跳过通知。")
            return
        
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            total_count = len(results)
            current_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            message = f"🛠️ Xserver 自动更新通知\n"
            message += f"📊 成功: {success_count}/{total_count}\n"
            message += f"📅 执行时间：{current_date}\n\n"
            
            for username, success, result, server_info in results:
                # 遮盖部分用户名
                masked_username = username[:3] + "***" + username[-4:]
                status = "✅" if success else "❌"
                message += f"账号：{masked_username}\n"
                message += f"{status} 更新结果：{result}\n\n"
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": self.telegram_chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"发送 Telegram 通知失败: {response.text}")
                
        except Exception as e:
            logger.error(f"发送 Telegram 通知时发生错误: {e}")
    
    def run_all(self):
        """运行所有账号的更新流程"""
        all_results = []
        
        if not self.accounts:
            logger.error("没有要处理的账号。退出。")
            return False, []
            
        for account in self.accounts:
            renewal_instance = None
            success = False
            result_msg = ""
            
            try:
                # 传入服务器ID
                renewal_instance = XserverRenewal(account['username'], account['password'], self.server_id)
                success, result_msg, _ = renewal_instance.run()
                
            except Exception as e:
                result_msg = f"致命错误: {str(e)}"
                logger.error(f"处理账号 {account['username'][:3] + '***'} 时发生错误: {result_msg}")
            
            all_results.append((account['username'], success, result_msg, f"服务器ID: {self.server_id}"))

        self.send_notification(all_results)
        
        # 仅当所有账号都成功时返回 True
        return all(success for _, success, _, _ in all_results), all_results

# 执行入口点
if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        success, _ = manager.run_all()
        
        if not success:
            logger.warning("部分或所有账号的更新失败。")
            # 退出代码 1，表明失败
            sys.exit(1)
        else:
            logger.info("所有账号的更新均已正常完成。")
            sys.exit(0)
            
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"发生未预期的严重错误: {e}")
        sys.exit(1)
