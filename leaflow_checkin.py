def renew_service(self):
        """执行多步骤续期操作：1. 点击入口按钮 -> 2. 循环点击确认/执行按钮"""
        
        logger.info("已位于游戏面板首页，开始查找续期入口按钮...")
        time.sleep(5) 
        
        try:
            # 1. 查找并点击主页上的入口按钮 (Step 1: Go to renewal page)
            logger.info("查找主页上引导进入续期流程的入口按钮...")
            
            entry_btn_xpath = (
                "//button[contains(text(), '期限延長') or contains(text(), '期限を延長する') or contains(text(), '期限を延長していただく必要がございます') or contains(text(), 'アップグレード・期限延長')] | "
                "//a[contains(text(), '期限延長') or contains(text(), '期限を延長する') or contains(text(), '期限を延長していただく必要がございます') or contains(text(), 'アップグレード・期限延長')]"
            )
            
            entry_btn = self.wait_for_element_clickable(
                By.XPATH, 
                entry_btn_xpath,
                20
            )
            # 使用 JS 强制点击入口按钮，以防主页有悬浮物遮挡
            try:
                entry_btn.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", entry_btn)
                logger.warning("入口按钮被拦截，已强制使用 JS 点击。")
                
            logger.info("已点击续期入口按钮，等待跳转到确认/套餐页面...")
            
            # 增加等待时间，确保跳转和DOM稳定
            time.sleep(12) 
            
            # 2. 循环点击确认/执行按钮 (Step 2/3/...)
            
            # 检查是否已经续期 (在新页面上检查)
            if "更新済み" in self.driver.page_source or "Already Renewed" in self.driver.page_source:
                return "今日已续期"
            
            # 最终执行按钮/中间确认按钮 - 包含所有可能性
            confirm_execute_btn_xpath = (
                "//button[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '選択') or contains(text(), '確定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する')] | "
                "//a[contains(text(), '延長手続きを行う') or contains(text(), '確認画面に進む') or contains(text(), '次へ') or contains(text(), '次に進む') or contains(text(), '選択') or contains(text(), '確定') or contains(text(), '完了') or contains(text(), '更新') or contains(text(), '更新する')]"
            )

            logger.info("在跳转后的页面上，循环查找执行或进入下一确认步骤的按钮...")
            
            final_click_count = 0
            max_clicks = 3  # 最多尝试点击三次
            
            for i in range(max_clicks):
                
                # **核心重试块：处理 Stale Element Reference**
                retry_stale = 0
                max_stale_retries = 3
                clicked = False
                current_btn = None
                
                while retry_stale < max_stale_retries:
                    try:
                        # 每次尝试都重新定位元素
                        current_btn = self.wait_for_element_clickable(
                            By.XPATH, 
                            confirm_execute_btn_xpath,
                            10 
                        )
                        
                        if not current_btn.is_enabled():
                            raise Exception("找到的确认按钮不可用，流程中断。")

                        # 解决点击被拦截的问题：优先常规点击，失败则使用 JS 强制点击
                        try:
                            current_btn.click()
                            logger.info(f"使用常规点击成功。按钮文本: {current_btn.text}")
                        except ElementClickInterceptedException:
                            self.driver.execute_script("arguments[0].click();", current_btn)
                            logger.warning(f"点击被拦截，已强制使用 JS 点击。按钮文本: {current_btn.text}")
                        except WebDriverException as e:
                            # 捕获其他 WebDriverException，尝试 JS 强制点击
                            self.driver.execute_script("arguments[0].click();", current_btn)
                            logger.warning(f"常规点击失败 ({str(e)}), 尝试强制 JS 点击。按钮文本: {current_btn.text}")
                        
                        # 成功点击
                        clicked = True
                        break # 跳出 while 循环
                        
                    except StaleElementReferenceException:
                        retry_stale += 1
                        logger.warning(f"检测到 Stale Element 错误，尝试重新定位并点击... (第 {retry_stale} 次)")
                        time.sleep(2) # 短暂等待 DOM 稳定
                        continue # 进入下一次 while 循环
                    except TimeoutException:
                        # 如果定位超时，退出 while 循环，进入后面的检查
                        break
                    except Exception as e:
                        # 捕获其他非 Stale 错误，直接向上抛出
                        raise Exception(f"在定位/点击步骤发生错误: {str(e)}")


                if not clicked:
                    # 如果 while 循环结束但没有点击成功
                    if final_click_count > 0:
                        logger.info(f"第 {i + 1} 次点击失败，但之前已点击 {final_click_count} 次，假定流程结束。")
                        return self._check_final_result(final_click_count)
                    else:
                        # 第一次点击就失败（超时或按钮不可用），抛出异常
                        raise TimeoutException("续期执行/确认按钮首次点击尝试失败或超时。")

                final_click_count += 1
                logger.info(f"✅ 第 {final_click_count} 次点击完成。")
                
                # 每次点击后增加等待时间
                time.sleep(8) 
            
            # 3. 检查最终结果
            return self._check_final_result(final_click_count)

        except TimeoutException as te:
            # 如果在任何一个步骤中超时
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

# ... (MultiAccountManager 保持不变) ...
