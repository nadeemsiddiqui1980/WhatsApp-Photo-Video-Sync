from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


@dataclass
class DownloadedMedia:
    local_temp_path: Path
    message_time: datetime
    sender: str
    message_id: str


class WhatsAppClient:
    """Minimal WhatsApp Web collector skeleton.

    Note: Selectors on WhatsApp Web can change. Keep selector logic isolated here.
    """

    def __init__(
        self,
        group_name: str,
        profile_dir: str,
        temp_download_dir: str,
        headless: bool = False,
        startup_timeout_seconds: int = 180,
        download_timeout_seconds: int = 30,
        message_scan_limit: int = 30,
        browser: str = "auto",
    ) -> None:
        self.group_name = group_name
        self.profile_dir = Path(profile_dir)
        self.temp_download_dir = Path(temp_download_dir)
        self.headless = headless
        self.startup_timeout_seconds = startup_timeout_seconds
        self.download_timeout_seconds = download_timeout_seconds
        self.message_scan_limit = message_scan_limit
        self.browser = browser.lower()
        self.driver = None
        self._seen_message_ids: set[str] = set()
        self._group_chat_opened = False

    @staticmethod
    def _find_existing_browser(preference: str) -> tuple[str, str]:
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        edge_paths = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]

        has_chrome = next((p for p in chrome_paths if Path(p).exists()), "")
        has_edge = next((p for p in edge_paths if Path(p).exists()), "")

        if not has_chrome:
            has_chrome = shutil.which("chrome.exe") or shutil.which("chrome") or ""
        if not has_edge:
            has_edge = shutil.which("msedge.exe") or shutil.which("msedge") or ""

        # Honor explicit preference first; otherwise auto-prefer Chrome.
        if preference == "edge":
            if has_edge:
                return "edge", has_edge
            raise RuntimeError("Browser preference is 'edge' but Microsoft Edge was not found.")
        if preference == "chrome":
            if has_chrome:
                return "chrome", has_chrome
            raise RuntimeError("Browser preference is 'chrome' but Google Chrome was not found.")

        if has_chrome:
            return "chrome", has_chrome
        if has_edge:
            return "edge", has_edge
        
        raise RuntimeError("No supported browser found. Microsoft Edge comes with Windows 10/11 by default. If missing, install from: https://www.microsoft.com/edge/download")

    def start(self) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.temp_download_dir.mkdir(parents=True, exist_ok=True)

        browser_name, browser_binary = self._find_existing_browser(self.browser)

        if browser_name == "chrome":
            chrome_options = Options()
            chrome_options.binary_location = browser_binary
            
            chrome_options.add_argument(f"--user-data-dir={self.profile_dir.resolve()}")
            
            # Add download preferences
            chrome_options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": str(self.temp_download_dir.resolve()),
                    "download.prompt_for_download": False,
                    "profile.default_content_setting_values.automatic_downloads": 1,
                },
            )
            
            # Chrome startup flags
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--remote-debugging-pipe")
            
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            try:
                self.driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to start Chrome. Please ensure you have a 64-bit version installed.\n"
                    f"Recommended: Use Microsoft Edge instead (comes with Windows).\n"
                    f"Chrome: https://www.google.com/chrome/ (install 64-bit version)\n"
                    f"Error: {str(e)}"
                )
        else:
            edge_options = webdriver.EdgeOptions()
            edge_profile_dir = self.profile_dir / "edge"
            edge_profile_dir.mkdir(parents=True, exist_ok=True)
            edge_options.add_argument(f"--user-data-dir={edge_profile_dir.resolve()}")
            
            edge_options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": str(self.temp_download_dir.resolve()),
                    "download.prompt_for_download": False,
                    "profile.default_content_setting_values.automatic_downloads": 1,
                },
            )
            
            # Edge startup flags
            edge_options.add_argument("--start-maximized")
            edge_options.add_argument("--disable-notifications")
            edge_options.add_argument("--disable-extensions")
            edge_options.add_argument("--disable-sync")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--disable-dev-shm-usage")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument("--disable-software-rasterizer")
            edge_options.add_argument("--no-first-run")
            edge_options.add_argument("--no-default-browser-check")
            # More reliable transport on Windows than remote-debugging-port.
            edge_options.add_argument("--remote-debugging-pipe")
            # Helps in hardened Windows environments where renderer attach can fail.
            edge_options.add_argument("--disable-features=RendererCodeIntegrity")
            
            if self.headless:
                edge_options.add_argument("--headless=new")
            
            try:
                self.driver = webdriver.Edge(
                    options=edge_options
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to start Microsoft Edge. Edge comes with Windows by default.\n"
                    f"Try: 1) Update Windows, 2) Restart computer, 3) Reinstall Edge\n"
                    f"Edge download: https://www.microsoft.com/edge/download\n"
                    f"Error: {str(e)}"
                )

        self.driver.get("https://web.whatsapp.com/")
        self._wait_until_logged_in()
        self._open_group_chat()
        self._group_chat_opened = True

    def _wait_until_logged_in(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")
        wait = WebDriverWait(self.driver, self.startup_timeout_seconds)
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='pane-side']"))
        )

    def _find_first(self, xpaths: list[str], timeout_seconds: int = 10):
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")
        end_time = time.time() + timeout_seconds
        while time.time() < end_time:
            for xp in xpaths:
                elems = self.driver.find_elements(By.XPATH, xp)
                for elem in elems:
                    if elem.is_displayed():
                        return elem
            time.sleep(0.3)
        raise TimeoutException(f"No matching element found for xpaths: {xpaths}")

    def _open_group_chat(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.1)

        direct = self.driver.find_elements(
            By.XPATH,
            f"//div[@id='pane-side']//span[@title={self._xpath_literal(self.group_name)}]",
        )
        if direct:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", direct[0])
            direct[0].click()
            return

        try:
            search_box = self._find_first(
                [
                    "//div[@id='side']//div[@contenteditable='true' and @role='textbox']",
                    "//div[@id='side']//div[@contenteditable='true'][@data-tab]",
                    "//div[@id='side']//*[@contenteditable='true']",
                ],
                timeout_seconds=20,
            )
        except TimeoutException:
            return
        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(Keys.BACKSPACE)
        search_box.send_keys(self.group_name)

        result = self._find_first(
            [
                f"//div[@id='pane-side']//span[@title={self._xpath_literal(self.group_name)}]",
                f"//span[@title={self._xpath_literal(self.group_name)}]",
            ],
            timeout_seconds=20,
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", result)
        result.click()

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

    def _message_rows_with_images(self):
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")
        rows = self.driver.find_elements(
            By.XPATH,
            "//div[@id='main']//div[@data-id and .//*[name()='img']]",
        )
        return rows[-self.message_scan_limit :]

    def _message_scroll_container(self):
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # WhatsApp uses a virtualized chat list inside a nested scrollable DIV.
        container = self.driver.execute_script(
            """
            const nodes = Array.from(document.querySelectorAll('#main *'));
            for (const el of nodes) {
                const st = getComputedStyle(el);
                if (el.scrollHeight > el.clientHeight + 20 &&
                    (st.overflowY === 'auto' || st.overflowY === 'scroll')) {
                    return el;
                }
            }
            return null;
            """
        )
        return container

    def _jump_to_latest_messages(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        container = self._message_scroll_container()
        if container:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            time.sleep(0.25)
        else:
            # Fallback if container lookup fails.
            body = self.driver.find_element(By.TAG_NAME, "body")
            for _ in range(3):
                body.send_keys(Keys.END)
                time.sleep(0.25)

    def _snapshot_temp_files(self) -> set[Path]:
        # Ignore transient download artifacts; keep only candidate final files.
        return {
            p
            for p in self.temp_download_dir.glob("*")
            if p.is_file()
            and not p.name.endswith(".crdownload")
            and p.suffix.lower() != ".tmp"
        }

    def _wait_for_download(self, before_files: set[Path]) -> Path:
        end_time = time.time() + self.download_timeout_seconds
        allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}

        while time.time() < end_time:
            after_files = self._snapshot_temp_files()
            new_files = [p for p in after_files - before_files if p.exists()]
            image_files = [p for p in new_files if p.suffix.lower() in allowed_exts]

            if image_files:
                image_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return image_files[0]

            time.sleep(0.5)

        raise TimeoutException("Timed out waiting for WhatsApp image download")

    def _click_download(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")
        download_elem = self._find_first(
            [
                "//span[@data-icon='download']/ancestor::button[1]",
                "//button[@aria-label='Download']",
                "//button[contains(@aria-label,'ownload')]",
                "//button[contains(@title,'ownload')]",
                "//*[@role='button' and contains(@aria-label,'ownload')]",
                "//span[@data-icon='download']",
            ],
            timeout_seconds=8,
        )
        download_elem.click()

    def _open_media_preview_from_row(self, row) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        candidates = row.find_elements(
            By.XPATH,
            ".//div[@role='button' and descendant::*[name()='img']]",
        )
        if not candidates:
            candidates = row.find_elements(By.XPATH, ".//*[name()='img']")

        for elem in candidates:
            if not elem.is_displayed():
                continue
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
            try:
                elem.click()
                return
            except (ElementNotInteractableException, ElementClickInterceptedException):
                try:
                    self.driver.execute_script("arguments[0].click();", elem)
                    return
                except Exception:
                    continue

        raise TimeoutException("Could not open media preview from message row")

    @staticmethod
    def _parse_pre_plain_text(value: Optional[str]) -> tuple[datetime, str]:
        now = datetime.now()
        if not value:
            return now, "Unknown"

        # Example: [9:55 PM, 17/03/2026] Alice:
        match = re.search(r"\[(.*?)\]\s*(.*?):\s*$", value)
        if not match:
            return now, "Unknown"

        dt_text = match.group(1).strip()
        sender = match.group(2).strip() or "Unknown"
        dt_patterns = [
            "%I:%M %p, %d/%m/%Y",
            "%H:%M, %d/%m/%Y",
            "%I:%M %p, %m/%d/%Y",
            "%H:%M, %m/%d/%Y",
        ]
        for pat in dt_patterns:
            try:
                return datetime.strptime(dt_text, pat), sender
            except ValueError:
                continue
        return now, sender

    def fetch_new_images(self) -> List[DownloadedMedia]:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        if not self._group_chat_opened:
            self._open_group_chat()
            self._group_chat_opened = True
        self._jump_to_latest_messages()
        collected: List[DownloadedMedia] = []

        # WhatsApp virtualizes chat DOM. Scan multiple pages upward so older media rows are seen.
        stable_passes = 0
        max_passes = 30
        scroll_container = self._message_scroll_container()

        for _ in range(max_passes):
            rows = self._message_rows_with_images()
            newly_seen_in_pass = 0

            # Iterate by index so we can re-query rows on each retry when DOM re-renders.
            row_count = len(rows)
            for reverse_index in range(row_count):
                row_index = row_count - 1 - reverse_index
                row_retry_count = 0
                max_row_retries = 2

                while row_retry_count <= max_row_retries:
                    try:
                        current_rows = self._message_rows_with_images()
                        if row_index >= len(current_rows):
                            break

                        row = current_rows[row_index]
                        message_id = row.get_attribute("data-id") or ""
                        if not message_id or message_id in self._seen_message_ids:
                            break

                        msg_meta = row.get_attribute("data-pre-plain-text")
                        msg_time, sender = self._parse_pre_plain_text(msg_meta)

                        # A single message can contain multiple media tiles.
                        photo_buttons = row.find_elements(By.XPATH, ".//div[@role='button' and descendant::*[name()='img']]")
                        if not photo_buttons:
                            photo_buttons = row.find_elements(By.XPATH, ".//*[name()='img']")

                        # Process photos with retry for stale elements (WhatsApp's virtualized DOM invalidates refs)
                        for photo_index in range(len(photo_buttons)):
                            before = self._snapshot_temp_files()
                            preview_opened = False
                            downloaded_file: Optional[Path] = None
                            stale_retry_count = 0
                            max_stale_retries = 2

                            while stale_retry_count <= max_stale_retries:
                                try:
                                    # Re-query the photo buttons each iteration to avoid stale refs
                                    # (DOM may have changed due to scrolling or re-renders)
                                    current_photos = row.find_elements(By.XPATH, ".//div[@role='button' and descendant::*[name()='img']]")
                                    if not current_photos:
                                        current_photos = row.find_elements(By.XPATH, ".//*[name()='img']")

                                    if photo_index >= len(current_photos):
                                        # Photo list changed; skip this iteration
                                        break

                                    photo_button = current_photos[photo_index]

                                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", photo_button)
                                    time.sleep(0.2)
                                    try:
                                        photo_button.click()
                                    except (ElementNotInteractableException, ElementClickInterceptedException):
                                        self.driver.execute_script("arguments[0].click();", photo_button)

                                    preview_opened = True
                                    self._click_download()
                                    downloaded_file = self._wait_for_download(before)
                                    break
                                except StaleElementReferenceException:
                                    stale_retry_count += 1
                                    if stale_retry_count <= max_stale_retries:
                                        time.sleep(0.1)
                                    else:
                                        break
                                except TimeoutException:
                                    break
                                finally:
                                    if preview_opened:
                                        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                                        time.sleep(0.2)

                            if downloaded_file is not None:
                                collected.append(
                                    DownloadedMedia(
                                        local_temp_path=downloaded_file,
                                        message_time=msg_time,
                                        sender=sender,
                                        message_id=message_id,
                                    )
                                )

                        self._seen_message_ids.add(message_id)
                        newly_seen_in_pass += 1
                        break
                    except StaleElementReferenceException:
                        row_retry_count += 1
                        if row_retry_count <= max_row_retries:
                            time.sleep(0.1)
                        else:
                            break

            if newly_seen_in_pass == 0:
                stable_passes += 1
            else:
                stable_passes = 0

            if stable_passes >= 3:
                break

            # Scroll upward to load older rows into the virtualized DOM.
            if scroll_container:
                prev_top = self.driver.execute_script("return arguments[0].scrollTop;", scroll_container)
                self.driver.execute_script(
                    "arguments[0].scrollTop = Math.max(0, arguments[0].scrollTop - Math.floor(arguments[0].clientHeight * 0.9));",
                    scroll_container,
                )
                time.sleep(0.35)
                current_top = self.driver.execute_script("return arguments[0].scrollTop;", scroll_container)
                if prev_top == current_top:
                    stable_passes += 1
            else:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
                time.sleep(0.35)

        return collected

    def stop(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None
