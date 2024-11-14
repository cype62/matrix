from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False)
    # 加载cookie
    context = browser.new_context(storage_state="/Users/benny/Documents/github/matrix/xhs_uploader/account/account.json")
    # 创建一个新页面，并访问小红书探索页面
    page = context.new_page()
    page.goto('https://creator.xiaohongshu.com/')


    # 获取页面标题并打印出来
    title = page.title()
    print('页面标题:', title)

    page.pause()

    browser.close()
