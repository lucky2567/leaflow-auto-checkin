#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本（基于实际页面截图优化版）
"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from datetime import datetime
import os.path

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
            raise ValueError("登录ID、密码或服务器标识符（XSERVER_SERVER_ID）不能为空")
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome驱动选项并自动管理ChromeDriver"""
        chrome_options = Options()
        
        # GitHub Actions环境配置 (无头模式)
        if os.getenv('GITHUB_ACTIONS') or os.getenv('CHROME_HEADLESS', 'true').lower() == 'true':
            chrome_options.add_argument('--headless=new')  # 使用新版无头模式
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
            
            driver_path_returned = ChromeDriverManager().install()
            logger.info(f"WebDriverManager 返回的路径: {driver_path_returned}")
            
            # 兼容处理：构造正确的驱动路径
            parent_dir = os.path.dirname(driver_path_returned)
            base_dir = os.path.dirname(parent_dir)
            final_driver_path = os.path.join(base_dir, 'chromedriver-linux64', 'chromedriver')
            
            if not os.path.exists(final_driver_path):
                final_driver_path = driver_path_returned  # 回退到原始路径

            logger.info(f"最终驱动路径: {final_driver_path}")
            
            if not os.path.exists(final_driver_path):
                raise FileNotFoundError(f"未找到驱动文件: {final_driver_path}")

            # 赋予执行权限
            os.chmod(final_driver_path, 0o755)

            # 初始化驱动
            service = Service(final_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            logger.info("Chrome 驱动启动成功")
            
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
        """执行登录流程"""
        logger.info("开始登录 Xserver 面板")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(5)  # 等待登录页加载
        
        try:
            # 输入登录信息（从截图提取的表单字段）
            self.wait_for_element_clickable(By.NAME, "username", 15).send_keys(self.username)
            self.wait_for_element_clickable(By.NAME, "server_identify", 15).send_keys(self.server_id)
            self.wait_for_element_clickable(By.NAME, "server_password", 15).send_keys(self.password)
            
            # 点击登录按钮
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            self.driver.execute_script("arguments[0].click();", login_btn)
            logger.info("已点击登录按钮")
            
            # 等待跳转并验证登录成功
            WebDriverWait(self.driver, 20).until(
                lambda d: "game/index" in d.current_url
            )
            logger.info("登录成功，已进入游戏面板首页")
            return True
            
        except Exception as e:
            raise Exception(f"登录失败: {str(e)}")

    def renew_service(self):
        """基于实际页面截图的精确三步续期流程"""
        
        logger.info("开始执行三步续期流程...")
        time.sleep(5)  # 确保页面完全加载
        
        try:
            # ======================== 步骤1：首页点击续期入口 ========================
            logger.info("步骤1/3：查找首页续期入口按钮...")
            
            # 精确匹配首页绿色续期按钮（从截图提取）
            entry_btn_xpath = "//div[contains(@class, 'free-server-term')]//a[contains(@class, 'btn-renewal') and contains(text(), '期限を延長する')]"
            
            try:
                entry_btn = self.wait_for_element_clickable(By.XPATH, entry_btn_xpath, 20)
                # 高亮并点击
                self.driver.execute_script("arguments[0].style.border='3px solid red';", entry_btn)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", entry_btn)
                logger.info("✅ 成功点击首页续期入口按钮")
            except TimeoutException:
                raise Exception("未找到首页续期入口按钮（步骤1失败）")
            
            # 等待跳转至套餐对比页
            WebDriverWait(self.driver, 20).until(
                lambda d: "extend/index" in d.current_url
            )
            logger.info("已跳转至套餐对比页面")
            time.sleep(5)
            
            # ======================== 步骤2：选择免费套餐 ========================
            logger.info("步骤2/3：选择免费套餐...")
            
            # 精确匹配免费套餐按钮（从截图提取）
            free_plan_btn_xpath = "//table[contains(@class, 'plan-comparison')]//td[contains(text(), '無料')]/following-sibling::td//button[contains(text(), '期限を延長する')]"
            
            try:
                free_plan_btn = self.wait_for_element_clickable(By.XPATH, free_plan_btn_xpath, 20)
                # 高亮并点击
                self.driver.execute_script("arguments[0].style.border='3px solid red';", free_plan_btn)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", free_plan_btn)
                logger.info("✅ 成功选择免费套餐")
            except TimeoutException:
                raise Exception("未找到免费套餐按钮（步骤2失败）")
            
            # 等待跳转至确认页
            WebDriverWait(self.driver, 20).until(
                lambda d: "extend/input" in d.current_url
            )
            logger.info("已跳转至续期确认页面")
            time.sleep(5)
            
            # ======================== 步骤3：提交续期 ========================
            logger.info("步骤3/3：提交续期确认...")
            
            # 精确匹配确认按钮（从截图提取）
            confirm_btn_xpath = "//div[contains(@class, 'free-server-renewal')]//button[contains(text(), '確認画面に進む')]"
            
            try:
                confirm_btn = self.wait_for_element_clickable(By.XPATH, confirm_btn_xpath, 20)
                # 高亮并点击
                self.driver.execute_script("arguments[0].style.border='3px solid red';", confirm_btn)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", confirm_btn)
                logger.info("✅ 成功提交续期确认")
            except TimeoutException:
                raise Exception("未找到确认提交按钮（步骤3失败）")
            
            # 验证最终结果
            WebDriverWait(self.driver, 20).until(
                lambda d: "更新完了" in d.page_source or "success" in d.current_url
            )
            
            # 检查是否真正续期成功
            if "無料サーバー契約期限" in self.driver.page_source:
                return "✅ 服务续期成功！新的到期时间已更新"
            else:
                return "⚠️ 续期流程完成，但未检测到到期时间更新"

        except TimeoutException as te:
            self.driver.save_screenshot("timeout_error.png")
            return f"❌ 续期超时: {str(te)}（请查看timeout_error.png截图）"
        except Exception as e:
            return f"❌ 续期失败: {str(e)}"

    def run(self):
        """执行完整续期流程"""
        try:
            logger.info(f"开始处理账号: {self.username[:3] + '***'}")
            
            if self.login():
                result = self.renew_service()
                logger.info(f"续期结果: {result}")
                return "✅" in result, result, result
            else:
                return False, "登录未成功", "登录失败"
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, "未知错误"
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
        logger.info("开始加载账号配置...")
        
        # 单账号模式
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        
        if single_username and single_password:
            accounts.append({'username': single_username, 'password': single_password})
            logger.info("加载了单个账号配置")
            return accounts
        
        # 多账号模式
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            try:
                for pair in accounts_str.split(','):
                    username, password = pair.split(':', 1)
                    accounts.append({'username': username.strip(), 'password': password.strip()})
                logger.info(f"加载了{len(accounts)}个账号配置")
                return accounts
            except Exception as e:
                raise ValueError(f"多账号配置格式错误: {e}")
        
        raise ValueError("未找到有效的账号配置")
    
    def send_notification(self, results):
        """发送Telegram通知"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("Telegram配置未设置，跳过通知")
            return
        
        try:
            success_count = sum(1 for _, success, _, _ in results if success)
            total_count = len(results)
            current_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            message = f"🛠️ Xserver 自动续期结果\n"
            message += f"📅 时间: {current_date}\n"
            message += f"📊 结果: {success_count}/{total_count} 成功\n\n"
            
            for username, success, result, _ in results:
                masked_user = username[:3] + "***" + username[-4:]
                status = "✅" if success else "❌"
                message += f"{status} {masked_user}\n"
                message += f"   {result[:50]}\n\n"
            
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                data={"chat_id": self.telegram_chat_id, "text": message},
                timeout=10
            )
            logger.info("Telegram通知发送成功")
            
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
    
    def run_all(self):
        """处理所有账号"""
        results = []
        for account in self.accounts:
            try:
                renewal = XserverRenewal(account['username'], account['password'])  
                success, result, info = renewal.run()
                results.append((account['username'], success, result, info))
                
                if len(self.accounts) > 1:
                    logger.info("等待10秒后处理下一个账号...")
                    time.sleep(10)
                    
            except Exception as e:
                results.append((account['username'], False, str(e), "错误"))
        
        self.send_notification(results)
        return all(r[1] for r in results), results

if __name__ == "__main__":
    try:
        manager = MultiAccountManager()
        success, results = manager.run_all()
        if not success:
            logger.error("部分账号续期失败")
            exit(1)
        logger.info("所有账号续期成功")
    except Exception as e:
        logger.error(f"脚本运行失败: {e}")
        exit(1)
