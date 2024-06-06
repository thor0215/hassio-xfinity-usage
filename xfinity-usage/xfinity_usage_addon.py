import os
import json
import logging
import sys
import requests
import urllib.parse
import fnmatch
import time
import base64
import jwt
import re
from datetime import datetime
from time import sleep
from pathlib import Path
from tenacity import stop_after_attempt,  wait_exponential, retry, before_sleep_log
from playwright.sync_api import Playwright, Route, sync_playwright, expect

def get_current_unix_epoch() -> float:
    return time.time()

"""
Playwright sometimes has an uncaught exception.
Restarting Playwright every 12 hrs helps prevent that

/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/utils/debug.js:29
  if (!value) throw new Error(message || 'Assertion error');
                    ^

Error: Assertion error
    at assert (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/utils/debug.js:29:21)
    at FrameManager.frameAttached (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/frames.js:104:25)
    at FFPage._onFrameAttached (/usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffPage.js:175:30)
    at FFSession.emit (node:events:513:28)
    at /usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffConnection.js:204:41

Node.js v18.16.0
    at /usr/local/lib/python3.10/dist-packages/playwright/driver/package/lib/server/firefox/ffConnection.js:204:41

Node.js v18.16.0

"""

POLLING_RATE = float(os.environ.get('POLLING_RATE', "300.0"))
LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper().split('_')[0]
SUPPORT = False
if len(os.environ.get('LOGLEVEL', 'INFO').upper().split('_')) > 1 and 'SUPPORT' == os.environ.get('LOGLEVEL', 'INFO').upper().split('_')[1] : SUPPORT = True
SENSOR_BACKUP = '/config/.sensor-backup'


logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', level=LOGLEVEL, datefmt='%Y-%m-%dT%H:%M:%S')
logger = logging.getLogger(__name__)

if LOGLEVEL == 'DEBUG':
    for name, value in sorted(os.environ.items()):
        if name == 'XFINITY_PASSWORD':
            value = base64.b64encode(base64.b64encode(value.encode()).decode().strip('=').encode()).decode().strip('=')
        logging.debug(f"{name}: {value}")

class xfinityUsage ():
    def __init__(self, playwright: Playwright) -> None:
        self.timeout = int(os.environ.get('PAGE_TIMEOUT', "45")) * 1000

        self.POLLING_RATE = float(os.environ.get('POLLING_RATE', "300.0"))

        self.View_Usage_Url = 'https://customer.xfinity.com/#/devices#usage'
        self.Internet_Service_Url = 'https://www.xfinity.com/learn/internet-service/auth'
        self.Login_Url = f"https://login.xfinity.com/login"
        self.Session_Url = 'https://customer.xfinity.com/apis/session'
        self.Usage_JSON_Url = 'https://api.sc.xfinity.com/session/csp/selfhelp/account/me/services/internet/usage'
        self.Plan_Details_JSON_Url = 'https://api.sc.xfinity.com/session/plan'
        self.BASHIO_SUPERVISOR_API = os.environ.get('BASHIO_SUPERVISOR_API', '')
        self.BASHIO_SUPERVISOR_TOKEN = os.environ.get('BASHIO_SUPERVISOR_TOKEN', '')
        self.SENSOR_NAME = "sensor.xfinity_usage"
        self.SENSOR_URL = f"{self.BASHIO_SUPERVISOR_API}/core/api/states/{self.SENSOR_NAME}"

        self.usage_data = None
        self.is_session_active = False
        self.session_details = {}
        self.plan_details_data = None
        self.reload_counter = 0

        if SUPPORT: self.support_page_hash = int; self.support_page_screenshot_hash = int

        if os.getenv('XFINITY_PASSWORD') and os.getenv('XFINITY_USERNAME'):
            self.xfinity_username = os.getenv('XFINITY_USERNAME')
            self.xfinity_password = os.getenv('XFINITY_PASSWORD')
        else:
            logging.error("No Username or Password specified")
            exit(99)

        if os.path.isfile(SENSOR_BACKUP) and os.path.getsize(SENSOR_BACKUP):
            with open(SENSOR_BACKUP, 'r') as file:
                self.usage_data = file.read()
                self.update_ha_sensor()

        #self.browser = playwright.firefox.launch(headless=False,slow_mo=5000)
        #self.browser = playwright.firefox.launch(headless=False)
        self.browser = playwright.firefox.launch(headless=True)


        self.context = self.browser.new_context(
            service_workers="block",
            screen={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )

        # Block unnecessary requests
        self.context.route("**/*", lambda route: self.abort_route(route))
        self.context.set_default_navigation_timeout(self.timeout)

        self.page = self.context.new_page()

        # Set Default Timeouts
        self.page.set_default_timeout(self.timeout)
        expect.set_options(timeout=self.timeout)

        self.page.on("response", self.check_responses)

    def abort_route(self, route: Route) :
        good_domains = ['*.xfinity.com', '*.comcast.net', 'static.cimcontent.net', '*.codebig2.net']
        bad_resource_types = ['image', 'images', 'stylesheet', 'media', 'font']

        if  route.request.resource_type not in bad_resource_types and \
            any(fnmatch.fnmatch(urllib.parse.urlsplit(route.request.url).netloc, pattern) for pattern in good_domains) :
                route.continue_()
        else:
            route.abort('blockedbyclient')

    def parse_url(self, url) -> str:
        split_url = urllib.parse.urlsplit(url, allow_fragments=True)
        if split_url.fragment:
            return split_url.scheme+'://'+split_url.netloc+split_url.path+'#'+split_url.fragment
        else:
            return split_url.scheme+'://'+split_url.netloc+split_url.path

    def camelTo_snake_case(self, string: str) -> str:
        """Converts camelCase strings to snake_case"""
        return ''.join(['_' + i.lower() if i.isupper() else i for i in string]).lstrip('_')
    
    def debug_support(self) -> None:
        if  SUPPORT and \
            os.path.exists('/config/'):

            datetime_format = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            page_content = self.page.content()
            page_content_hash = hash(base64.b64encode(self.page.content().encode()).decode())
            page_screenshot = self.page.screenshot()
            page_screenshot_hash = hash(base64.b64encode(page_screenshot).decode())
            

            if self.support_page_hash != page_content_hash:
                with open(f"/config/{datetime_format}-page.html", "w") as file:
                    if file.write(page_content):
                        file.close()
                        logging.debug(f"Writing page source to addon_config")
                self.support_page_hash = page_content_hash

            if self.support_page_screenshot_hash != page_screenshot_hash:
                with open(f"/config/{datetime_format}-screenshot.png", "wb") as file:
                    if file.write(page_screenshot):
                        file.close()
                        logging.debug(f"Writing page screenshot to addon_config")
                self.support_page_screenshot_hash = page_screenshot_hash


    def process_usage_json(self, json_data: dict) -> bool:
        _cur_month = json_data['usageMonths'][-1]
        # record current month's information
        # convert key names to 'snake_case'
        attributes = {}
        for k, v in _cur_month.items():
            attributes[self.camelTo_snake_case(k)] = v

        if _cur_month['policy'] == 'limited':
            # extend data for limited accounts
            #attributes['accountNumber'] = json_data['accountNumber']
            attributes['courtesy_used'] = json_data['courtesyUsed']
            attributes['courtesy_remaining'] = json_data['courtesyRemaining']
            attributes['courtesy_allowed'] = json_data['courtesyAllowed']
            attributes['courtesy_months'] = json_data['courtesyMonths']
            attributes['in_paid_overage'] = json_data['inPaidOverage']
            attributes['remaining_usage'] = _cur_month['allowableUsage'] - _cur_month['totalUsage']

        # assign some values as properties
        total_usage = _cur_month['totalUsage']

        json_dict = {}
        json_dict['attributes'] = attributes
        json_dict['attributes']['friendly_name'] = 'Xfinity Usage'
        json_dict['attributes']['unit_of_measurement'] = _cur_month['unitOfMeasure']
        json_dict['attributes']['device_class'] = 'data_size'
        json_dict['attributes']['state_class'] = 'measurement'
        json_dict['attributes']['icon'] = 'mdi:network'
        json_dict['state'] = total_usage

        if  self.plan_details_data is not None and \
            self.plan_details_data.get('InternetDownloadSpeed') and \
            self.plan_details_data.get('InternetUploadSpeed'):
                json_dict['attributes']['internet_download_speeds_Mbps'] = self.plan_details_data['InternetDownloadSpeed']
                json_dict['attributes']['internet_upload_speeds_Mbps'] = self.plan_details_data['InternetUploadSpeed']

        if total_usage >= 0:
            self.usage_data = json.dumps(json_dict)
            logging.info(f"Usage data retrieved and processed")
            logging.debug(f"Usage Data JSON: {self.usage_data}")
        else:
            self.usage_data = None

    def update_sensor_file(self) -> None:
        if  self.usage_data is not None and \
            os.path.exists('/config/'):

            with open(SENSOR_BACKUP, 'w') as file:
                if file.write(self.usage_data):
                    logging.info(f"Updating Sensor File")
                    file.close()


    def update_ha_sensor(self) -> None:
        if  bool(self.BASHIO_SUPERVISOR_API) and \
            bool(self.BASHIO_SUPERVISOR_TOKEN) and \
            self.usage_data is not None:

            headers = {
                'Authorization': 'Bearer ' + self.BASHIO_SUPERVISOR_TOKEN,
                'Content-Type': 'application/json',
            }

            logging.info(f"Updating Sensor: {self.SENSOR_NAME}")

            response = requests.post(
                self.SENSOR_URL,
                headers=headers,
                data=self.usage_data
            )

            if response.ok:
                return None

            if response.status_code == 401:
                logging.error(f"Unable to authenticate with the API, permission denied")
            else:
                logging.error(f"Response Status Code: {response.status_code}")
                logging.error(f"Response: {response.text}")
                logging.debug(f"Response Raw: {response.raw}")

        return None

    def check_jwt_session(self,response) -> None:
        session_data = jwt.decode(response.header_value('x-ssm-token'), options={"verify_signature": False})

        if  session_data['sessionType'] == 'FULL' and \
            session_data['exp'] > time.time() and \
            self.is_session_active == False:
            self.is_session_active = True
            logging.info(f"Updating Session Details")
            logging.debug(f"Updating Session Details {response.url}")
            logging.debug(f"Updating Session Details is_session_active: {self.is_session_active}")
            logging.debug(f"Updating Session Details session time left: {session_data['exp'] - int(time.time())} seconds")
            logging.debug(f"Updating Session Details {json.dumps(session_data)}")

        elif session_data['sessionType'] != 'FULL' or \
            session_data['exp'] <= time.time():
            self.is_session_active = False


    def check_responses(self,response) -> None:
        if response.ok:
            if 'x-ssm-token' in response.headers:
                self.check_jwt_session(response)

            if response.url == self.Plan_Details_JSON_Url:
                self.plan_details_data = {}
                test = response.json()["shoppingOfferDetail"]["dynamicParameters"]
                download_speed = response.json()["shoppingOfferDetail"]["dynamicParameters"][1]["value"].split(" ", 1)[0]
                upload_speed = response.json()["shoppingOfferDetail"]["dynamicParameters"][0]["value"].split(" ",1)[0]
                self.plan_details_data['InternetDownloadSpeed'] = int(download_speed)
                self.plan_details_data['InternetUploadSpeed'] = int(upload_speed)
                logging.info(f"Updating Plan Details")
                logging.debug(f"Updating Plan Details {json.dumps(self.plan_details_data)}")
            """
                {   "accountNumber": "9999999999999999",
                    "courtesyUsed": 0,
                    "courtesyRemaining": 1,
                    "courtesyAllowed": 1,
                    "courtesyMonths": [
                        "03/2023"
                    ],
                    "inPaidOverage": false,
                    "displayUsage": true,
                    "usageMonths": [
                    {   # Array -1 Current month is last element in array
                        "policyName": "1.2 Terabyte Data Plan",
                        "startDate": "04/01/2024",
                        "endDate": "04/30/2024",
                        "homeUsage": 585,
                        "wifiUsage": 0,
                        "totalUsage": 585,
                        "allowableUsage": 1229,
                        "unitOfMeasure": "GB",
                        "displayUsage": true,
                        "devices": [{
                            "id": "AA:BB:1A:B2:C3:4D",
                            "usage": 592,
                            "policyName": "XI Superfast"
                        }],
                        "additionalBlocksUsed": 0,
                        "additionalCostPerBlock": 10,
                        "additionalUnitsPerBlock": 50,
                        "additionalBlockSize": 50,
                        "additionalIncluded": 0,
                        "additionalUsed": 0,
                        "additionalPercentUsed": 0,
                        "additionalRemaining": 0,
                        "billableOverage": 0,
                        "overageCharges": 0,
                        "overageUsed": 0,
                        "currentCreditAmount": 0,
                        "maxCreditAmount": 0,
                        "maximumOverageCharge": 100,
                        "policy": "limited"
                        }]}
            """
            if response.url == self.Usage_JSON_Url:
                if response.json() is not None: self.usage_details_data = response.json()
                logging.info(f"Updating Usage Details")
                logging.debug(f"Updating Usage Details {json.dumps(response.json())}")
                

    def run(self) -> None:
        """
        Main business loop.
            * Go to Usage URL
            * Login if needed
            * Process usage data for HA Sensor
            * Push usage to HA Sensor

        Returns: None
        """
        self.usage_data = None
        self.plan_details_data = None
        self.usage_details_data = None
        self.is_session_active = False

        # Username Section
        self.page.goto(self.Internet_Service_Url)
        logging.info(f"Loading Internet Usage (URL: {self.parse_url(self.page.url)})")
        self.page.wait_for_url(f'{self.Login_Url}*')
        expect(self.page).to_have_title('Sign in to Xfinity')
        expect(self.page.locator("input#user")).to_be_editable()
        logging.info(f"Entering username (URL: {self.parse_url(self.page.url)})")
        self.page.locator("input#user").press_sequentially(self.xfinity_username, delay=100)
        self.debug_support()
        self.page.locator("button[type=submit]#sign_in").click()
        self.debug_support()

        # Password Section
        self.page.wait_for_url(f'{self.Login_Url}*')
        expect(self.page).to_have_title('Sign in to Xfinity')
        expect(self.page.locator("input#passwd")).to_be_editable()
        logging.info(f"Entering password (URL: {self.parse_url(self.page.url)})")
        self.page.locator("input#passwd").press_sequentially(self.xfinity_password, delay=100)
        self.debug_support()
        self.page.locator("button[type=submit]#sign_in").click()
        self.debug_support()

        # Loading Xfinity Internet Customer Overview Page
        self.page.wait_for_url(self.Internet_Service_Url)
        self.page.wait_for_load_state("load")

        while self.plan_details_data is None or self.usage_details_data is None:
            expect(self.page.get_by_test_id('planRowDetail').filter(has=self.page.locator(f"prism-button[href=\"{self.View_Usage_Url}\"]"))).to_be_visible()
            logging.debug(f"Finished loading page (URL: {self.page.url})")

            self.debug_support()

        # Now compile the usage data for the sensor
        self.process_usage_json(self.usage_details_data)

        #if  self.is_session_active and self.usage_data is not None:
        if self.usage_data is not None:
            logging.debug(f"Sensor API Url: {self.SENSOR_URL}")
            self.update_ha_sensor()
            self.update_sensor_file()

# Retry
# Stop retrying after 15 attempts
# Wait exponentially
#
@retry(stop=stop_after_attempt(15),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True)
def run_playwright() -> None:
    """
        * Start Playwright
        * Initialize xfinityUsage class
        * usage.run() to get usage data and push usage to HA Sensor
        * Stop Playwright

    Returns: None
    """
    with sync_playwright() as playwright:
        usage = xfinityUsage(playwright)
        usage.run()
        usage.browser.close()
        playwright.stop()

if __name__ == '__main__':
    """
        * run_playwright does all the work
        * sleep for POLLING_RATE

    Returns: None
    """
    logging.info(f"Xfinity Internet Usage Starting")
    while True:
        try:
            run_playwright()
            logging.info(f"Sleeping for {int(POLLING_RATE)} seconds")
            sleep(POLLING_RATE)
        except:
            exit(98)

