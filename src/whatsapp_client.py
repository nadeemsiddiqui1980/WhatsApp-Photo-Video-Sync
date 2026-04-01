from __future__ import annotations

import logging
import re
import hashlib
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
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.webdriver import WebDriver as EdgeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService


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
        allowed_download_extensions: Optional[List[str]] = None,
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
        self.allowed_download_extensions = {
            ext.lower() for ext in (allowed_download_extensions or [".jpg", ".jpeg", ".png", ".webp"])
        }
        self.driver = None
        self._seen_message_ids: set[str] = set()
        self._group_chat_opened = False

    @staticmethod
    def _kill_stale_browser_processes() -> None:
        """Kill stale Chrome/Edge processes that may be holding profile locks."""
        import subprocess
        for proc_name in ["chrome.exe", "msedge.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name, "/T"],
                    capture_output=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
        time.sleep(1)

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

        # Kill any existing Chrome/Edge processes that might be holding locks
        # on the profile directory. This prevents "crashed" startup errors.
        self._kill_stale_browser_processes()

        if self.browser == "edge":
            browser_order = ["edge", "chrome"]
        elif self.browser == "chrome":
            browser_order = ["chrome", "edge"]
        else:
            browser_order = ["chrome", "edge"]

        start_errors: list[str] = []
        started = False
        for browser_pref in browser_order:
            try:
                browser_name, browser_binary = self._find_existing_browser(browser_pref)
            except Exception as e:
                start_errors.append(f"{browser_pref}: {e}")
                continue

            try:
                self._start_driver(browser_name, browser_binary)
                started = True
                break
            except Exception as e:
                start_errors.append(f"{browser_name}: {e}")
                self.driver = None

        if not started:
            raise RuntimeError("Failed to start browser for WhatsApp Web. Attempts: " + " | ".join(start_errors))

        assert self.driver is not None
        self.driver.get("https://web.whatsapp.com/")
        self._wait_until_logged_in()
        self._open_group_chat()
        self._group_chat_opened = True

    def _start_driver(self, browser_name: str, browser_binary: str) -> None:
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
                    "profile.default_content_settings.popups": 0,
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
            chrome_options.add_argument("--hide-crash-restore-bubble")
            # Disable CORS for media fetching via JavaScript.
            # Required because WhatsApp media URLs are served from CDN domains
            # and the fetch API cannot access them from the WhatsApp Web origin.
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            try:
                self.driver = ChromeDriver(
                    service=ChromeService(ChromeDriverManager().install()),
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
            edge_options = EdgeOptions()
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
            edge_options.add_argument("--hide-crash-restore-bubble")
            # More reliable transport on Windows than remote-debugging-port.
            edge_options.add_argument("--remote-debugging-pipe")
            # Helps in hardened Windows environments where renderer attach can fail.
            edge_options.add_argument("--disable-features=RendererCodeIntegrity")
            
            if self.headless:
                edge_options.add_argument("--headless=new")
            
            try:
                self.driver = EdgeDriver(
                    options=edge_options
                )
            except Exception as e:
                raise RuntimeError(
                    f"Failed to start Microsoft Edge. Edge comes with Windows by default.\n"
                    f"Try: 1) Update Windows, 2) Restart computer, 3) Reinstall Edge\n"
                    f"Edge download: https://www.microsoft.com/edge/download\n"
                    f"Error: {str(e)}"
                )

        if not self.driver:
            raise RuntimeError("WebDriver did not initialize")

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

        if self._is_group_chat_open():
            return

        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='side']"))
        )

        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.1)

        group_literal = self._xpath_literal(self.group_name)

        def _find_group_result(timeout_seconds: int = 5):
            return self._find_first(
                [
                    f"//div[@id='pane-side']//span[@title={group_literal}]",
                    f"//div[@id='pane-side']//*[@title={group_literal}]",
                    f"//div[@id='pane-side']//span[normalize-space()={group_literal}]",
                    f"//div[@id='pane-side']//*[contains(normalize-space(.), {group_literal})]",
                    f"//span[@title={group_literal}]",
                    f"//*[@title={group_literal}]",
                ],
                timeout_seconds=timeout_seconds,
            )

        def _try_click_group_from_visible_lists(timeout_seconds: int = 12) -> bool:
            if not self.driver:
                return False
            end_time = time.time() + timeout_seconds
            group_lower = self.group_name.strip().lower()
            while time.time() < end_time:
                try:
                    clicked = self.driver.execute_script(
                        """
                        const target = (arguments[0] || '').toLowerCase();
                        const roots = [document.querySelector('#side'), document.querySelector('#pane-side'), document.body]
                          .filter(Boolean);
                        for (const root of roots) {
                          const candidates = root.querySelectorAll(
                            "[title], span, div[role='row'], div[role='listitem'], [data-testid='cell-frame-container']"
                          );
                          for (const node of candidates) {
                            const title = (node.getAttribute('title') || '').trim();
                            const text = ((node.innerText || node.textContent || '') || '').trim();
                            const hay = (title || text).toLowerCase();
                            if (!hay) continue;
                            if (hay === target || hay.includes(target)) {
                              const clickable = node.closest(
                                "[role='row'], [role='listitem'], [data-testid='cell-frame-container'], [tabindex='0'], [tabindex='-1'], div"
                              ) || node;
                              if (clickable && clickable.offsetParent !== null) {
                                clickable.scrollIntoView({ block: 'center' });
                                clickable.click();
                                return true;
                              }
                            }
                          }
                        }
                        return false;
                        """,
                        group_lower,
                    )
                    if clicked:
                        time.sleep(0.25)
                        if self._is_group_chat_open():
                            return True
                except Exception:
                    pass

                try:
                    pane = self.driver.find_element(By.XPATH, "//div[@id='pane-side']")
                    self.driver.execute_script("arguments[0].scrollTop = 0;", pane)
                except Exception:
                    pass
                time.sleep(0.3)
            return False

        try:
            direct = _find_group_result(timeout_seconds=2)
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", direct)
            direct.click()
            if self._is_group_chat_open():
                return
        except TimeoutException:
            pass

        try:
            search_box = self._find_first(
                [
                    "//div[@id='side']//div[@contenteditable='true' and @role='textbox']",
                    "//div[@id='side']//div[@contenteditable='true'][@data-tab]",
                    "//div[@id='side']//*[@contenteditable='true']",
                    "//div[@id='side']//*[@role='textbox' and @contenteditable='true']",
                    "//div[@role='textbox' and @contenteditable='true' and contains(@aria-label,'Search')]",
                    "//input[@type='text' and contains(@aria-label,'Search')]",
                    "//input[@type='text' and contains(@placeholder,'Search')]",
                    "//div[@id='side']//input[@type='text']",
                ],
                timeout_seconds=20,
            )
        except TimeoutException:
            for xp in [
                "//div[@id='side']//*[@role='button' and contains(@aria-label,'Search')]",
                "//*[@role='button' and contains(@aria-label,'Search or start new chat')]",
                "//*[@role='button' and contains(@title,'Search')]",
            ]:
                elems = self.driver.find_elements(By.XPATH, xp)
                for elem in elems:
                    if not elem.is_displayed():
                        continue
                    try:
                        elem.click()
                        time.sleep(0.2)
                        break
                    except Exception:
                        continue

            try:
                direct = _find_group_result(timeout_seconds=3)
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", direct)
                direct.click()
                if self._is_group_chat_open():
                    return
            except TimeoutException:
                pass

            try:
                search_box = self._find_first(
                    [
                        "//div[@id='side']//div[@contenteditable='true' and @role='textbox']",
                        "//div[@id='side']//div[@contenteditable='true'][@data-tab]",
                        "//div[@id='side']//*[@contenteditable='true']",
                        "//div[@id='side']//*[@role='textbox' and @contenteditable='true']",
                        "//div[@role='textbox' and @contenteditable='true' and contains(@aria-label,'Search')]",
                        "//input[@type='text' and contains(@aria-label,'Search')]",
                        "//input[@type='text' and contains(@placeholder,'Search')]",
                        "//div[@id='side']//input[@type='text']",
                    ],
                    timeout_seconds=8,
                )
            except TimeoutException:
                if self._is_group_chat_open():
                    return
                if _try_click_group_from_visible_lists(timeout_seconds=8):
                    return

                # WhatsApp variants can expose search only via keyboard shortcut (Ctrl+K).
                try:
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.CONTROL, "k")
                    time.sleep(0.25)
                    global_search = self._find_first(
                        [
                            "//input[@type='text' and contains(@aria-label,'Search')]",
                            "//input[@type='text' and contains(@placeholder,'Search')]",
                            "//*[@role='textbox' and @contenteditable='true' and contains(@aria-label,'Search')]",
                            "//*[@contenteditable='true' and @role='textbox']",
                        ],
                        timeout_seconds=6,
                    )
                    try:
                        global_search.click()
                        global_search.send_keys(Keys.CONTROL, "a")
                        global_search.send_keys(Keys.BACKSPACE)
                        global_search.send_keys(self.group_name)
                        time.sleep(0.4)
                        global_search.send_keys(Keys.ENTER)
                    except Exception:
                        pass

                    end_time = time.time() + 6
                    while time.time() < end_time:
                        if self._is_group_chat_open():
                            return
                        time.sleep(0.2)
                except Exception:
                    pass

                raise

            if self._is_group_chat_open():
                return
        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(Keys.BACKSPACE)
        search_box.send_keys(self.group_name)

        result = _find_group_result(timeout_seconds=20)
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", result)
        result.click()

        # Ensure target chat header is actually active before returning.
        end_time = time.time() + 12
        while time.time() < end_time:
            if self._is_group_chat_open():
                return
            time.sleep(0.2)
        raise TimeoutException(f"Failed to activate target chat: {self.group_name}")

    def _is_group_chat_open(self) -> bool:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        title_literal = self._xpath_literal(self.group_name)
        checks = [
            f"//header//span[@title={title_literal}]",
            f"//header//*[contains(normalize-space(.), {title_literal})]",
        ]
        for xp in checks:
            elems = self.driver.find_elements(By.XPATH, xp)
            for elem in elems:
                if elem.is_displayed():
                    return True

        # Fallback to header text match in case title/span attributes differ.
        try:
            header_text = self.driver.execute_script(
                """
                const h = document.querySelector('#main header');
                return h ? (h.innerText || h.textContent || '') : '';
                """
            )
            if isinstance(header_text, str) and self.group_name.lower() in header_text.lower():
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if "'" not in value:
            return f"'{value}'"
        if '"' not in value:
            return f'"{value}"'
        parts = value.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"

    def _message_rows_with_media(self):
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # Use JavaScript to find message IDs that contain media elements.
        # Debug output showed: SPAN:msg-video (4), SPAN:media-play (2), IMG (4), SPAN:video-pip (2)
        message_ids = self.driver.execute_script(
            """
            const main = document.querySelector('#main');
            if (!main) return [];

            // Include msg-video and media-play selectors that WhatsApp uses for video messages.
            const mediaSelectors = [
                'img',
                'video',
                '[data-testid="media-thumb"]',
                '[data-testid="media-viewer"]',
                '[data-icon="camera"]',
                '[data-icon="msg-video"]',
                '[data-icon="media-play"]',
                '[data-icon*="video"]',
                '[data-icon*="play"]',
                '[role="button"][aria-label*="video" i]',
                '[role="button"][aria-label*="photo" i]',
                '[role="button"][aria-label*="image" i]',
                '[data-opencode-video-hint="true"]',
            ];

            const mediaElements = main.querySelectorAll(mediaSelectors.join(', '));
            const idSet = new Set();

            for (const el of mediaElements) {
                // Walk up to find the message row container.
                let row = el.closest('[data-id], [data-pre-plain-text], [data-testid="msg-container"]');
                if (!row) {
                    // Fallback: walk up to find a parent with message-like attributes.
                    let parent = el.parentElement;
                    let depth = 0;
                    while (parent && depth < 10) {
                        if (parent.getAttribute('data-id') ||
                            parent.getAttribute('data-pre-plain-text') ||
                            parent.getAttribute('data-testid') === 'msg-container') {
                            row = parent;
                            break;
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                }
                if (row && row.offsetParent !== null) {
                    const id = row.getAttribute('data-id') || row.getAttribute('data-pre-plain-text') || '';
                    if (id) {
                        idSet.add(id);
                    }
                }
            }

            return Array.from(idSet);
            """
        )

        # Now use Selenium to find the actual row elements by their data-id.
        unique_rows = []
        seen_ids: set[str] = set()
        for msg_id in (message_ids or []):
            if msg_id in seen_ids:
                continue
            try:
                # Escape single quotes in the ID for XPath.
                escaped_id = msg_id.replace("'", "\\'")
                rows = self.driver.find_elements(
                    By.XPATH,
                    f"//*[@data-id='{escaped_id}' or @data-pre-plain-text='{escaped_id}']",
                )
                for row in rows:
                    if row.is_displayed() and row.id not in seen_ids:
                        unique_rows.append(row)
                        seen_ids.add(row.id)
                        break
            except Exception:
                pass
            seen_ids.add(msg_id)

        return unique_rows[-self.message_scan_limit :]

    def _row_media_buttons(self, row):
        selectors = [
            ".//div[@role='button' and (descendant::*[name()='img'] or descendant::*[name()='video'])]",
            ".//*[@data-testid='media-thumb']",
            ".//*[@data-testid='media-viewer']",
            ".//span[contains(@data-icon,'play')]/ancestor::*[@role='button'][1]",
            ".//span[@data-icon='camera']/ancestor::*[@role='button'][1]",
            ".//span[contains(@data-icon,'video')]/ancestor::*[@role='button'][1]",
            ".//*[@role='button' and @aria-label and contains(translate(@aria-label,'VIDEOPHOTOIMAGE','videophotoimage'),'video')]",
            ".//*[@role='button' and @aria-label and contains(translate(@aria-label,'VIDEOPHOTOIMAGE','videophotoimage'),'photo')]",
            ".//*[@role='button' and @aria-label and contains(translate(@aria-label,'VIDEOPHOTOIMAGE','videophotoimage'),'image')]",
            ".//*[name()='img' or name()='video']",
        ]
        media_buttons = []
        seen_ids: set[str] = set()
        for xp in selectors:
            found = row.find_elements(By.XPATH, xp)
            if found:
                for elem in found:
                    try:
                        elem_id = elem.id
                    except Exception:
                        elem_id = ""
                    if elem_id and elem_id in seen_ids:
                        continue
                    if elem_id:
                        seen_ids.add(elem_id)
                    media_buttons.append(elem)
        media_buttons = [elem for elem in media_buttons if elem.is_displayed()]
        return media_buttons

    def _try_open_any_media_preview(self, row) -> bool:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        fallback_selectors = [
            ".//*[@data-testid='media-thumb']",
            ".//*[@data-testid='media-viewer']",
            ".//*[@role='button' and (@aria-label or @title)]",
            ".//*[name()='img']/ancestor::*[@role='button'][1]",
            ".//*[name()='video']/ancestor::*[@role='button'][1]",
            ".//*[name()='img' or name()='video']",
        ]

        for xp in fallback_selectors:
            for elem in row.find_elements(By.XPATH, xp):
                if not elem.is_displayed():
                    continue
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                    time.sleep(0.1)
                    try:
                        elem.click()
                    except (ElementNotInteractableException, ElementClickInterceptedException):
                        self.driver.execute_script("arguments[0].click();", elem)
                    return True
                except Exception:
                    continue

        return False

    def _close_media_preview(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        body = self.driver.find_element(By.TAG_NAME, "body")
        # Escape is the most reliable close action on WhatsApp Web media viewer.
        for _ in range(3):
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.15)

        # Fallback close/back controls across UI variants.
        for xp in [
            "//span[@data-icon='x-viewer']/ancestor::button[1]",
            "//button[@aria-label='Close']",
            "//button[contains(@aria-label,'lose')]",
            "//span[@data-icon='back']/ancestor::button[1]",
            "//button[contains(@aria-label,'Back')]",
        ]:
            elems = self.driver.find_elements(By.XPATH, xp)
            for elem in elems:
                if not elem.is_displayed():
                    continue
                try:
                    elem.click()
                    time.sleep(0.15)
                except Exception:
                    continue

    def _message_scroll_container(self):
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # Pick the best scrollable conversation container under #main that actually owns message rows.
        container = self.driver.execute_script(
            """
            const root = document.querySelector('#main');
            if (!root) return null;

            const selectors = [
                "div[data-testid='conversation-panel-messages']",
                "div[aria-label='Message list']",
                "div.copyable-area"
            ];

            let seed = null;
            for (const sel of selectors) {
                const found = root.querySelector(sel);
                if (found) {
                    seed = found;
                    break;
                }
            }
            if (!seed) seed = root;

            const candidates = [seed, ...seed.querySelectorAll('*')];
            let best = null;
            let bestScore = -1;

            for (const el of candidates) {
                const st = getComputedStyle(el);
                const overflowScrollable = st.overflowY === 'auto' || st.overflowY === 'scroll';
                if (!overflowScrollable) continue;
                if (el.scrollHeight <= el.clientHeight + 20) continue;

                // Prefer containers that include real message rows.
                const hasRows = !!el.querySelector('[data-id]');
                const score = (el.scrollHeight - el.clientHeight) + (hasRows ? 100000 : 0);
                if (score > bestScore) {
                    best = el;
                    bestScore = score;
                }
            }

            return best;
            """
        )
        return container

    def _jump_to_latest_messages(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # Repeatedly jump to bottom because WhatsApp virtualized DOM can replace scroll nodes.
        for _ in range(3):
            container = self._message_scroll_container()
            if container:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
                time.sleep(0.2)
                try:
                    at_bottom = self.driver.execute_script(
                        "return (arguments[0].scrollHeight - arguments[0].clientHeight - arguments[0].scrollTop) <= 4;",
                        container,
                    )
                    if at_bottom:
                        break
                except StaleElementReferenceException:
                    time.sleep(0.1)
            else:
                # Fallback if container lookup fails.
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.END)
                time.sleep(0.2)

    def _scroll_chat_to_load_all_media(self) -> None:
        """Scroll through the entire chat to force lazy-loaded video thumbnails into the DOM.

        WhatsApp Web lazy-loads media thumbnails. Videos outside the viewport do not have
        <video> elements in the DOM, so XPath-based detection cannot find them. This method
        scrolls upward through the chat in viewport-sized steps, waits for content to render,
        then scrolls back to the bottom.
        """
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        container = self._message_scroll_container()
        if not container:
            return

        # Get current scroll position (should be at bottom).
        try:
            current_scroll = self.driver.execute_script("return arguments[0].scrollTop;", container)
            scroll_height = self.driver.execute_script("return arguments[0].scrollHeight;", container)
            client_height = self.driver.execute_script("return arguments[0].clientHeight;", container)
        except StaleElementReferenceException:
            return

        if scroll_height <= client_height:
            return

        logging.info("Scrolling chat to load all media thumbnails into DOM")
        step = max(1, client_height // 2)
        max_steps = 200
        for i in range(max_steps):
            try:
                current_scroll = self.driver.execute_script("return arguments[0].scrollTop;", container)
                if current_scroll <= 0:
                    break
                self.driver.execute_script(
                    "arguments[0].scrollTop = Math.max(0, arguments[0].scrollTop - arguments[1]);",
                    container, step,
                )
                time.sleep(0.3)
            except StaleElementReferenceException:
                container = self._message_scroll_container()
                if not container:
                    break
                time.sleep(0.2)

        # Scroll back to bottom.
        try:
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            time.sleep(0.3)
        except StaleElementReferenceException:
            pass

        logging.info("Chat scroll complete, ready for media scan")

    def _try_download_video_from_row(self, row, before_files: set[Path]) -> Optional[Path]:
        """Fallback: try to download video by finding download button directly in the message row.

        For videos that can't play in the browser (codec unsupported), WhatsApp Web may show
        a download button directly in the row instead of a playable preview. This method
        looks for that button and clicks it.
        """
        if not self.driver:
            return None

        # Look for download buttons directly in the message row.
        download_selectors = [
            ".//span[@data-icon='download']/ancestor::*[@role='button'][1]",
            ".//span[contains(@data-icon,'download')]/ancestor::*[@role='button'][1]",
            ".//*[@aria-label and contains(translate(@aria-label,'DOWNLOAD','download'),'download')]",
            ".//*[@title and contains(translate(@title,'DOWNLOAD','download'),'download')]",
        ]
        for sel in download_selectors:
            try:
                btns = row.find_elements(By.XPATH, sel)
                for btn in btns:
                    if btn.is_displayed():
                        logging.info("Found direct download button in row, clicking")
                        try:
                            btn.click()
                        except (ElementNotInteractableException, ElementClickInterceptedException):
                            self.driver.execute_script("arguments[0].click();", btn)
                        return self._wait_for_download(before_files)
            except Exception:
                continue

        # If no download button, try to find video source and save via JavaScript.
        try:
            video_info = self.driver.execute_script(
                """
                const row = arguments[0];
                const videos = row.querySelectorAll('video');
                const sources = [];
                for (const v of videos) {
                    if (v.src) sources.push(v.src);
                    if (v.currentSrc) sources.push(v.currentSrc);
                    for (const s of v.querySelectorAll('source')) {
                        if (s.src) sources.push(s.src);
                    }
                }
                return sources;
                """,
                row,
            )
            if video_info:
                logging.info("Found video sources in row: %s", [s[:60] for s in video_info])
        except Exception:
            pass

        return None

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
        allowed_exts = self.allowed_download_extensions

        while time.time() < end_time:
            after_files = self._snapshot_temp_files()
            new_files = [p for p in after_files - before_files if p.exists()]
            media_files = [p for p in new_files if p.suffix.lower() in allowed_exts]

            if media_files:
                media_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return media_files[0]

            time.sleep(0.5)

        raise TimeoutException("Timed out waiting for WhatsApp media download")

    def _click_download(self) -> None:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # Detect if we're viewing a video or photo in the media viewer.
        # WhatsApp shows video thumbnails as <img> elements even in the viewer.
        # We need to distinguish between actual photos and video thumbnails.
        media_info = self.driver.execute_script(
            """
            const preview = document.querySelector('[data-testid="media-viewer"]') ||
                            document.querySelector('[class*="media-viewer"]') ||
                            document.querySelector('div[tabindex="-1"]');
            if (!preview) return {error: 'no preview'};

            const video = preview.querySelector('video');
            const img = preview.querySelector('img');

            // Check for video-specific indicators in the viewer.
            const playBtn = preview.querySelector('[data-icon="play"]') ||
                           preview.querySelector('[data-icon="video"]') ||
                           preview.querySelector('[aria-label*="Play"]') ||
                           preview.querySelector('[title*="Play"]');

            // Check if there's a download button (videos often show this directly).
            const downloadBtn = preview.querySelector('[data-icon="download"]') ||
                               preview.querySelector('[aria-label*="Download"]') ||
                               preview.querySelector('[title*="Download"]');

            const result = {
                hasVideo: !!video,
                hasImg: !!img,
                hasPlayIcon: !!playBtn,
                hasDownloadBtn: !!downloadBtn,
            };

            if (video) {
                result.src = video.src || video.currentSrc || '';
                result.type = 'video';
            } else if (img) {
                result.src = img.src || img.currentSrc || '';
                result.type = 'image';
            }

            return result;
            """
        )

        is_video = False
        if media_info and isinstance(media_info, dict):
            is_video = media_info.get("hasVideo") or media_info.get("hasPlayIcon")
            logging.info("Media viewer info: type=%s hasVideo=%s hasPlayIcon=%s hasDownloadBtn=%s src=%s",
                        media_info.get("type", "unknown"),
                        media_info.get("hasVideo"),
                        media_info.get("hasPlayIcon"),
                        media_info.get("hasDownloadBtn"),
                        (media_info.get("src", "") or "")[:80])

        # For videos: click play button first to load the actual video, then download.
        if is_video:
            try:
                # Click the play button to start video playback.
                play_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//span[@data-icon='play']/ancestor::button[1] | //button[@aria-label='Play'] | //button[contains(@aria-label,'lay')]",
                )
                for btn in play_buttons:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.2)
                        try:
                            btn.click()
                        except (ElementNotInteractableException, ElementClickInterceptedException):
                            self.driver.execute_script("arguments[0].click();", btn)
                        logging.info("Clicked play button for video")
                        break

                # Wait for video to load and check multiple times.
                video_loaded = False
                for wait_attempt in range(5):
                    time.sleep(2)
                    video_check = self.driver.execute_script(
                        """
                        const preview = document.querySelector('[data-testid="media-viewer"]') ||
                                        document.querySelector('[class*="media-viewer"]') ||
                                        document.querySelector('div[tabindex="-1"]');
                        if (!preview) return {error: 'no preview'};
                        const video = preview.querySelector('video');
                        if (!video) return {error: 'no video element'};
                        const src = video.src || video.currentSrc;
                        if (!src) return {error: 'no video src'};
                        return {ok: true, src: src};
                        """
                    )
                    if video_check and isinstance(video_check, dict) and video_check.get("ok"):
                        video_loaded = True
                        video_src = video_check["src"]
                        logging.info("Video loaded after %d attempts: %s", wait_attempt + 1, video_src[:80])

                        # Download the video.
                        if video_src.startswith("blob:"):
                            js_result = self.driver.execute_async_script(
                                """
                                const callback = arguments[arguments.length - 1];
                                const src = arguments[0];
                                fetch(src)
                                    .then(resp => resp.blob())
                                    .then(blob => {
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'whatsapp_video.mp4';
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                        callback({ok: true, method: 'blob_video_download'});
                                    })
                                    .catch(e => callback({error: 'blob video fetch: ' + e.message}));
                                """,
                                video_src,
                            )
                        elif video_src.startswith("https://"):
                            js_result = self.driver.execute_async_script(
                                """
                                const callback = arguments[arguments.length - 1];
                                const src = arguments[0];
                                fetch(src)
                                    .then(resp => {
                                        if (!resp.ok) throw new Error('HTTP ' + resp.status);
                                        return resp.blob();
                                    })
                                    .then(blob => {
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.href = url;
                                        a.download = 'whatsapp_video.mp4';
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                        callback({ok: true, method: 'https_video_download'});
                                    })
                                    .catch(e => callback({error: 'https video fetch: ' + e.message}));
                                """,
                                video_src,
                            )
                        else:
                            js_result = {"error": f"unknown video src: {video_src[:80]}"}

                        if js_result and isinstance(js_result, dict) and js_result.get("ok"):
                            logging.info("Triggered video download via JS method: %s", js_result.get("method", "unknown"))
                            return
                        if js_result:
                            logging.warning("Video JS download failed: %s", js_result)
                        break

                if not video_loaded:
                    logging.warning("Video did not load after play click, trying download button fallback")
                    # Fallback: try clicking download button directly.
                    download_selectors = [
                        "//span[@data-icon='download']/ancestor::button[1]",
                        "//span[@data-icon='download']/ancestor::*[@role='button'][1]",
                        "//button[@aria-label='Download']",
                        "//button[contains(@aria-label,'ownload')]",
                    ]
                    for selector in download_selectors:
                        try:
                            btns = self.driver.find_elements(By.XPATH, selector)
                            for btn in btns:
                                if btn.is_displayed():
                                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                                    time.sleep(0.2)
                                    try:
                                        btn.click()
                                    except (ElementNotInteractableException, ElementClickInterceptedException):
                                        self.driver.execute_script("arguments[0].click();", btn)
                                    logging.info("Clicked video download button via selector: %s", selector)
                                    return
                        except Exception:
                            continue
            except Exception as video_exc:
                logging.warning("Video download attempt failed: %s", video_exc)

        # Strategy 2: Use JavaScript fetch+blob download for photos and videos.
        # For photos: fetch the image URL and download as blob.
        # For videos: fetch the video URL and download as blob.
        if media_info and isinstance(media_info, dict) and media_info.get("src"):
            src = media_info["src"]
            media_type = media_info.get("type", "image")

            if src.startswith("blob:"):
                # Blob URLs are same-origin, fetch works directly.
                js_result = self.driver.execute_async_script(
                    """
                    const callback = arguments[arguments.length - 1];
                    const src = arguments[0];
                    fetch(src)
                        .then(resp => resp.blob())
                        .then(blob => {
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'whatsapp_media';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                            callback({ok: true, method: 'blob_download'});
                        })
                        .catch(e => callback({error: 'blob fetch: ' + e.message}));
                    """,
                    src,
                )
                if js_result and isinstance(js_result, dict) and js_result.get("ok"):
                    logging.info("Triggered download via JS blob method: %s", js_result.get("method", "unknown"))
                    return
                if js_result:
                    logging.warning("JS blob download failed: %s", js_result)

            elif src.startswith("https://"):
                # For HTTPS URLs, fetch via page context and trigger native download.
                # This bypasses CORS because fetch runs in WhatsApp Web's origin.
                js_result = self.driver.execute_async_script(
                    """
                    const callback = arguments[arguments.length - 1];
                    const src = arguments[0];
                    fetch(src)
                        .then(resp => {
                            if (!resp.ok) throw new Error('HTTP ' + resp.status);
                            return resp.blob();
                        })
                        .then(blob => {
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'whatsapp_media';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                            callback({ok: true, method: 'https_blob_download'});
                        })
                        .catch(e => callback({error: 'fetch+blob: ' + e.message}));
                    """,
                    src,
                )
                if js_result and isinstance(js_result, dict) and js_result.get("ok"):
                    logging.info("Triggered download via JS blob method: %s", js_result.get("method", "unknown"))
                    return
                if js_result:
                    logging.warning("JS blob download failed: %s", js_result)

        # Strategy 3: Fallback - try any download button in the viewer.
        download_selectors = [
            "//span[@data-icon='download']/ancestor::button[1]",
            "//span[@data-icon='download']/ancestor::*[@role='button'][1]",
            "//button[@aria-label='Download']",
            "//button[contains(@aria-label,'ownload')]",
            "//button[contains(@title,'ownload')]",
            "//*[@role='button' and contains(@aria-label,'ownload')]",
            "//span[@data-icon='download']",
        ]
        for selector in download_selectors:
            try:
                btns = self.driver.find_elements(By.XPATH, selector)
                for btn in btns:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.2)
                        try:
                            btn.click()
                        except (ElementNotInteractableException, ElementClickInterceptedException):
                            self.driver.execute_script("arguments[0].click();", btn)
                        logging.info("Clicked download button via selector: %s", selector)
                        return
            except Exception:
                continue

        logging.warning("All download strategies failed for media item")

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

    @staticmethod
    def _fallback_message_id(msg_meta: Optional[str], row_text: str) -> str:
        # Some WhatsApp rows can momentarily miss data-id while virtualized;
        # use stable content-derived fallback id so they still participate in dedup.
        base = f"{msg_meta or ''}|{row_text[:200].strip()}"
        return "fallback:" + hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()

    def fetch_new_media(self) -> List[DownloadedMedia]:
        if not self.driver:
            raise RuntimeError("WhatsApp browser not started")

        # Re-open target chat when possible, but do not fail the whole cycle if side/search UI is hidden.
        if not self._is_group_chat_open():
            try:
                self._open_group_chat()
                self._group_chat_opened = True
            except TimeoutException:
                # Recovery path: close overlays and continue on current chat context.
                try:
                    self._close_media_preview()
                except Exception:
                    pass
        self._jump_to_latest_messages()
        # Scroll through chat to load lazy-loaded video thumbnails into the DOM.
        self._scroll_chat_to_load_all_media()
        collected: List[DownloadedMedia] = []

        # WhatsApp virtualizes chat DOM. Scan multiple pages upward so older media rows are seen.
        stable_passes = 0
        max_passes = 30
        for pass_num in range(max_passes):
            rows = self._message_rows_with_media()
            newly_seen_in_pass = 0

            if pass_num == 0:
                logging.info("Scan pass 0: found %d media rows, %d already seen", len(rows), sum(1 for r in rows if (r.get_attribute("data-id") or "") in self._seen_message_ids))

            # Iterate by index so we can re-query rows on each retry when DOM re-renders.
            row_count = len(rows)
            for reverse_index in range(row_count):
                row_index = row_count - 1 - reverse_index
                row_retry_count = 0
                max_row_retries = 2

                while row_retry_count <= max_row_retries:
                    try:
                        current_rows = self._message_rows_with_media()
                        if row_index >= len(current_rows):
                            break

                        row = current_rows[row_index]
                        msg_meta = row.get_attribute("data-pre-plain-text")
                        message_id = row.get_attribute("data-id") or self._fallback_message_id(
                            msg_meta,
                            row.text,
                        )
                        if message_id in self._seen_message_ids:
                            break

                        msg_time, sender = self._parse_pre_plain_text(msg_meta)

                        # A single message can contain multiple media tiles.
                        media_buttons = self._row_media_buttons(row)
                        if not media_buttons:
                            # Try a generic open path for album-like rows where tile selectors are delayed/variant.
                            logging.info("No media buttons for msg %s, trying fallback preview", message_id[:30])
                            before = self._snapshot_temp_files()
                            downloaded_file: Optional[Path] = None
                            preview_opened = False
                            try:
                                preview_opened = self._try_open_any_media_preview(row)
                                if preview_opened:
                                    self._click_download()
                                    downloaded_file = self._wait_for_download(before)
                            except TimeoutException:
                                logging.warning(
                                    "Media download timeout: msg_id=%s preview=%s",
                                    message_id[:40], preview_opened,
                                )
                                if preview_opened:
                                    try:
                                        self._close_media_preview()
                                    except Exception:
                                        pass
                                downloaded_file = self._try_download_video_from_row(row, before)
                            except Exception as dl_exc:
                                logging.warning(
                                    "Media download error: msg_id=%s err=%s",
                                    message_id[:40], dl_exc,
                                )
                            finally:
                                if preview_opened:
                                    self._close_media_preview()

                            if downloaded_file is not None:
                                downloaded_any = True
                                collected.append(
                                    DownloadedMedia(
                                        local_temp_path=downloaded_file,
                                        message_time=msg_time,
                                        sender=sender,
                                        message_id=message_id,
                                    )
                                )
                            else:
                                logging.warning("Fallback download failed for msg %s, not marking seen", message_id[:30])
                                break
                            # Completed fallback handling for this row.
                            if downloaded_any:
                                self._seen_message_ids.add(message_id)
                                newly_seen_in_pass += 1
                            break

                        # Process media with retry for stale elements (WhatsApp's virtualized DOM invalidates refs)
                        downloaded_any = False
                        for media_index in range(len(media_buttons)):
                            before = self._snapshot_temp_files()
                            preview_opened = False
                            downloaded_file: Optional[Path] = None
                            stale_retry_count = 0
                            max_stale_retries = 2

                            while stale_retry_count <= max_stale_retries:
                                try:
                                    # Re-query media buttons each iteration to avoid stale refs
                                    # (DOM may have changed due to scrolling or re-renders)
                                    current_media = self._row_media_buttons(row)

                                    if media_index >= len(current_media):
                                        # Media list changed; skip this iteration
                                        break

                                    photo_button = current_media[media_index]

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
                                    logging.warning(
                                        "Media button download timeout: msg_id=%s media_idx=%d preview=%s",
                                        message_id[:40], media_index, preview_opened,
                                    )
                                    break
                                except Exception as media_exc:
                                    logging.warning(
                                        "Media button error: msg_id=%s media_idx=%d err=%s",
                                        message_id[:40], media_index, media_exc,
                                    )
                                    break
                                finally:
                                    if preview_opened:
                                        self._close_media_preview()

                            if downloaded_file is not None:
                                downloaded_any = True
                                collected.append(
                                    DownloadedMedia(
                                        local_temp_path=downloaded_file,
                                        message_time=msg_time,
                                        sender=sender,
                                        message_id=message_id,
                                    )
                                )

                        # Mark as seen only after at least one successful download.
                        # This prevents permanently skipping new rows when a transient preview/download error occurs.
                        if downloaded_any:
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
            try:
                scroll_container = self._message_scroll_container()
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
            except StaleElementReferenceException:
                # Virtualized message container can be replaced by WhatsApp between passes.
                scroll_container = self._message_scroll_container()
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_UP)
                time.sleep(0.35)

        return collected

    def fetch_new_images(self) -> List[DownloadedMedia]:
        # Backward-compatible shim for older callsites.
        return self.fetch_new_media()

    def stop(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None
