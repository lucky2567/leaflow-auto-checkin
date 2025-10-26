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

# 💥 关键修改 1: 导入 webdriver-manager 相关的库
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
        
        # 💥 关键更新 2: 读取服务器标识符
        # 注意：此处从环境变量读取，并将其作为必填项检查
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
            # 💥 关键修改 3: 使用 ChromeDriverManager 自动获取驱动
            logger.info("正在自动下载并配置 ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome 驱动启动成功。")
        except WebDriverException as e:
            logger.error(f"启动Chrome驱动失败 (WebDriverException)。请检查 'webdriver-manager' 是否安装或 Chrome 是否可用: {e}")
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
        """执行 Xserver 登录流程"""
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
            
            # 等待登录完成，跳转到仪表板页面 (URL包含 'manage' 或 'top')
            WebDriverWait(self.driver, 20).until(
                lambda driver: "manage" in driver.current_url or "top" in driver.current_url
            )
            
            current_url = self.driver.current_url
            if "manage" in current_url or "top" in current_url:
                logger.info(f"登录成功，当前URL: {current_url}")
                return True
            else:
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
        """执行续期操作"""
        RENEWAL_PAGE_URL = "https://secure.xserver.ne.jp/xapanel/manage/xmgame/game"
        self.driver.get(RENEWAL_PAGE_URL)
        logger.info("已导航到服务管理页，等待加载...")
        time.sleep(5)  # 给予页面充分加载时间
        
        try:
            # 2. 查找并点击“延长/更新”按钮
            logger.info("查找服务列表中的 '升级/延长' 或 '更新' 按钮...")
            renewal_btn = self.wait_for_element_clickable(
                By.XPATH, 
                "//button[contains(text(), '延長') or contains(text(), '更新') or contains(text(), 'Upgrade') or contains(text(), 'Renew')] | //a[contains(text(), '延長') or contains(text(), '更新') or contains(text(), 'Upgrade') or contains(text(), 'Renew')]",
                20
            )
            renewal_btn.click()
            logger.info("已点击续期/延长操作按钮，跳转到确认页...")
            time.sleep(5) 
            
            # 3. 确认续期
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
            
            # 4. 检查最终结果
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
        """执行单个账号的完整续期流程"""
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
                pass # 登录失败已在 login() 中抛出异常
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知错误"
            
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
                
        if accounts: return accounts

        # 方法2: 单账号格式 (XSERVER_USERNAME 和 XSERVER_PASSWORD)
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        
        if single_username and single_password:
            # 单账号配置，只传入 username/password，server_id会在 XserverRenewal.__init__ 中从 env 读取
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
                # 隐藏部分用户名
                masked_username = username[:3] + "***" + username[-4:]
                
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
            # 如果 load_accounts 抛出异常，就不会到这里，这是额外的防御性检查
            logger.error("无账号可处理，退出。")
            return False, []
            
        logger.info(f"开始执行 {len(self.accounts)} 个账号的续期任务")
        results = []
        
        for i, account in enumerate(self.accounts, 1):
            logger.info(f"处理第 {i}/{len(self.accounts)} 个账号 ({account['username']})")
            
            try:
                # XserverRenewal.__init__ 将读取 XSERVER_SERVER_ID 环境变量
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
                exit(1) # 退出码 1 表示失败
            else:
                logger.info("所有账号续期完成，流程成功。")
                
    except ValueError as ve:
        logger.error(f"致命配置错误: {ve}")
        exit(1)
    except Exception as e:
        logger.error(f"脚本运行时发生未捕获的全局错误: {e}")
        exit(1)
