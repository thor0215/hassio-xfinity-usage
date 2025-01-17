import asyncio
import base64
import fnmatch
import os
import random
import re
import textwrap
import time
import uuid
import urllib.parse
from datetime import datetime
from playwright.async_api import async_playwright, Playwright, Route, Response, Request, Frame, Page, expect
from playwright_stealth import stealth_async
from playwright_stealth.core import StealthConfig, BrowserType


from xfinity_helper import *
from xfinity_token import get_code_token

CODE_VERIFIER = generate_code_verifier()
CODE_CHALLENGE = generate_code_challenge(CODE_VERIFIER)
STATE = generate_state()
ACTIVITY_ID = str(uuid.uuid1())

def parse_url(url: str) -> str:
    split_url = urllib.parse.urlsplit(url, allow_fragments=True)
    if split_url.fragment:
        return split_url.scheme+'://'+split_url.netloc+split_url.path+'#'+split_url.fragment
    else:
        return split_url.scheme+'://'+split_url.netloc+split_url.path

async def akamai_sleep():
    for sleep in range(5):
        done = sleep+1
        togo = 5-sleep
        await asyncio.sleep(3600) # Sleep for 1 hr then log progress
        logger.error(f"In Akamai Access Denied sleep cycle")
        logger.error(f"{done} {'hour' if done == 1 else 'hours'} done, {togo} to go")

def two_step_verification_handler() -> None:
    logger.error(f"Two-Step Verification is turned on. Exiting...")
    exit(exit_code.TWO_STEP_VERIFICATION.value)

async def get_slow_down_login():
    if SLOW_DOWN_LOGIN:
        await asyncio.sleep(random.uniform(SLOW_DOWN_MIN, SLOW_DOWN_MAX))



class XfinityWebAuth ():
    def __init__(self, playwright: Playwright):
        #super().__init__()
        if XFINITY_PASSWORD is None or XFINITY_USERNAME is None:
            logger.error("No Username or Password specified")
            exit(exit_code.MISSING_LOGIN_CONFIG.value)

        self.timeout = PAGE_TIMEOUT * 1000
        self.playwright = playwright
        self.form_stage = []
        self.username_count = 0
        self.password_count = 0

        self.reload_counter = 0
        self.pending_requests = []
        self.page_title = ''
        self.akamia_error = False
        self.OAUTH_CODE = None
        self.AUTH_URL = OAUTH_AUTHORIZE_URL + '?redirect_uri=xfinitydigitalhome%3A%2F%2Fauth&client_id=xfinity-android-application&response_type=code&prompt=select_account&state=' + STATE + '&scope=profile&code_challenge=' + CODE_CHALLENGE + '&code_challenge_method=S256&activity_id=' + ACTIVITY_ID + '&active_x1_account_count=true&rm_hint=true&partner_id=comcast&mso_partner_hint=true'
        self.AUTH_REFERER = 'android-app://com.xfinity.digitalhome/'

        """
        self.OAUTH_ACCESS_TOKEN = None
        if REFRESH_TOKEN is not None:
            self.OAUTH_REFRESH_TOKEN = REFRESH_TOKEN
        else:
            self.OAUTH_REFRESH_TOKEN = None
        self.OAUTH_ID_TOKEN = None
        self.OAUTH_EXPIRES_IN = None
        self.OAUTH_ACTIVITY_ID = None
        self.OAUTH_TOKEN_TYPE = None
        self.OAUTH_TOKEN_EXTRA_HEADERS = {
            'Content-Type':             'application/x-www-form-urlencoded',
            'Accept':                   'application/json',
            'User-Agent':               'Dalvik/2.1.0 (Linux; U; Android 14; sdk_gphone64_x86_64 Build/UE1A.230829.050)',
            'Accept-Encoding':          'gzip'
        }
        self.OAUTH_TOKEN_DATA = {
            'active_x1_account_count':  'true',
            'partner_id':               'comcast',
            'mso_partner_hint':         'true',
            'scope':                    'profile',
            'rm_hint':                  'true',
            'client_id':                'xfinity-android-application'
        }
        self.OAUTH_USAGE_EXTRA_HEADERS = {
            'x-apollo-operation-name': 'AccountServicesWithoutXM',
            'x-apollo-operation-id':   'cb26cdb7288e179b750ec86d62f8a16548902db3d79d2508ca98aa4a8864c7e1',
            'accept':                  'multipart/mixed; deferSpec=20220824, application/json',
            'user-agent':              'Digital Home / Samsung SM-G991B / Android 14',
            'client':                  'digital-home-android',
            'client-detail':           'MOBILE;Samsung;SM-G991B;Android 14;v5.39.0',
            'accept-language':         'en-US',
            'content-type':            'application/json'
        }
        """
        if DEBUG_SUPPORT: self.support_page_hash = int; self.support_page_screenshot_hash = int

        self.xfinity_block_list = []
        for block_list in os.popen(f"curl -s --connect-timeout {PAGE_TIMEOUT} https://easylist.to/easylist/easyprivacy.txt | grep '^||.*xfinity' | sed -e 's/^||//' -e 's/\^//'"):
            self.xfinity_block_list.append(block_list.rstrip())



    async def start(self):
        self.device = await self.get_browser_device()
        #self.profile_path = await self.get_browser_profile_path()
        self.profile_path = '/config/profile'

        #logger.info(f"Launching {textwrap.shorten(self.device['user_agent'], width=77, placeholder='...')}")

        self.firefox_user_prefs={'webgl.disabled': True, 'network.http.http2.enabled': False}
        #self.firefox_user_prefs={'webgl.disabled': True}
        #self.firefox_user_prefs={'webgl.disabled': False}
        self.webdriver_script = "delete Object.getPrototypeOf(navigator).webdriver"
        #self.webdriver_script = ""

        #self.browser = playwright.firefox.launch(headless=False,slow_mo=1000,firefox_user_prefs=self.firefox_user_prefs)
        #self.browser = await self.playwright.firefox.launch(headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs)
        #self.browser = playwright.firefox.launch(headless=False,firefox_user_prefs=self.firefox_user_prefs,proxy={"server": "http://127.0.0.1:3128"})
        #self.browser = playwright.firefox.launch(headless=True,firefox_user_prefs=self.firefox_user_prefs)

        #self.browser = await self.playwright.chromium.launch(headless=HEADLESS,proxy=PLAYWRIGHT_PROXY)
        #self.browser = await self.playwright.chromium.launch(headless=HEADLESS,channel='chrome',proxy=PLAYWRIGHT_PROXY)
        self.browser = await self.playwright.firefox.launch(headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs,proxy=PLAYWRIGHT_PROXY)
        #self.browser = await self.playwright.firefox.launch(headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs)

        if self.browser.browser_type.name == 'firefox': self.context = await self.browser.new_context(**self.device,ignore_https_errors=True)
        else: self.context = await self.browser.new_context(**self.device,is_mobile=True,ignore_https_errors=True)


        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        #self.context = playwright.firefox.launch_persistent_context(profile_path,headless=False,firefox_user_prefs=self.firefox_user_prefs,**self.device)
        #self.context = await self.playwright.firefox.launch_persistent_context(self.profile_path,headless=HEADLESS,firefox_user_prefs=self.firefox_user_prefs,**self.device)

        self.api_request = self.context.request
        # Block unnecessary requests
        await self.context.route("**/*", lambda route: self.abort_route(route))
        self.context.set_default_navigation_timeout(self.timeout)
        #await self.context.clear_cookies()
        #await self.context.clear_permissions()
        self.context.on("response", self.check_response)
        self.context.on("request", self.check_request)
        self.context.on("requestfailed", self.check_requestfailed)
        self.context.on("requestfinished", self.check_requestfinished)


        #self.page = await self.context.new_page()
        self.page = await self.get_new_page()

        logger.info(f"Launching {textwrap.shorten(await self.page.evaluate('navigator.userAgent'), width=77, placeholder='...')}")

        if  DEBUG_SUPPORT and \
            os.path.exists('/config/'):
            self.page.on("console", lambda consolemessage: debug_support_logger.debug(f"Console Message: {consolemessage.text}"))
            self.page.on("pageerror", self.check_pageerror)
            self.page.on("close", self.check_close)
            self.page.on("domcontentloaded", self.check_domcontentloaded)
            self.page.on("frameattached", self.check_frameattached)
            self.page.on("framenavigated", self.check_framenavigated)
            self.page.on("load", self.check_load)


    async def get_new_page(self) -> Page:
        _page = await self.context.new_page()
        await stealth_async(_page)
        # Set Default Timeouts
        _page.set_default_timeout(self.timeout)
        expect.set_options(timeout=self.timeout)

        # Help reduce bot detection
        await _page.add_init_script(self.webdriver_script)

        return _page

    async def get_browser_device(self) -> dict:
        # Help reduce bot detection
        device_choices = []

        device_choices.append({
            "user_agent": PLAYWRIGHT_USER_AGENT,
            "screen": {"width": 1080,"height": 2400}, "viewport": {"width": 360,"height": 800},
            "device_scale_factor": 3, "has_touch": True
        })
        device_choices.append({
            "user_agent": PLAYWRIGHT_USER_AGENT,
            "screen": {"width": 414,"height": 896}, "viewport": {"width": 414,"height": 896},
            "device_scale_factor": 2, "has_touch": True
        })
        device_choices.append({
            "user_agent": PLAYWRIGHT_USER_AGENT,
            "screen": {"width": 514,"height": 896}, "viewport": {"width": 514,"height": 896},
            "device_scale_factor": 3, "has_touch": True
        })

        return random.choice(device_choices)

    async def get_browser_profile_path(self) -> str:
        if self.device['user_agent']:
            if re.search('Mobile', self.device['user_agent']): return '/config/profile_mobile'
            elif re.search('Ubuntu', self.device['user_agent']): return '/config/profile_linux_ubuntu'
            elif re.search('Fedora', self.device['user_agent']): return '/config/profile_linux_fedora'
            elif re.search('Linux', self.device['user_agent']): return '/config/profile_linux'
            elif re.search('Win64', self.device['user_agent']): return '/config/profile_win'    
        return '/config/profile'

    async def abort_route(self, route: Route) :
        # Necessary Xfinity domains
        good_xfinity_domains = ['*.xfinity.com', '*.comcast.net', 'static.cimcontent.net', '*.codebig2.net', 'xerxes-sub.xerxessecure.com', 'gw.api.dh.comcast.com']
        regex_good_xfinity_domains = ['xfinity.com', 'comcast.net', 'static.cimcontent.net', 'codebig2.net']

        #good_xfinity_domains = ['*.xfinity.com', '*.comcast.net', 'static.cimcontent.net', '*.codebig2.net', '*']
        #regex_good_xfinity_domains = ['xfinity.com', 'comcast.net', 'static.cimcontent.net', 'codebig2.net', '.*']

        # Domains blocked base on Origin Ad Block filters
        regex_block_xfinity_domains = ['.ico$','.mp4$','.vtt$',
                                       '/akam/',
                                       #re.compile('xfinity.com/(?:\w+\/{1}){4,}\w+'), # Will cause Akamai Access Denied
                                       'login.xfinity.com/static/ui-common/',
                                       'login.xfinity.com/static/images/',
                                       'assets.xfinity.com/assets/dotcom/adrum/', 
                                       'xfinity.com/event/',
                                       'metrics.xfinity.com',
                                       'serviceo.xfinity.com',
                                       'serviceos.xfinity.com',
                                       'target.xfinity.com',
                                       'yhm.comcast.net'
                                       ] + self.xfinity_block_list
        """
        regex_block_xfinity_domains = ['.ico$','.mp4$','.vtt$'
                                       ] + self.xfinity_block_list
        regex_block_xfinity_domains = ['quantummetric.com',
                                       'amazonaws.com'] + self.xfinity_block_list
        """

        # Block unnecessary resources
        bad_resource_types = ['image', 'images', 'stylesheet', 'media', 'font']
        #bad_resource_types = []

        headers = await route.request.all_headers()

        if 'sec-ch-ua' in headers and headers['sec-ch-ua'].find('Headless') != -1 :
            headers['sec-ch-ua'] = headers['sec-ch-ua'].replace('Headless','')
            
            

        if  route.request.resource_type not in bad_resource_types and \
            any(fnmatch.fnmatch(urllib.parse.urlsplit(route.request.url).netloc, pattern) for pattern in good_xfinity_domains):
            for urls in regex_block_xfinity_domains:
                if re.search(urls, urllib.parse.urlsplit(route.request.url).hostname + urllib.parse.urlsplit(route.request.url).path):
                    if DEBUG_SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
                    #logger.info(f"Blocked URL: {route.request.url}")
                    await route.abort('blockedbyclient')        
                    return None
            for urls in regex_good_xfinity_domains:
                if  re.search(urls, urllib.parse.urlsplit(route.request.url).hostname) and \
                    route.request.resource_type not in bad_resource_types:
                    if DEBUG_SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
                    #logger.info(f"Good URL: {route.request.url}")
                    response = await route.fetch(headers=headers,
                                                 max_redirects=0,
                                                 timeout=self.timeout)
                    if response.status == 302:
                        await route.fallback()
                    else:                            
                        await route.continue_(headers=headers)     
                    return None
            if DEBUG_SUPPORT: debug_support_logger.debug(f"Good URL: {route.request.url}")
            #logger.info(f"Good URL2: {route.request.url}")
            response = await route.fetch(headers=headers,
                                                 max_redirects=0,
                                                 timeout=self.timeout)
            if response.status == 302:
                await route.fallback()
            else:                            
                await route.continue_(headers=headers)     
            return None
        else:
            if DEBUG_SUPPORT: debug_support_logger.debug(f"Blocked URL: {route.request.url}")
            await route.abort('blockedbyclient')
            return None




    async def debug_support(self) -> None:
        if  DEBUG_SUPPORT and \
            os.path.exists('/config/'):

            datetime_format = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            page_content = await self.page.content()
            page_content_hash = hash(base64.b64encode(await self.page.content().encode()).decode())
            page_screenshot = await self.page.screenshot()
            page_screenshot_hash = hash(base64.b64encode(page_screenshot).decode())


            if self.support_page_hash != page_content_hash:
                with open(f"/config/{datetime_format}-page.html", "w") as file:
                    if file.write(page_content):
                        file.close()
                        logger.debug(f"Writing page source to addon_config")
                self.support_page_hash = page_content_hash

            if self.support_page_screenshot_hash != page_screenshot_hash:
                with open(f"/config/{datetime_format}-screenshot.png", "wb") as file:
                    if file.write(page_screenshot):
                        file.close()
                        logger.debug(f"Writing page screenshot to addon_config")
                self.support_page_screenshot_hash = page_screenshot_hash


    async def check_pageerror(self, exc) -> None:
        debug_support_logger.debug(f"Page Error: uncaught exception: {exc}")

    async def check_frameattached(self, frame: Frame) -> None:
        #self.frameattached_url = frame.page.url
        logger.debug(f"Page frameattached: {frame.page.url}") 

    async def check_close(self, page: Page) -> None:
        #self.close_url = page.url
        logger.debug(f"Page close: {page.url}")

    async def check_domcontentloaded(self, page: Page) -> None:
        #self.domcontentloaded_url = page.url
        logger.debug(f"Page domcontentloaded: {page.url}")

    async def check_load(self, page: Page) -> None:
        #self.load_url = page.url
        logger.debug(f"Page load: {page.url}")

    async def check_framenavigated(self, frame: Frame) -> None:
        #self.framenavigated_url = frame.page.url
        logger.debug(f"Page framenavigated: {frame.page.url}")

    async def check_request(self, request: Request) -> None:
        self.pending_requests.append(request)

        if  LOG_LEVEL == 'DEBUG' and \
            request.is_navigation_request() and \
            request.method == 'POST' and \
            request.url.find('login.xfinity.com') != -1:
                logger.debug(f"Request: {request.method} {request.url}")
                logger.debug(f"Request: {request.method} {request.post_data}")
                logger.debug(f"Request: {request.method} {request.headers}")

    async def check_requestfailed(self, request: Request) -> None:
        self.pending_requests.remove(request)

    async def check_requestfinished(self, request: Request) -> None:
        self.pending_requests.remove(request)

    async def check_response(self,response: Response) -> None:
        logger.debug(f"Network Response: {response.status} {response.url}")

        if response.status == 302:
            logger.debug(f"Redirect url: {response.headers['location']}")
            location_parse = urllib.parse.urlparse(response.headers.get('location',''))
            if location_parse.scheme == 'xfinitydigitalhome':
                query_params = urllib.parse.parse_qs(location_parse.query)
                self.OAUTH_CODE = query_params['code'][0]
                logger.debug(f"Token Code: {self.OAUTH_CODE}")

        else:
            if  response.status == 403:
                if response.headers.get('server','') == 'AkamaiGHost':
                    self.akamia_error = True


    async def get_authentication_form_inputs(self) -> list:
        return await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[type="text"], input[type="password"]').all()


    async def get_authentication_form_hidden_inputs(self) -> None:
        hidden_inputs = await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[type="hidden"]').all()
        if LOG_LEVEL == 'DEBUG':
            logger.debug(f"Number of hidden inputs: {len(hidden_inputs)}")
            for input in hidden_inputs:
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")


    async def get_page_title(self) -> str:
        try:
            return await self.page.title()
        except:
            return ''


    async def check_authentication_form(self):
        #self.page.wait_for_url(re.compile('https://(?:www|login)\.xfinity\.com(?:/learn/internet-service){0,1}/(?:auth|login).*'))

        #_title = self.page_title
        if len(self.pending_requests) == 0:
            logger.debug(f'pending requests {len(self.pending_requests)}')
            #await self.page.wait_for_load_state('networkidle')
            _title = await self.get_page_title()

            #if  self.frameattached_url == self.framenavigated_url and \
            #    re.match('https://(?:www|login)\.xfinity\.com(?:/learn/internet-service){0,1}/login',self.frameattached_url) and \
            if _title == 'Sign in to Xfinity':
                    #expect(self.page).to_have_title('Sign in to Xfinity')
                    if await self.page.locator('main').locator("form[name=\"signin\"]").is_enabled():
                        for input in await self.get_authentication_form_inputs():
                            _input_id = await input.get_attribute("id")
                            if LOG_LEVEL == 'DEBUG':
                                logger.debug(f"{self.page.url}")
                                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")
                                submit_button = await self.page.locator('main').locator("form[name=\"signin\"]").locator('button#sign_in.sc-prism-button').evaluate('el => el.outerHTML') 
                                logger.debug(f"{submit_button}")

                            #<input class="input text contained body1 sc-prism-input-text" id="user" autocapitalize="off" autocomplete="username" autocorrect="off" inputmode="text" maxlength="128" name="user" placeholder="Email, mobile, or username" required="" type="text" aria-invalid="false" aria-required="true" data-ddg-inputtype="credentials.username">
                            #<input id="user" name="user" type="text" autocomplete="username" value="username" disabled="" class="hidden" data-ddg-inputtype="credentials.password.current">
                            if _input_id == 'user' and \
                                await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[name="flowStep"]').get_attribute("value") == "username":
                                if await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').is_editable():
                                    self.form_stage.append('Username')
                                    if self.username_count < 2:
                                        await self.enter_username()
                                        self.username_count += 1
                                        await self.wait_for_submit_button()
                                    else:
                                        logger.error(f"Navigated to username page for the {ordinal(self.username_count)} time. Exiting...")
                                        exit(exit_code.TOO_MANY_USERNAME.value)


                            #<input class="input icon-trailing password contained body1 sc-prism-input-text" id="passwd" autocapitalize="none" autocomplete="current-password" autocorrect="off" inputmode="text" maxlength="128" name="passwd" required="" type="password" aria-invalid="false" aria-required="true" aria-describedby="passwd-hint">
                            elif _input_id == 'passwd' and \
                                await self.page.locator('main').locator("form[name=\"signin\"]").locator('input[name="flowStep"]').get_attribute("value") == "password":
                                passwd_value = await self.page.locator('main').locator("form[name=\"signin\"]").locator('prism-input-text[name="passwd"]').get_attribute('value')
                                userid_value = await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').get_attribute("value")
                                if  await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').get_attribute("value") == XFINITY_USERNAME and \
                                    await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#user').is_disabled() and \
                                    await self.page.locator('main').locator("form[name=\"signin\"]").locator('input#passwd').is_editable() and \
                                    await self.page.locator('main').locator("form[name=\"signin\"]").locator('prism-input-text[name="passwd"]').get_attribute('value') is None:


                                    if await self.page.locator('main').locator("form[name=\"signin\"]").locator('prism-input-text[name="passwd"]').get_attribute('invalid-message') == 'The Xfinity ID or password you entered was incorrect. Please try again.':
                                        logger.error(f"Bad password. Exiting...")
                                        exit(exit_code.BAD_PASSWORD.value)

                                    if self.password_count < 2:
                                        self.form_stage.append('Password')
                                        await self.enter_password()
                                        self.password_count += 1 
                                        #await self.wait_for_submit_button()
                                    else:
                                        logger.error(f"Navigated to password page for the  {ordinal(self.password_count)} time. Exiting...")
                                        exit(exit_code.TOO_MANY_PASSWORD.value)
                                elif await self.page.locator('main').locator("form[name=\"signin\"]").locator('prism-input-text[name="passwd"]').get_attribute('value') == XFINITY_PASSWORD:
                                    return
                                else:
                                    raise AssertionError("Password form page is missing the user id")

                            elif 'Password' in self.form_stage and _input_id == 'verificationCode':
                                await self.check_for_two_step_verification()

                    # Didn't find signin form
                    else:
                        if LOG_LEVEL == 'DEBUG':
                            for input in await self.page.locator('main').get_by_role('textbox').all():
                                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")
                        raise AssertionError("Signin form is missing")

    async def enter_username(self):
        # Username Section
        logger.info(f"Entering username (URL: {parse_url(self.page.url)})")
        await self.get_authentication_form_hidden_inputs()
        await get_slow_down_login()

        all_inputs = await self.get_authentication_form_inputs()
        if len(all_inputs) != 1:
            raise AssertionError("Username page: not the right amount of inputs")

        #self.session_storage = self.page.evaluate("() => JSON.stringify(sessionStorage)")

        if LOG_LEVEL == 'DEBUG':
            for input in all_inputs:
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")

        await self.page.locator("input#user").click()
        await get_slow_down_login()
        await self.page.locator("input#user").press_sequentially(XFINITY_USERNAME, delay=150)
        await get_slow_down_login()
        await self.debug_support()
        await self.page.locator("input#user").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        await self.debug_support()

    async def enter_password(self):
        # Password Section
        logger.info(f"Entering password (URL: {parse_url(self.page.url)})")
        await self.get_authentication_form_hidden_inputs()
        await get_slow_down_login()

        all_inputs = await self.get_authentication_form_inputs()
        if len(all_inputs) != 2:
                raise AssertionError("not the right amount of inputs")

        await self.page.locator("input#passwd").click()
        await get_slow_down_login()

        await expect(self.page.get_by_label('toggle password visibility')).to_be_visible()
        await self.page.locator("input#passwd").press_sequentially(XFINITY_PASSWORD, delay=175)
        await get_slow_down_login()
        await self.debug_support()

        if LOG_LEVEL == 'DEBUG':
            for input in await self.get_authentication_form_inputs():
                logger.debug(f"{await input.evaluate('el => el.outerHTML')}")

        await self.page.locator("input#passwd").press("Enter")
        #self.page.locator("button[type=submit]#sign_in").click()
        await self.debug_support()

    async def wait_for_submit_button(self) -> None:
        try:
            _submit_button = self.page.locator('main').locator("form[name=\"signin\"]").locator('button#sign_in.sc-prism-button')
            #await expect(_submit_button.locator('div.loading-spinner')).to_be_attached()
            await _submit_button.locator('div.loading-spinner').wait_for(state='visible')
            logger.debug(f"{await _submit_button.evaluate('el => el.outerHTML')}")
            await _submit_button.locator('div.loading-spinner').wait_for(state='detached')
            #self.page.wait_for_load_state('domcontentloaded')
        finally:
            return


    async def check_for_two_step_verification(self):
        # Check for Two Step Verification
        logger.info(f"Two Step Verification Check: Page Title {await self.get_page_title()}")
        logger.info(f"Two Step Verification Check: Page Url {self.page.url}")
        await self.get_authentication_form_hidden_inputs()

        for input in await self.get_authentication_form_inputs():
            logger.error(f"{await input.evaluate('el => el.outerHTML')}")
            if re.search('id="user"',await input.evaluate('el => el.outerHTML')):
                raise AssertionError("Password form submission failed")

            if  re.search('id="verificationCode"',await input.evaluate('el => el.outerHTML')) and \
                await self.page.locator("input#verificationCode").is_enabled():
                    two_step_verification_handler()

    async def get_authenticated(self) -> None:
        if self.browser.browser_type.name == 'firefox':
            browser_type = BrowserType.FIREFOX
        else:
            browser_type = BrowserType.CHROME

        await stealth_async(self.page,
                            StealthConfig(browser_type=browser_type)
                            )
        
        await self.page.set_extra_http_headers({"referer": self.AUTH_REFERER,
                                                })
        if self.browser.browser_type.name != 'firefox':
            await self.page.set_extra_http_headers({"sec-ch-ua": '"Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                                                    })
        await self.page.goto(self.AUTH_URL)
        #await self.page.goto(self.AUTH_URL, referer=self.AUTH_REFERER)
        logger.info(f"Loading Xfinity Authentication (URL: {parse_url(self.page.url)})")

        _start_time = time.time()
        while(self.OAUTH_CODE is None and not self.akamia_error):

            #await self.check_for_authentication_errors()
            #if len(self.pending_requests) == 0:
            await self.check_authentication_form()
            await get_slow_down_login()

            if self.akamia_error:
                token_code = {
                    "activity_id": ACTIVITY_ID,
                    "code_verifier": CODE_VERIFIER,
                }
                write_token_code_file_data(token_code)

                logger.error(f"""Akamai Access Denied error!!
Using a browser, manually go to this url and login:
{self.AUTH_URL}

ACTIVITY_ID: {ACTIVITY_ID}
CODE_VERIFIER: {CODE_VERIFIER}
 """)
                raise AssertionError(f"Akamai Access Denied error!!")
            

            if time.time()-_start_time > PAGE_TIMEOUT*2 and self.OAUTH_CODE is None:
                raise AssertionError(f"Login Failed: Please try again.")

        await self.page.close()

    async def run(self) -> None:
        """
        Main business loop.
            * Go to Usage URL
            * Login if needed
            * Process usage data for HA Sensor
            * Push usage to HA Sensor
        Returns: None
        """

        """
        await self.page.set_extra_http_headers({
            'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'accept-language': 'en-US',
            'upgrade-insecure-requests': '1',
            # 'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-dest': 'document',
            'referer': 'android-app://com.xfinity.digitalhome/'
        })
        """

        #await self.page.goto(XFINITY_START_URL)

        await self.start()
        await self.get_authenticated()



async def playwright_get_code():
    logger.info(f"Xfinity Webpage Login Process Starting")
    async with async_playwright() as playwright:
        xfinityWebAuth = XfinityWebAuth(playwright)
        try:
            await xfinityWebAuth.run()
            return get_code_token(xfinityWebAuth.OAUTH_CODE, ACTIVITY_ID, CODE_VERIFIER)

        except AssertionError as msg:
            logger.error(f"AssertionError: {msg}")
            return None
