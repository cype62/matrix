# -*- coding: utf-8 -*-
import asyncio
import base64
import io
import pathlib
import time
import traceback
from PIL import Image
from playwright.async_api import Playwright, async_playwright, Page
from conf import BASE_DIR

account_file = "/Users/benny/Documents/github/matrix/xhs_uploader/account/account.json"

async def cookie_auth(account_file):
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
            return False
        except:
            print("[+] cookie 有效")
            return True

async def xhs_setup(account_file_path, handle=False,account_id="",queue_id=""):
    user_info = await xhs_cookie_gen(account_file_path,account_id,queue_id)
    print("23423423:",user_info)
    return user_info

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
                    third_id = third_id_cont.split(": ")[1]
                    user_info = {
                        'account_id':third_id,#小红书号
                        'username':await page.locator("div[class^=account-name]").inner_text(),#用户名
                        'avatar':await page.locator("div[class^=avatar] img").nth(0).get_attribute("src")#头像
                    }
                    # 保存cookie
                    await context.storage_state(path=account_file)
           
            return user_info
    except:
        traceback.print_exc()
        return False

async def show_qr_code(image_data):
    """解码 base64 图像数据并显示出来。"""
    header, encoded = image_data.split(',', 1)
    img_bytes = base64.b64decode(encoded)
    image = Image.open(io.BytesIO(img_bytes))
    image.show()

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
        print("[-]没找到id，继续等待。")
        await asyncio.sleep(1)  # 轮询等待
    return qr_code_id

async def check_qr_code_status(page, qr_code_id):
    """检查二维码的状态，并设置超时。"""
    status_url = f'https://customer.xiaohongshu.com/api/cas/customer/web/qr-code?service=https:%2F%2Fcreator.xiaohongshu.com&qr_code_id={qr_code_id}&source='
    scan = False
    print(not scan)
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

        await asyncio.sleep(2)  # 使用 asyncio.sleep

async def main():
    # await xhs_cookie_gen(None, None, None)
    await cookie_auth(account_file)

if __name__ == '__main__':
    try:
        asyncio.run(main())  # 使用 asyncio.run 执行 main 函数
    except Exception as e:
        traceback.print_exc()