from channels.testing import ChannelsLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class SeleniumTests(ChannelsLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_page_title(self):
        self.driver.get(f"{self.live_server_url}/chat/")
        self.assertIn("chat", self.driver.title)
