# -*- coding: utf-8 -*-
import asyncio
import base64
import io
import os
import pathlib
import traceback
from PIL import Image
from pyzbar.pyzbar import decode
from playwright.async_api import Playwright, async_playwright, Page
import qrcode
import redis
from conf import BASE_DIR, REDIS_CONF

async def cookie_auth(account_file_path, account_id, third_id):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com")
        try:
            await page.wait_for_selector("div.home-card-title('热门活动')", timeout=5000)  # 等待5秒
            print("[+] 等待5秒 cookie 失效")
            await cache_delete(f"xhs_login_status_third_{account_id}_{third_id}")
            context.close()
            browser.close()
            playwright.stop()
            return False
        except:
            print("[+] cookie 有效")
            context.close()
            browser.close()
            playwright.stop()
            return True

async def xhs_setup(account_file_path, handle=True,account_id="",queue_id=""):
    user_info = await xhs_cookie_gen(account_file_path,account_id,queue_id)
    return user_info

def cache_data(key:str,value:str,timeout=60)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.set(key, value)
    redis_client.expire(key, timeout)

def cache_get_data(key:str)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    data = redis_client.get(key)
    if data is not None:  
        # 解码bytes为字符串，这里假设数据是utf-8编码的  
        data_str = data.decode('utf-8')  
        return data_str
    else:  
        return ""
def cache_delete(key:str)->None:
    if REDIS_CONF["password"]:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"],password=REDIS_CONF["password"])
    else:
        redis_client = redis.Redis(host=REDIS_CONF["host"], port=REDIS_CONF["port"], db=REDIS_CONF["select_db"])
    redis_client.delete(key)

async def xhs_cookie_gen(account_file_path,account_id="",queue_id=""):
    try:
        async with async_playwright() as playwright:
            stealth_js_path = pathlib.Path(
                        BASE_DIR) / "xhs_uploader" / "cdn.jsdelivr.net_gh_requireCool_stealth.min.js_stealth.min.js"
            options = {
                'headless': False
            }
            # Make sure to run headed.
            browser = await playwright.chromium.launch(**options)
            # Setup context however you like.
            context = await browser.new_context()  # Pass any options
            # Pause the page, and start recording manually.
            await context.add_init_script(path=stealth_js_path)
            page = await context.new_page()
            await page.goto(url="https://creator.xiaohongshu.com",timeout=20000)
            await page.locator("img").click()
            # 获取二维码base64值
            qrcode_base64 = await page.get_by_role("img").nth(2).get_attribute(name="src")
            cache_data(f"xhs_login_ewm_{queue_id}",qrcode_base64)

            # 显示二维码图片
            await show_qr_code(qrcode_base64)

            # 监听二维码qr_code_id
            qr_code_id = await fetch_qr_code_id(page)
            # 监听扫码状态
            scan_status = None
            if len(qr_code_id) > 0:
                scan_status = await check_qr_code_status(page, qr_code_id)
                await asyncio.sleep(1)
            # 获取cookies
            if scan_status in (1,4):
                await page.goto("https://creator.xiaohongshu.com/new/home")
                await page.wait_for_load_state("networkidle")
                # 判断cookie长度过短说明没登录，无需保存
                cookies = await context.cookies("https://creator.xiaohongshu.com")
                # 默认没获取到用户信息
                user_info = None
                
                # 保存cookie长度不大于9不保存
                if len(cookies) > 9:
                    third_id_cont = await page.get_by_text("小红书账号:").inner_text()
                    third_id = third_id_cont.split(":")[1].strip()
                    user_info = {
                        'account_id':third_id,#小红书号
                        'username':await page.locator("div[class^=account-name]").inner_text(),#用户名
                        'avatar':await page.locator("div[class^=avatar] img").nth(0).get_attribute("src")#头像
                    }
                    account_file = f"{account_file_path}/{account_id}_{third_id}_account.json"
                    # 保存cookie
                    await context.storage_state(path=account_file)
                    # 保存当前用户的登录状态，临时用来检测登陆状态用，只保存60s的状态检测
                    cache_data(f"xhs_login_status_{account_id}",1,60)
                    # 保存小红书号的登录状态，时间一个周
                    cache_data(f"xhs_login_status_third_{account_id}_{third_id}",1,604800)
            # 关闭浏览器
            await context.close()
            await browser.close()
            await playwright.stop()
            return user_info
    except:
        traceback.print_exc()
        return False

async def show_qr_code(image_data):
    """解码 base64 图像数据并显示出来，同时识别二维码内容。"""

    try:
        # 解码图像数据
        img_bytes = base64.b64decode(image_data.split(',', 1)[1])
        image = Image.open(io.BytesIO(img_bytes))
        # image.show()
    except Exception as e:
        print("图像解码失败:", e)
        return None  # 返回 None 表示失败

    # 解码二维码内容
    decoded_objects = decode(image)

    if decoded_objects:
        content = decoded_objects[0].data.decode('utf-8')  # 取第一个二维码内容
        # print("二维码内容:", content)

        # 生成新的二维码
        qr = qrcode.QRCode(version=1, error_correction=qrcode.ERROR_CORRECT_L,
                            box_size=50, border=1)
        qr.add_data(content)
        qr.make()
        qr.print_ascii(tty='#fff')

        return content  # 返回二维码内容
    else:
        print("未检测到二维码")
        return None  # 返回 None 表示没有找到二维码

async def fetch_qr_code_id(page):
    """通过监听响应事件获取二维码 ID。"""
    qr_code_id = None
    async def handle_response(response):
        nonlocal qr_code_id
        if 'api/cas/customer/web/qr-code' in response.url and not qr_code_id:
            try:
                response_json = await response.json()
                qr_code_id = response_json.get('data', {}).get('id')
                if qr_code_id:
                    print(f"QR Code ID: {qr_code_id}")
            except Exception as e:
                print(f"读取响应体错误: {e}")
    page.on('response', handle_response)

    while not qr_code_id:
        print("[-]没找到qrcode_id，继续等待。")
        await asyncio.sleep(1)  # 轮询等待
    return qr_code_id

async def check_qr_code_status(page, qr_code_id):
    """检查二维码的状态，并设置超时。"""
    status_url = f'https://customer.xiaohongshu.com/api/cas/customer/web/qr-code?service=https:%2F%2Fcreator.xiaohongshu.com&qr_code_id={qr_code_id}&source='
    scan = False
    while not scan:
        response = await page.request.get(status_url)
        # 在这里修改成正确的属性访问
        if response.status == 200:
            status_response = await response.json()
            status = status_response.get('data', {}).get('status')
            
            if status == 1:
                print("二维码状态：扫描成功")
                scan = True
                return status
            elif status == 2:
                print("二维码状态：未扫码")
            elif status == 3:
                print("二维码状态：已扫码，未确认")
            elif status == 4:
                print("二维码状态：二维码已失效")
                scan = True
                return status
            else:
                print("无法获取二维码状态。")
                scan = True
                return status
        else:
            print(f"HTTP 错误: {response.status}")

        await asyncio.sleep(1)  # 使用 asyncio.sleep


class XhsVideo(object):
    def __init__(self, title, file_path,preview_path, tags, publish_date, account_file,location="重庆市", thumbnail_path=None):
        self.title = title  # 视频标题
        self.file_path = file_path # 视频文件路径
        self.preview_path = preview_path # 视频预览图路径
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.date_format = '%Y年%m月%d日 %H:%M'
        self.local_executable_path = ""  # change me
        self.location = location
        self.thumbnail_path = thumbnail_path
    
    async def set_schedule_time_xhs(self, page, publish_date):
        # 选择定时发布lable
        await page.get_by_text("定时发布").click()
        await asyncio.sleep(1)
        # publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        
        await asyncio.sleep(1)
        await page.locator('.el-input__inner[placeholder="选择日期和时间"]').click()
        await page.keyboard.press("Control+KeyA")
        # await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.type(publish_date)
        await page.keyboard.press("Enter")

        await asyncio.sleep(1)

    async def handle_upload_error(self, page):
        print("视频出错了，重新上传中")
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        if self.local_executable_path:
            browser = await playwright.chromium.launch(headless=False, executable_path=self.local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=False)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.xiaohongshu.com/publish/publish?from=menu")
        print('[+]正在上传-------{}.mp4'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        print('[-] 正在打开主页...')
        await page.wait_for_url("https://creator.xiaohongshu.com/publish/publish?from=menu")

        # 点击 "上传视频" 按钮
        if not os.path.exists(self.file_path):
            print(f"上传的视频文件不存在，路径是{self.file_path}")
            # 关闭浏览器上下文和浏览器实例
            await context.close()
            await browser.close()
            await playwright.stop()
            return False
        await page.locator("div[class^='drag-over'] input").set_input_files(self.file_path)

        while True:
            # 判断重新上传按钮是否存在，如果不存在，代表视频正在上传，则等待
            try:
                number = await page.get_by_text("替换视频").count()
                if number > 0:
                    print("  [-]视频上传完毕")
                    break
                else:
                    print("  [-] 正在上传视频中...")
                    await asyncio.sleep(2)

                    if await page.get_by_text("上传失败").count():
                        print("  [-] 发现上传出错了...")
                        await self.handle_upload_error(page)
            except:
                print("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

        # 填充标题和话题
        await asyncio.sleep(1)
        print("  [-] 正在填充标题和话题...")
        await page.get_by_placeholder("填写标题会有更多赞哦～").click()
        await page.get_by_placeholder("填写标题会有更多赞哦～").fill(self.title[:30])

        for index, tag in enumerate(self.tags, start = 1):
            print("正在添加第%s个话题" % index)
            await page.locator("#post-textarea").click()
            await page.type("id=post-textarea", "#")
            await asyncio.sleep(0.5)
            await page.type("id=post-textarea", tag)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

        # 定位
        if self.location != 0:
            await self.set_location(page, self.location)

        
        # 定时发布
        if self.publish_date != 0:
            await self.set_schedule_time_xhs(page, self.publish_date)
        
        # 点击 "发布" 按钮
        print("  [-] 正在点击发布...")
        await page.get_by_role("button", name="发布").click()
        

        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                publish_button = page.get_by_role('button', name="发布", exact=True)
                if await publish_button.count():
                    await publish_button.click()
                await page.wait_for_url("https://creator.xiaohongshu.com/publish/success?source&bind_status=not_bind&__debugger__=&proxy=",
                                        timeout=5000)  # 如果自动跳转到作品页面，则代表发布成功
                print("  [-]视频发布成功")
                break
            except:
                # 如果页面是管理页面代表发布成功
                current_url = page.url
                if "https://creator.xiaohongshu.com/publish/success?source&bind_status=not_bind&__debugger__=&proxy=" in current_url:
                    print("  [-]视频发布成功")
                    break
                else:        
                    print("  [-] 视频正在发布中...")
                    # await page.screenshot(full_page=True) 取消截屏
                    await asyncio.sleep(0.5)
        await context.storage_state(path=self.account_file)  # 保存cookie
        print('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例



        await context.close()
        await browser.close()
        await playwright.stop()

    # 修改封面有空再完善
    # async def set_thumbnail(self, page: Page, thumbnail_path: str):
    #     if thumbnail_path:
    #         await page.click('text="选择封面"')
    #         await page.wait_for_selector("div.semi-modal-content:visible")
    #         await page.click('text="上传封面"')
    #         # 定位到上传区域并点击
    #         await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
    #         await page.wait_for_timeout(2000)  # 等待2秒
    #         await page.locator("div[class^='uploadCrop'] button:has-text('完成')").click()

    async def set_location(self, page: Page, location: str = "重庆市"):
        await page.locator('div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap:has-text("添加地点")').click()
        print("clear existing location")
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.press("Delete")
        await page.keyboard.type(self.location)
        await page.wait_for_selector('div[class="d-grid-item"]')
        await asyncio.sleep(0.5)
        await page.locator('div[class="d-grid-item"]').first.click()


    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
