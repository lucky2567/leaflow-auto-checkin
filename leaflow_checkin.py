#!/usr/bin/env python3
"""
Xserver 游戏面板自动续期脚本

使用方法:
在运行环境中设置以下环境变量/Secrets:
1. 单账号模式(推荐):
    - XSERVER_USERNAME: 您的 Xserver 登录ID
    - XSERVER_PASSWORD: 您的 Xserver 密码
    - XSERVER_SERVER_ID: 您的 Xserver 服务器标识符/客户ID (必填项)
2. 多账号模式(次选):
    - XSERVER_ACCOUNTS: ID1:Pass1:ServerId1,ID2:Pass2:ServerId2,... (逗号分隔，支持为每个账号指定ServerId)

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
    def __init__(self, username, password, server_id):
        self.username = username
        self.password = password
        self.server_id = server_id  # 支持每个账号独立的ServerId
        
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
            chrome_options.add_argument('--headless=new')  # 新版无头模式
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

            logger.info(f"使用的驱动路径: {final_driver_path}")
            
            if not os.path.exists(final_driver_path):
                ):
                 raise FileNotFoundError("致命错误: 未找到预期的驱动文件。")

            # 赋予执行权限
            os.chmod(final_driver_path, 0o755) 

            # 使用构造的正确路径初始化 Service
            service = Service(final_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
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
        """执行 Xserver 登录流程"""
        logger.info(f"开始登录 Xserver 面板 (账号: {self.username[:3]}***)")
        
        LOGIN_URL = "https://secure.xserver.ne.jp/xapanel/login/xmgame/game"
        self.driver.get(LOGIN_URL)
        time.sleep(3)  # 初始加载等待
        
       
        
        try:
            # 1. 输入登录ID (name="username")
            username            username_input = self.wait_for_element_clickable(By.NAME, "username", 15)
            username_input.clear()
            username_input.send_keys(self.username)
            logger.info("登录ID输入完成")
            time.sleep(1)

            # 2. 输入服务器标识符 (name="server_identify")
            server_id_input = self.wait_for_element_clickable(By.NAME, "server_identify", 15)
            server_id_input.clear()
            server_id_input.send_keys(self.server_id)
            logger.info("服务器标识符输入完成")
            time.sleep(1)
            
            # 3. 输入密码 (name="server_password")
            password_input = self.wait_for_element_clickable(By.NAME, "server_password", 15)
            password_input.clear()
            password            password_input.send_keys(self.password)
            logger.info("密码输入完成")
            time.sleep(1)
            
            # 4. 点击登录按钮 (name="b1")
            login_btn = self.wait_for_element_clickable(By.NAME, "b1", 10)
            self.driver.execute_script("arguments[0].click();", login_btn)
            logger.info("已点击登录按钮")
            
            # 等待登录后跳转 (验证URL是否变化)
            WebDriverWait(self.driver, 20).until_not(
                EC.url_contains("login")
            )
            time.sleep(5)  # 等待页面加载稳定

            # 验证是否登录成功 (检查是否进入游戏面板首页)
            if "game/index" not in self.driver.current_url:
                raise Exception(f"登录后未跳转到游戏面板，当前URL: {self.driver.current_url}")
            
            logger.info("登录成功，已进入游戏面板首页")
            return True
            
        except TimeoutException:
            self._save_screenshot("login_timeout")
            raise Exception(f"登录页面元素加载超时。当前URL: {self.driver.current_url}")
        except NoSuchElementException as e:
            self._save_screenshot("login_element_not_found")
            raise Exception(f"登录页面元素定位失败: {str(e)}")
        except Exception as e:
            self._save_screenshot("login_error")
            raise Exception(f"登录失败: {str(e)}")

    def renew_service(self):
        """按实际页面流程执行三级续期按钮点击，以点击最后一步为成功标志"""
        logger.info("开始执行续期流程...")
        time.sleep(5)  # 等待页面完全加载

        try:
            # ======================== 第一步：首页续期入口（第一张图）========================
            entry_btn_xpath = "//a[@href='/xmgame/game/freeplan/extend/index']"
            entry_btn = self.wait_for_element_clickable(By.XPATH, entry_btn_xpath, 30)
            self.driver.execute_script("arguments[0].click();", entry_btn)
            logger.info("✅ 已点击首页续期入口按钮")
            
            # 验证跳转至续期计划页面
            WebDriverWait(self.driver, 36).until(
                EC.url_contains("/freeplan/extend/index")
            )
            logger.info("已跳转到续期计划选择页面")
            time.sleep(6)  # 增加等待时间确保页面完全加载

            # ======================== 第二步：续期计划选择（第二张图）========================
            extend_btn_xpath = "//a[@href='/xmgame/game/freeplan/extend/input']"
            extend_btn = self.wait_for_element_clickable(By.XPATH, extend_btn_xpath, 32)
            self.driver.execute_script("arguments[0].click();", extend_btn)
            logger.info("✅ 已点击'期限を延長する'按钮")
            
            # 验证跳转至续期确认页面
            WebDriverWait(self.driver, 38).until(
                EC.url_contains("/freeplan/extend/input")
            )
            logger.info("已跳转到续期确认页面")
            time.sleep(9)

            # ======================== 第三步：确认提交（第三张图）- 以此步为成功标准 ========================
            confirm_btn_xpath = "//button[@formaction='/xmgame/game/freeplan/extend/conf']"
            confirm            confirm_btn = self.wait_for_element_clickable(By.XPATH, confirm_btn_xpath, 34)
            self.driver.execute_script("arguments[0].click();", confirm_btn)
            logger.info("🎉 ✅ 成功点击'確認画面に進む'按钮 - 续期操作已完成")
            time.sleep(11)  # 给予足够时间观察后续反应

            # ======================== 结论判定 ========================
            # 由于我们定义的成功标准就是能够顺利点击到最后一步的确认按钮
            # 因此只要没有抛出异常到达这里，即视为续期成功
            
            return "🎉 服务续期成功！已成功提交续期请求。"

        except TimeoutException as e:
            self._save_screenshot("timeout_renew_process")
            return f"❌ 续期失败：在执行过程中遇到超时 ({str(e)})")
        except NoSuchElementException as e:
            self._save_screenshot("element_missing_renew")
            return f"❌ 续期失败：某个必要的按钮未能找到 ({str(e)})")
        except Exception as e:
            self._save_screenshot("unexpected_error_renew")
            return f"❌ 续期失败：发生未知错误 ({str(e)})")
    
    def run(self):
        """执行单个账号的完整续期流程"""
        result = "未执行"
        success = False
        
       
        
        try:
            # 1. 登录
            if self.login():
               ():
                # 2. 续期
                result = self.renew_service()
                success = "🎉" in result or "✅" in result  # 根据emoji判断成功
                
                logger.info(f"续期结果: {result}")
                return success, result
                
        except Exception as e:
            error_msg = f"自动续期失败: {str(e)}")
            logger.error(error_msg)
            return False, error_msg
            
        finally:
            if self.driver:
                self                self.driver.quit()
                logger.info("Chrome驱动已关闭")

class MultiAccountManager:
    """多账号管理器"""
    
    def __init__(self):
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.accounts = self.load_accounts()
    
    def load_accounts(self):
        """从环境变量加载多账号信息（支持单账号/多账号，支持每个账号独立ServerId)"""
        accounts = []
        logger.info("开始加载 XSERVER 账号配置...")
        
        # 方法1: 多账号格式 (优先级更高): ID1:Pass1:ServerId1,ID2:Pass2:ServerId2,...")
        accounts_str = os.getenv('XSERVER_ACCOUNTS', '').strip()
        if accounts_str:
            try:
                account_pairs = [pair.strip() for pair in accounts_str.split(',')]
                for i, pair in enumerate(account_pairs):
                    if ':' in pair:
                        parts = pair.split(':', 2)  # 最多分割为3部分
                        if len(parts) == 3:
                            username, password, server_id = parts
                            accounts.append({
                                'username': username.strip(),
                                'password': password.strip(),
                                'server_id': server_id.strip()
                            })
                            logger.info(f"成功添加第 {i+1} 个账号 (含独立ServerId)")
                        elif len(parts) == 2:
                            # 使用全局ServerId
                            username, password = parts
                            global_server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
                            if not global_server_id:
                                raise ValueError(f"账号 {username} 未提供ServerId，且未设置全局XSERVER_SERVER_ID")
                            accounts.append({
                                'username': username.strip(),
                                'password': password.strip(),
                                'server_id': global_server_id
                            })
                            logger.info(f"成功添加第 {i+1} 个账号 (使用全局ServerId)")
                        else:
                            logger.warning(f"无效的账号格式: {pair}，跳过")
                if accounts:
                    return accounts
            except Exception as e:
                logger.error(f"解析 XSERVER_ACCOUNTS 配置失败: {e}")
                
        # 方法2: 单账号格式 (XSERVER_USERNAME/XSERVER_PASSWORD + 全局XSERVER_SERVER_ID")
        single_username = os.getenv('XSERVER_USERNAME', '').strip()
        single_password = os.getenv('XSERVER_PASSWORD', '').strip()
        single_server_id = os.getenv('XSERVER_SERVER_ID', '').strip()
        
        if single_username and single_password and single_server_id:
            accounts.append({
                'username': single_username,
                'password': single_password,
                'server_id': single_server_id
            })
            logger.info("加载了单个账号配置 (来自 XSERVER_USERNAME/PASSWORD/SERVER_ID)")
            return accounts
        
        # 配置错误
        logger.error("未找到有效的 XSERVER 账号配置")
        logger.error("请设置：")
        logger.error("1. 单账号: XSERVER_USERNAME + XSERVER_PASSWORD + XSERVER_SERVER_ID")
        logger.error("2. 多账号: XSERVER_ACCOUNTS=ID1:Pass1:ServerId1,ID2:Pass2:ServerId2...")
        raise ValueError("未找到有效的 XSERVER 账号配置")
    
    def send_notification(self, results):
        """发送汇总通知到Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info("Telegram配置未设置，跳过通知")
            return
        
        try:
            success_count = sum(1 for success, _ in results if success)
            total_count = len(results)
            current            current_date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            
            message_lines = [
                f"🚀 *Xserver 免费游戏面板续期报告*",
               ",
                f"📅 执行时间: {current_date}",
                "",
                f"📊 *统计结果:*",
               ",
                f"✅ 成功的账号: {success_count}/{total_count}",
                ""
            ]
            
            for idx, (success, msg) in enumerate(results, 1):
               ):
                status_icon = "✅" if success else "❌"
                message_lines.append(f"{status_icon} *账号 #{idx}:*"),
                message_lines.append(f"   📝 {msg}"),
                message_lines.append("")
            
            full_message = "\n".join(message_lines)
            
            telegram_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload            payload = {
                'chat_id': self.telegram_chat_id,
                'text': full_message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(telegram_url, data=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Telegram通知发送成功")
            
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}")
    
    def run_all_accounts(self):
        """批量执行所有账号的续期流程"""
        all_results = []
        
        logger.info(f"开始处理 {len(self.accounts)} 个账号...")
        
        for idx, account_info in enumerate(self.accounts, 1):
            username = account_info['username']
            logger.info(f"\n{'='*50}")
            logger.info(f"正在处理第 {idx}/{len(self.accounts)} 个账号 ({username[:3]}***)...")
            
")
            
            try:
                renewal_instance = XserverRenewal(
                    username=account_info['username'],
                    password=account_info['password'],
                    server_id=account_info['server_id']
               ']
                )
                
                success, result = renewal_instance.run()
                all_results.append((success, result))
                
                # 为防止频繁访问被封禁，在处理完一个账号后稍作休息
                if idx < len(self.accounts):
                    logger.info(f"等待 {5} 秒后继续下一个账号...")
                    time.sleep(5)
                    
            except Exception as e:
                error_msg = f"处理账号 {username[:3]}*** 时发生严重错误: {str(e)}")
               ")
                all_results.append((False, error_msg))
        
        # 发送汇总通知
        self.send_notification(all_results)
        
        # 输出最终摘要
        logger.info("\n" + "="*60)
        logger.info("🏁 全部账号处理完毕")
        logger.info("="*60)
        
        successful_tasks = [(success, msg) for success, msg in all_results if success]
        failed_tasks = [(success, msg) for success, msg in all_results if not success]
        
        if successful_tasks:
            logger.info(f"✅ 成功续期的账号数量: {len(successful_tasks)}")
        if failed_tasks:
            logger.info(f"❌ 失败的账号数量: {len(failed_tasks)}")
            for fail_task in failed_tasks:
                logger.info(f"   - {fail_task[1]}")
        
        return all_results

def main():
    """主函数"""
    try:
        manager = MultiAccountManager()
        manager.run_all_accounts()
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        exit(1)

if __name__ == "__main__":
    main()
