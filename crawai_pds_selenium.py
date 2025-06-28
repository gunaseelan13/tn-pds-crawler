"""
Script to navigate the Tamil Nadu PDS website using Selenium
since it's a complex Ajax-based JSF website that requires proper session handling
"""
import json
import os
import time
import argparse
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

def save_data_to_json(data, output_file="pds_data.json"):
    """Save extracted data to a JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Data saved to {output_file}")

def find_shop_by_id(driver, wait, shop_id, known_district=None, known_taluk=None):
    """
    Find a shop by its ID by searching through districts and taluks
    If known_district and known_taluk are provided, will search only in that location
    Returns a tuple of (found, district, taluk, shop_details) where found is a boolean
    """
    print(f"Searching for shop with ID: {shop_id}")
    
    # Navigate to the main page and get districts
    navigate_to_main_page(driver, wait)
    districts = navigate_to_pds_reports_and_get_districts(driver, wait)
    if not districts:
        print("Failed to get districts list")
        return False, None, None, None
        
    # If we know the district, only search there
    if known_district and known_district in districts:
        districts = [known_district]
    
    # Search through each district
    for district in districts:
        print(f"Searching in district: {district}")
        taluks = navigate_to_district_and_get_taluks(driver, wait, district)
        if not taluks:
            print(f"Failed to get taluks for district {district}, skipping")
            navigate_back_using_breadcrumbs(driver, wait, 'state')
            continue
            
        # If we know the taluk, only search there
        if known_taluk and known_taluk in taluks:
            taluks = [known_taluk]
        
        # Search through each taluk
        for taluk in taluks:
            print(f"Searching in taluk: {taluk}")
            shops = navigate_to_taluk_and_get_shops(driver, wait, taluk)
            if not shops:
                print(f"Failed to get shops for taluk {taluk}, skipping")
                navigate_back_using_breadcrumbs(driver, wait, 'district')
                continue
            
            # Check if shop ID exists in this taluk
            shop_found = False
            for shop in shops:
                shop_id_in_list = shop.get('SHOP CODE', '')
                if shop_id_in_list == shop_id:
                    shop_found = True
                    print(f"Found shop {shop_id} in district {district}, taluk {taluk}")
                    
                    # Store shop name from the search results for fallback
                    shop_name = shop.get('SHOP NAME', '')
                    print(f"Shop name from search results: {shop_name}")
                    
                    # Create output directory
                    output_dir = f"pds_data/{district}/{taluk}"
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Navigate to the shop details page
                    shop_details = navigate_to_shop_and_get_details(driver, wait, shop_id, district, taluk, output_dir, shop_name)
                    
                    # If shop details were found but name is missing, add it from search results
                    if isinstance(shop_details, dict) and not shop_details.get('name') and shop_name:
                        shop_details['name'] = shop_name
                        
                    # If shop details weren't found, create a basic record from the shop list
                    if not shop_details:
                        shop_details = {
                            "name": shop.get('SHOP NAME', ''),
                            "incharge": shop.get('SHOP INCHARGE', ''),
                            "cards": shop.get('TOTAL NUMBER OF CARDS', ''),
                            "beneficiaries": shop.get('TOTAL NUMBER OF BENEFICIARIES', ''),
                            "status": "Unknown"
                        }
                    
                    # Navigate back to state level
                    navigate_back_using_breadcrumbs(driver, wait, 'taluk')
                    navigate_back_using_breadcrumbs(driver, wait, 'district')
                    navigate_back_using_breadcrumbs(driver, wait, 'state')
                    
                    return True, district, taluk, shop_details
            
            # If shop not found in this taluk, go back to district level
            if not shop_found:
                navigate_back_using_breadcrumbs(driver, wait, 'district')
        
        # If shop not found in this district, go back to state level
        navigate_back_using_breadcrumbs(driver, wait, 'state')
    
    print(f"Shop {shop_id} not found in any district/taluk")
    return False, None, None, None

def process_shop_list_json(shop_list_file, output_json, headless=True):
    """
    Process a list of shop IDs from a JSON file and check their status
    """
    print(f"Processing shop list from {shop_list_file}")
    start_time = time.time()
    
    # Read the input JSON file
    try:
        with open(shop_list_file, 'r') as f:
            input_data = json.load(f)
            shop_list = input_data.get('shops', [])
            options = input_data.get('options', {})
            
            # Check if the shop list is in the new format (list of objects) or old format (list of strings)
            if shop_list and isinstance(shop_list[0], dict):
                print(f"Using new JSON format with district and taluk information")
            else:
                # Convert old format to new format
                print(f"Converting old JSON format to new format")
                shop_list = [{"id": shop_id} for shop_id in shop_list]
    except Exception as e:
        print(f"Error reading input JSON file: {str(e)}")
        return False
    
    # Get options
    include_details = options.get('include_details', True)
    headless = options.get('headless', headless)
    
    # Initialize results
    results = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_shops_checked": len(shop_list),
        "shops_found": 0,
        "shops_not_found": 0,
        "online_shops": 0,
        "offline_shops": 0,
        "results": {}
    }
    
    # Initialize webdriver
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    
    # Use Chrome directly without webdriver-manager in Docker environment
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)
    
    try:
        # Navigate to the main page
        navigate_to_main_page(driver, wait)
        
        # Process each shop in the list
        for shop_item in shop_list:
            # Extract shop information
            shop_id = shop_item.get('id')
            known_district = shop_item.get('district')
            known_taluk = shop_item.get('taluk')
            
            if known_district and known_taluk:
                print(f"Using provided district '{known_district}' and taluk '{known_taluk}' for shop {shop_id}")
            elif known_district:
                print(f"Using provided district '{known_district}' for shop {shop_id}")
            
            # Find the shop using available information
            found, district, taluk, shop_details = find_shop_by_id(driver, wait, shop_id, known_district, known_taluk)
            
            if found and shop_details:
                results["shops_found"] += 1
                results["results"][shop_id] = {
                    "found": True,
                    "district": district,
                    "taluk": taluk
                }
                
                # Add shop details if available
                if include_details and isinstance(shop_details, dict):
                    for key, value in shop_details.items():
                        results["results"][shop_id][key] = value
                
                # Update status counts
                if isinstance(shop_details, dict):
                    status = shop_details.get('status', '').lower()
                    if status == 'online':
                        results["online_shops"] += 1
                    elif status == 'offline':
                        results["offline_shops"] += 1
            else:
                results["shops_not_found"] += 1
                results["results"][shop_id] = {
                    "found": False,
                    "error": "Shop ID not found in the system"
                }
    except Exception as e:
        print(f"Error during crawling: {str(e)}")
    finally:
        # Calculate execution time
        execution_time = time.time() - start_time
        results["execution_time_seconds"] = round(execution_time, 2)
        
        # Save results to JSON file
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to {output_json}")
        print(f"Found {results['shops_found']} shops out of {results['total_shops_checked']}")
        print(f"Online shops: {results['online_shops']}, Offline shops: {results['offline_shops']}")
        
        # Close the browser
        driver.quit()
    
    return True

def find_element_with_retry(driver, wait, selectors, element_name="element"):
    """Try multiple selectors to find an element with retry logic"""
    for selector in selectors:
        try:
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            print(f"Found {element_name} with selector: {selector}")
            return element
        except:
            continue
    return None

def wait_for_ajax(driver, wait):
    """Wait for AJAX calls to complete"""
    try:
        wait.until(lambda d: d.execute_script('return jQuery.active == 0'))
        time.sleep(1)  # Additional small delay
    except:
        time.sleep(2)  # Fallback delay if jQuery is not available

def switch_to_english(driver, wait):
    """Switch the website language to English"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"\nAttempt {attempt + 1} to switch language")
            
            # Wait for page to be fully loaded
            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            print("Page loaded")
            
            # Check if already in English
            body_class = driver.find_element(By.TAG_NAME, 'body').get_attribute('class')
            if 'lang-english' in body_class:
                print("Already in English mode")
                return True
                
            # Wait for the masterForm to be present
            try:
                master_form = wait.until(EC.presence_of_element_located((By.ID, 'masterForm')))
                print("Found masterForm")
                
                # Find the language menu table
                lang_table = wait.until(EC.presence_of_element_located(
                    (By.ID, 'masterForm:languageSelectMenu')
                ))
                print("Found language menu")
                
                # Find all radio buttons in the language menu
                radio_buttons = lang_table.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
                print(f"Found {len(radio_buttons)} language options")
                
                # Find and click the English radio button
                for radio in radio_buttons:
                    if radio.get_attribute('value') == 'en':
                        print("Found English radio button")
                        if not radio.is_selected():
                            print("Clicking English option...")
                            try:
                                radio.click()
                            except:
                                print("Direct click failed, trying JavaScript")
                                driver.execute_script("""
                                    var radio = arguments[0];
                                    radio.click();
                                    radio.form.submit();
                                """, radio)
                            
                            # Wait for page reload
                            time.sleep(3)
                            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                            print("Page reloaded")
                            
                            # Verify language switch
                            body_class = driver.find_element(By.TAG_NAME, 'body').get_attribute('class')
                            if 'lang-english' in body_class:
                                print("Successfully switched to English")
                                return True
                        else:
                            print("English already selected")
                            return True
                
                print("Could not find English radio button")
            except:
                # Alternative approach - look for language links
                print("Could not find masterForm, trying alternative approach")
                
                # Try finding all links and look for one that might be a language switcher
                all_links = driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    try:
                        href = link.get_attribute("href")
                        text = link.text.strip()
                        if (href and "locale=en" in href) or (text and "English" in text):
                            driver.execute_script("arguments[0].click();", link)
                            print(f"Clicked language switcher: {text} with href: {href}")
                            time.sleep(2)  # Wait for language change
                            return True
                    except:
                        continue
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                print("\nDebug information:")
                try:
                    print("Current URL:", driver.current_url)
                    print("Page title:", driver.title)
                    forms = driver.find_elements(By.TAG_NAME, 'form')
                    print(f"Found {len(forms)} forms:")
                    for form in forms:
                        print(f"Form ID: {form.get_attribute('id')}, Name: {form.get_attribute('name')}")
                except Exception as debug_e:
                    print(f"Error getting debug info: {str(debug_e)}")
            else:
                print("Retrying...")
                time.sleep(2)
                continue
                
    return False

def navigate_to_district_table(driver, wait):
    """Navigate to the district table on the PDS website"""
    try:
        # Go to homepage
        print("Loading main page...")
        driver.get("https://www.tnpds.gov.in/")
        
        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Main page loaded")
        
        # Switch to English first
        if not switch_to_english(driver, wait):
            print("Warning: Failed to switch to English, continuing anyway")
        
        # Take screenshot for debugging
        driver.save_screenshot("main_page.png")
        print("Screenshot saved as main_page.png")
        
        # Find and click PDS Reports link directly
        print("Looking for PDS Reports link...")
        links = driver.find_elements(By.TAG_NAME, 'a')
        pds_reports_link = None
        for link in links:
            if link.text == 'PDS Reports':
                pds_reports_link = link
                print("Found PDS Reports link")
                break
                
        if pds_reports_link:
            try:
                pds_reports_link.click()
                print("Clicked PDS Reports link")
                
                # Wait for page to load
                time.sleep(2)
                wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                print("Successfully loaded PDS Reports page")
                
                # Now look for the district table
                print("Looking for district table...")
                try:
                    # Wait for the district table to be present
                    table = wait.until(EC.presence_of_element_located(
                        (By.ID, 'StateLevelDetailsForm:StateLevelDetailsTable')
                    ))
                    print("Found district table")
                    
                    # Take screenshot for debugging
                    driver.save_screenshot("district_table.png")
                    print("District table screenshot saved")
                    
                    return table
                except Exception as e:
                    print(f"Error finding district table: {str(e)}")
                    driver.save_screenshot("district_table_error.png")
                    return None
            except Exception as e:
                print(f"Error clicking PDS Reports link: {str(e)}")
        
        # If direct link not found, try through Reports menu
        print("PDS Reports link not found, trying through Reports menu...")
        
        # Try multiple approaches to find the Reports menu
        reports_menu_selectors = [
            'a[onclick*="masterForm:j_idt82"]',
            'a:contains("Reports")',
            'a.ui-menuitem-link:contains("Reports")',
            'li.ui-menuitem:contains("Reports") > a'
        ]
        
        reports_menu = None
        for selector in reports_menu_selectors:
            try:
                # Try CSS selector first
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    reports_menu = elements[0]
                    break
            except:
                try:
                    # Try XPath as fallback
                    if "contains" in selector:
                        xpath = selector.replace('a:contains("', '//a[contains(text(),"').replace('")', '")]')
                        xpath = xpath.replace('a.ui-menuitem-link:contains("', '//a[@class="ui-menuitem-link" and contains(text(),"')
                        xpath = xpath.replace('li.ui-menuitem:contains("', '//li[contains(@class,"ui-menuitem") and contains(.,"')
                        elements = driver.find_elements(By.XPATH, xpath)
                        if elements:
                            reports_menu = elements[0]
                            break
                except:
                    continue
        
        if not reports_menu:
            # Try to find all menu items and look for one containing "Reports"
            print("Trying to find Reports menu by text content...")
            menu_items = driver.find_elements(By.CSS_SELECTOR, "a.ui-menuitem-link, li.ui-menuitem a")
            for item in menu_items:
                if "Reports" in item.text:
                    reports_menu = item
                    print(f"Found Reports menu: {item.text}")
                    break
        
        if reports_menu:
            print("Clicking Reports menu...")
            driver.execute_script("arguments[0].click();", reports_menu)
            time.sleep(2)  # Wait for submenu to appear
        else:
            print("Reports menu not found. Listing available menu items:")
            menu_items = driver.find_elements(By.TAG_NAME, "a")
            for item in menu_items:
                try:
                    print(f"Menu item: {item.text} - onclick: {item.get_attribute('onclick')}")
                except:
                    pass
            
            # Try direct navigation to the reports page as fallback
            print("Trying direct navigation to reports page...")
            driver.get("https://www.tnpds.gov.in/pages/reports/pds-report-state.xhtml")
            time.sleep(3)
        
        # Look for FPS Reports submenu or check if we're already on the reports page
        if "pds-report-state.xhtml" not in driver.current_url:
            print("Looking for FPS Reports submenu...")
            fps_reports_selectors = [
                'a:contains("FPS Reports")',
                'li.ui-menuitem:contains("FPS Reports") > a',
                'a.ui-menuitem-link:contains("FPS")'
            ]
            
            fps_reports_menu = None
            for selector in fps_reports_selectors:
                try:
                    # Try XPath
                    if "contains" in selector:
                        xpath = selector.replace('a:contains("', '//a[contains(text(),"').replace('")', '")]')
                        xpath = xpath.replace('li.ui-menuitem:contains("', '//li[contains(@class,"ui-menuitem") and contains(.,"')
                        elements = driver.find_elements(By.XPATH, xpath)
                        if elements:
                            fps_reports_menu = elements[0]
                            break
                except:
                    continue
            
            if not fps_reports_menu:
                # Try to find all submenu items and look for one containing "FPS"
                submenu_items = driver.find_elements(By.CSS_SELECTOR, ".ui-menu-list a, .ui-submenu a")
                for item in submenu_items:
                    if "FPS" in item.text:
                        fps_reports_menu = item
                        print(f"Found FPS Reports submenu: {item.text}")
                        break
            
            if fps_reports_menu:
                print("Clicking FPS Reports submenu...")
                driver.execute_script("arguments[0].click();", fps_reports_menu)
                time.sleep(3)  # Wait for page to load
            else:
                print("FPS Reports submenu not found. Trying direct navigation...")
                driver.get("https://www.tnpds.gov.in/pages/reports/pds-report-state.xhtml")
                time.sleep(3)
        
        # Check if we're on the reports page
        try:
            form_element = wait.until(EC.presence_of_element_located((By.ID, "fpsReportForm")))
            print("Successfully navigated to FPS Reports page")
            return True
        except TimeoutException:
            print("Failed to navigate to FPS Reports page")
            driver.save_screenshot("navigation_failed.png")
            return False
    
    except Exception as e:
        print(f"Error navigating to PDS Reports: {str(e)}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("navigation_error.png")
        return False

def navigate_to_taluk_level(driver, wait):
    """Navigate to the taluk level after clicking on a district"""
    try:
        # Wait for taluk table to load
        print("\nLooking for taluk table...")
        try:
            # Save page source for analysis
            with open("after_district_click_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("Page source saved after district click")
            
            # Wait for the taluk table to be present - try multiple possible IDs
            taluk_table_selectors = [
                '[id$="TalukLevelDetailsTable"]',  # Ends with TalukLevelDetailsTable
                '[id*="Taluk"][id*="Table"]',     # Contains both 'Taluk' and 'Table'
                '.ui-datatable',                  # PrimeFaces datatable class
                'table.dataTable',                # Common datatable class
                'table:not(.ui-menu-list)'       # Any table that's not a menu
            ]
            
            taluk_table = None
            for selector in taluk_table_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Filter out small tables that might be menus or other UI elements
                        valid_tables = []
                        for table in elements:
                            try:
                                rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                                if len(rows) > 1:  # Table should have multiple rows
                                    valid_tables.append(table)
                            except:
                                continue
                        
                        if valid_tables:
                            taluk_table = valid_tables[0]
                            print(f"Found taluk table with selector: {selector}, with {len(valid_tables)} valid tables")
                            break
                except Exception as e:
                    print(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not taluk_table:
                print("Could not find taluk table")
                driver.save_screenshot("taluk_table_not_found.png")
                return False
            
            # Take screenshot of taluk table
            driver.save_screenshot("taluk_table.png")
            print("Taluk table screenshot saved")
            
            # Get all taluk rows
            rows = taluk_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            print(f"Found {len(rows)} taluk rows")
            
            # Print table structure for debugging
            print("Table structure:")
            headers = taluk_table.find_elements(By.CSS_SELECTOR, 'th')
            header_texts = [h.text for h in headers]
            print(f"Headers: {header_texts}")
            
            if len(rows) > 0:
                sample_row = rows[0]
                cells = sample_row.find_elements(By.CSS_SELECTOR, 'td')
                cell_texts = [c.text for c in cells]
                print(f"Sample row cells: {cell_texts}")
            
            # Extract taluk data
            taluks = []
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                    if cells:
                        taluk_name = cells[0].text  # First column should be taluk name
                        if taluk_name and len(taluk_name.strip()) > 0:
                            taluks.append(taluk_name)
                except Exception as e:
                    print(f"Error extracting taluk name: {str(e)}")
                    continue
            
            print(f"Extracted {len(taluks)} taluk names")
            print("Taluks:", taluks[:5], "..." if len(taluks) > 5 else "")
            
            # Save taluk data
            save_data_to_json({"taluks": taluks}, "pds_taluks.json")
            print("Taluk data saved to pds_taluks.json")
            
            # Try clicking on the first taluk
            if len(rows) > 0:
                try:
                    # Look for a clickable link in the first row
                    links = rows[0].find_elements(By.TAG_NAME, 'a')
                    if links:
                        first_taluk_link = links[0]
                        taluk_name = rows[0].text.split('\n')[0] if '\n' in rows[0].text else rows[0].text
                        print(f"Clicking on first taluk: {taluk_name}")
                        
                        # Click on taluk link
                        driver.execute_script("arguments[0].click();", first_taluk_link)
                    else:
                        # If no link, try clicking the row itself
                        print("No direct link found, trying to click the row")
                        driver.execute_script("arguments[0].click();", rows[0])
                    
                    # Wait for page update
                    time.sleep(2)
                    wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                    print("Page updated after taluk click")
                    
                    # Take screenshot after clicking taluk
                    driver.save_screenshot("after_taluk_click.png")
                    print("Screenshot saved after clicking taluk")
                    
                    # Navigate to shop level
                    navigate_to_shop_level(driver, wait)
                    
                    return True
                except Exception as e:
                    print(f"Error clicking on first taluk: {str(e)}")
                    driver.save_screenshot("taluk_click_error.png")
                    return False
            else:
                print("No taluk rows found to click")
                return False
                
        except Exception as e:
            print(f"Error finding taluk table: {str(e)}")
            driver.save_screenshot("taluk_error.png")
            return False
            
    except Exception as e:
        print(f"Error navigating to taluk level: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def navigate_to_shop_level(driver, wait):
    """Navigate to the shop level after clicking on a taluk"""
    try:
        # Wait for shop table to load
        print("\nLooking for shop table...")
        try:
            # Save page source for analysis
            with open("after_taluk_click_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("Page source saved after taluk click")
            
            # Wait for the shop table to be present - try multiple possible IDs
            shop_table_selectors = [
                '[id$="ShopLevelDetailsTable"]',  # Ends with ShopLevelDetailsTable
                '[id*="Shop"][id*="Table"]',     # Contains both 'Shop' and 'Table'
                '.ui-datatable',                 # PrimeFaces datatable class
                'table.dataTable',               # Common datatable class
                'table:not(.ui-menu-list)'      # Any table that's not a menu
            ]
            
            shop_table = None
            for selector in shop_table_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Filter out small tables that might be menus or other UI elements
                        valid_tables = []
                        for table in elements:
                            try:
                                rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                                if len(rows) > 1:  # Table should have multiple rows
                                    valid_tables.append(table)
                            except:
                                continue
                        
                        if valid_tables:
                            shop_table = valid_tables[0]
                            print(f"Found shop table with selector: {selector}, with {len(valid_tables)} valid tables")
                            break
                except Exception as e:
                    print(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not shop_table:
                print("Could not find shop table")
                driver.save_screenshot("shop_table_not_found.png")
                return False
            
            # Take screenshot of shop table
            driver.save_screenshot("shop_table.png")
            print("Shop table screenshot saved")
            
            # Get all shop rows
            rows = shop_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            print(f"Found {len(rows)} shop rows")
            
            # Print table structure for debugging
            print("Table structure:")
            headers = shop_table.find_elements(By.CSS_SELECTOR, 'th')
            header_texts = [h.text for h in headers]
            print(f"Headers: {header_texts}")
            
            if len(rows) > 0:
                sample_row = rows[0]
                cells = sample_row.find_elements(By.CSS_SELECTOR, 'td')
                cell_texts = [c.text for c in cells]
                print(f"Sample row cells: {cell_texts}")
            
            # Extract shop data
            shops = []
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                    if cells:
                        shop_data = {}
                        for i, header in enumerate(header_texts):
                            if i < len(cells):
                                shop_data[header] = cells[i].text
                        if shop_data:
                            shops.append(shop_data)
                except Exception as e:
                    print(f"Error extracting shop data: {str(e)}")
                    continue
            
            print(f"Extracted {len(shops)} shop records")
            if shops:
                print("Sample shop data:", shops[0])
            
            # Save shop data
            save_data_to_json({"shops": shops}, "pds_shops.json")
            print("Shop data saved to pds_shops.json")
            
            # Try clicking on the first shop
            if len(rows) > 0:
                try:
                    # Look for a clickable link in the first row
                    links = rows[0].find_elements(By.TAG_NAME, 'a')
                    if links:
                        first_shop_link = links[0]
                        shop_name = cells[0].text if cells else "Unknown"
                        print(f"Clicking on first shop: {shop_name}")
                        
                        # Click on shop link
                        driver.execute_script("arguments[0].click();", first_shop_link)
                        
                        # Wait for page update
                        time.sleep(2)
                        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                        print("Page updated after shop click")
                        
                        # Take screenshot after clicking shop
                        driver.save_screenshot("after_shop_click.png")
                        print("Screenshot saved after shop click")
                        
                        # Extract shop details
                        extract_shop_details(driver, wait)
                        
                        return True
                    else:
                        print("No shop links found to click")
                        return False
                except Exception as e:
                    print(f"Error clicking on first shop: {str(e)}")
                    driver.save_screenshot("shop_click_error.png")
                    return False
            else:
                print("No shop rows found to click")
                return False
                
        except Exception as e:
            print(f"Error finding shop table: {str(e)}")
            driver.save_screenshot("shop_error.png")
            return False
            
    except Exception as e:
        print(f"Error navigating to shop level: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def extract_shop_details(driver, wait):
    """Extract detailed information from a shop page"""
    try:
        print("\nExtracting shop details...")
        
        # Save page source for analysis
        with open("shop_details_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Shop details page source saved")
        
        # Extract all tables on the page
        tables = {}
        table_index = 3
        
        # Find all tables on the page
        all_tables = driver.find_elements(By.CSS_SELECTOR, 'table')
        print(f"Found {len(all_tables)} tables on the shop details page")
        
        # Process each table
        for i, table in enumerate(all_tables, 1):
            try:
                rows = table.find_elements(By.CSS_SELECTOR, 'tr')
                if not rows:
                    continue
                    
                # Extract headers
                headers = []
                header_cells = rows[0].find_elements(By.CSS_SELECTOR, 'th')
                if header_cells:
                    headers = [cell.text.strip() for cell in header_cells]
                else:
                    # Try to get headers from first row if no th elements
                    header_cells = rows[0].find_elements(By.CSS_SELECTOR, 'td')
                    headers = [cell.text.strip() for cell in header_cells]
                    
                # If no headers found, create default column names
                if not headers or all(not h for h in headers):
                    headers = [f"Column{j}" for j in range(len(header_cells))]
                
                # Check if this is a transaction table with bill numbers
                is_transaction_table = False
                bill_number_index = -1
                for idx, header in enumerate(headers):
                    if header.lower() in ['bill number', 'bill no', 'bill no.', 'transaction id']:
                        is_transaction_table = True
                        bill_number_index = idx
                        break
                
                # If this is a transaction table, mark it specially
                if is_transaction_table:
                    print(f"Found transaction table with bill numbers")
                    tables['transactions'] = []
                    
                # Extract data rows
                data = []
                for row in rows[1:]:  # Skip header row
                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                    if cells:
                        row_data = {}
                        for j, cell in enumerate(cells):
                            if j < len(headers):
                                row_data[headers[j]] = cell.text.strip()
                            else:
                                row_data[f"Column{j}"] = cell.text.strip()
                        data.append(row_data)
                        
                        # If this is a transaction row, add to transactions list
                        if is_transaction_table and bill_number_index >= 0 and j >= bill_number_index:
                            tables['transactions'].append(row_data)
                
                # Add table to results
                if data:
                    tables[f"Table{table_index}"] = data
                    table_index += 1
                    
            except Exception as e:
                print(f"Error extracting data from table {i}: {str(e)}")
                
        # Add tables to shop details
        shop_details = {}
        shop_details.update(tables)
        print(f"Successfully extracted shop details")
        print(f"Found {len(tables)} data points")
        
        # Save shop details
        save_data_to_json(shop_details, "pds_shop_details.json")
        print("Shop details saved to pds_shop_details.json")
        return True
            
    except Exception as e:
        print(f"Error extracting shop details: {str(e)}")
        driver.save_screenshot("shop_details_error.png")
        return False


def extract_form_elements(driver):
    """Extract all form elements and their options"""
    try:
        form_data = {}
        
        # Take screenshot of the form page
        driver.save_screenshot("form_page.png")
        print("Form page screenshot saved")
        
        # Save page source for analysis
        with open("form_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Form page source saved")
        
        # Find all forms on the page
        forms = driver.find_elements(By.TAG_NAME, "form")
        print(f"Found {len(forms)} forms on the page")
        for i, form in enumerate(forms):
            form_id = form.get_attribute("id")
            print(f"Form {i+1}: ID = {form_id}")
        
        # Try to find the correct form - could be fpsReportForm or something else
        form_selectors = [
            "#fpsReportForm",
            "form[id*='ReportForm']",
            "form[id*='report']",
            "form:has(select)",  # Form containing select elements
            "form"  # Any form as fallback
        ]
        
        target_form = None
        for selector in form_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    target_form = elements[0]
                    print(f"Found target form with selector: {selector}, ID: {target_form.get_attribute('id')}")
                    break
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")
                continue
        
        if not target_form:
            print("Could not find target form")
            return None
        
        # Get all select elements within the form
        form_id = target_form.get_attribute("id")
        select_elements = target_form.find_elements(By.TAG_NAME, "select")
        print(f"Found {len(select_elements)} select elements in form {form_id}")
        
        for select_elem in select_elements:
            select_id = select_elem.get_attribute("id")
            select_name = select_elem.get_attribute("name")
            print(f"Select element: ID = {select_id}, Name = {select_name}")
            
            select = Select(select_elem)
            options = []
            for opt in select.options:
                value = opt.get_attribute("value")
                text = opt.text.strip()
                if text:
                    options.append({"value": value, "text": text})
                    print(f"  - Option: {text} (value: {value})")
            
            form_data[select_id] = options
        
        # Get all buttons within the form
        buttons = target_form.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
        form_data["buttons"] = []
        print(f"Found {len(buttons)} buttons in form {form_id}")
        
        for btn in buttons:
            btn_id = btn.get_attribute("id")
            btn_name = btn.get_attribute("name")
            btn_text = btn.text or btn.get_attribute("value")
            print(f"Button: ID = {btn_id}, Name = {btn_name}, Text = {btn_text}")
            form_data["buttons"].append({"id": btn_id, "name": btn_name, "text": btn_text})
        
        print("Successfully extracted form elements")
        save_data_to_json(form_data, "pds_form_data.json")
        return form_data
    
    except Exception as e:
        print(f"Error extracting form elements: {str(e)}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("form_extraction_error.png")
        return None

def fill_form_and_submit(driver, wait, form_data):
    """Fill the form with specific values and submit it"""
    if not form_data:
        print("No form data available, cannot fill form")
        return False
    
    try:
        # Find the form first
        form_selectors = [
            "#fpsReportForm",
            "form[id*='ReportForm']",
            "form[id*='report']",
            "form:has(select)",  # Form containing select elements
            "form"  # Any form as fallback
        ]
        
        target_form = None
        for selector in form_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    target_form = elements[0]
                    print(f"Found target form with selector: {selector}, ID: {target_form.get_attribute('id')}")
                    break
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")
                continue
        
        if not target_form:
            print("Could not find target form")
            return False
            
        form_id = target_form.get_attribute("id")
        
        # Step 1: Find and select state dropdown
        print("Looking for state dropdown...")
        state_select_found = False
        
        # Try different approaches to find state dropdown
        state_selectors = [
            f"#{form_id}\\:state",  # Standard JSF naming
            "select[id*='state']",   # Any select with 'state' in ID
            "select:first-of-type"   # First select as fallback
        ]
        
        for selector in state_selectors:
            try:
                state_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if state_elements:
                    state_select = Select(state_elements[0])
                    print(f"Found state dropdown with selector: {selector}")
                    state_select_found = True
                    break
            except Exception as e:
                print(f"Error with state selector {selector}: {str(e)}")
                continue
        
        if not state_select_found:
            # Try to find all select elements and look for one that might be state
            select_elements = target_form.find_elements(By.TAG_NAME, "select")
            for select_elem in select_elements:
                try:
                    select = Select(select_elem)
                    options_text = [opt.text for opt in select.options]
                    options_str = ", ".join(options_text[:5]) + ("..." if len(options_text) > 5 else "")
                    print(f"Select element options: {options_str}")
                    
                    # Check if this might be the state dropdown
                    if any("TAMIL" in opt.text.upper() for opt in select.options):
                        state_select = select
                        state_select_found = True
                        print(f"Found state dropdown with ID: {select_elem.get_attribute('id')}")
                        break
                except Exception as e:
                    print(f"Error checking select element: {str(e)}")
                    continue
        
        if not state_select_found:
            print("Could not find state dropdown")
            return False
            
        # Find Tamil Nadu option
        state_selected = False
        for i, option in enumerate(state_select.options):
            if "TAMIL NADU" in option.text.upper():
                state_select.select_by_index(i)
                print(f"Selected state: {option.text}")
                state_selected = True
                break
        
        if not state_selected:
            print("Could not find Tamil Nadu state option")
            return False
        
        # Wait for AJAX update
        time.sleep(2)
        wait_for_ajax(driver, wait)
        
        # Step 2: Select Sivagangai district
        print("Selecting district...")
        try:
            district_select = Select(wait.until(EC.element_to_be_clickable((By.ID, "fpsReportForm:district"))))
            
            # Find Sivagangai option
            district_selected = False
            for i, option in enumerate(district_select.options):
                if "SIVAGANGAI" in option.text:
                    district_select.select_by_index(i)
                    print(f"Selected district: {option.text}")
                    district_selected = True
                    break
            
            if not district_selected:
                print("Could not find Sivagangai district option")
                print("Available districts:")
                for option in district_select.options:
                    print(f"- {option.text}")
                return False
            
            # Wait for AJAX update
            time.sleep(2)
            wait_for_ajax(driver, wait)
        except Exception as e:
            print(f"Error selecting district: {str(e)}")
            return False
        
        # Step 3: Select Karaikudi taluk
        print("Selecting taluk...")
        try:
            taluk_select = Select(wait.until(EC.element_to_be_clickable((By.ID, "fpsReportForm:taluk"))))
            
            # Find Karaikudi option
            taluk_selected = False
            for i, option in enumerate(taluk_select.options):
                if "KARAIKUDI" in option.text:
                    taluk_select.select_by_index(i)
                    print(f"Selected taluk: {option.text}")
                    taluk_selected = True
                    break
            
            if not taluk_selected:
                print("Could not find Karaikudi taluk option")
                print("Available taluks:")
                for option in taluk_select.options:
                    print(f"- {option.text}")
                return False
            
            # Wait for AJAX update
            time.sleep(2)
            wait_for_ajax(driver, wait)
        except Exception as e:
            print(f"Error selecting taluk: {str(e)}")
            return False
        
        # Step 4: Select a shop
        print("Selecting shop...")
        try:
            shop_select = Select(wait.until(EC.element_to_be_clickable((By.ID, "fpsReportForm:fps"))))
            
            # Select first non-default shop
            shop_selected = False
            if len(shop_select.options) > 1:
                shop_select.select_by_index(1)  # Select first non-default option
                print(f"Selected shop: {shop_select.options[1].text}")
                shop_selected = True
            
            if not shop_selected:
                print("No shops available to select")
                return False
            
            # Wait for AJAX update
            time.sleep(2)
            wait_for_ajax(driver, wait)
        except Exception as e:
            print(f"Error selecting shop: {str(e)}")
            return False
        
        # Step 5: Click search/submit button
        print("Clicking search button...")
        search_button_selectors = [
            "#fpsReportForm\\:searchButton",
            "button[id*='search']",
            "input[type='submit']",
            "button[type='submit']"
        ]
        
        search_button = find_element_with_retry(driver, wait, search_button_selectors, "search button")
        if search_button:
            driver.execute_script("arguments[0].click();", search_button)
            print("Clicked search button")
            
            # Wait for results to load
            time.sleep(3)
            wait_for_ajax(driver, wait)
            
            # Check if results loaded
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".fps-detail-container, .ui-datatable")))
                print("Results loaded successfully")
                driver.save_screenshot("results_page.png")
                return True
            except TimeoutException:
                print("Results did not load within timeout")
                driver.save_screenshot("results_timeout.png")
                return False
        else:
            print("Could not find search button")
            return False
    
    except Exception as e:
        print(f"Error filling form: {str(e)}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("form_fill_error.png")
        return False

def extract_results(driver):
    """Extract results from the page"""
    try:
        results_data = {
            "tableData": [],
            "shopDetails": {}
        }
        
        # Extract table data
        tables = driver.find_elements(By.CSS_SELECTOR, "table[role='grid']")
        for table_idx, table in enumerate(tables):
            # Get headers
            headers = []
            header_cells = table.find_elements(By.TAG_NAME, "th")
            for cell in header_cells:
                headers.append(cell.text.strip())
            
            # Get rows
            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                row_data = {}
                cells = row.find_elements(By.TAG_NAME, "td")
                
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        header = headers[i] or f"Column{i}"
                        row_data[header] = cell.text.strip()
                
                if row_data:
                    results_data["tableData"].append(row_data)
        
        # Extract shop details
        detail_containers = driver.find_elements(By.CSS_SELECTOR, ".fps-detail-container")
        for container in detail_containers:
            labels = container.find_elements(By.TAG_NAME, "label")
            for label in labels:
                try:
                    key = label.text.strip().replace(":", "")
                    # Get the next sibling which contains the value
                    value_element = driver.execute_script("return arguments[0].nextElementSibling;", label)
                    value = value_element.text.strip() if value_element else ""
                    if key and value:
                        results_data["shopDetails"][key] = value
                except Exception as e:
                    pass
        
        print("Successfully extracted results")
        save_data_to_json(results_data, "pds_results.json")
        return results_data
    except Exception as e:
        print(f"Error extracting results: {str(e)}")
        import traceback
        return None

def navigate_to_main_page(driver, wait):
    """Navigate to the main page of the Tamil Nadu PDS website"""
    try:
        # Go to homepage
        print("Loading main page...")
        driver.get("https://www.tnpds.gov.in")
        
        # Wait for page to load
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        print("Main page loaded")
        
        # Switch to English
        if switch_to_english(driver, wait):
            print("Successfully switched to English")
            return True
        else:
            print("Failed to switch to English")
            return False
    except Exception as e:
        print(f"Error navigating to main page: {str(e)}")
        driver.save_screenshot("main_page_error.png")
        return False

def check_navigation_state(driver, wait, expected_level, district=None, taluk=None):
    """
    Check if we're on the expected navigation level
    expected_level: 'state', 'district', 'taluk', or 'shop'
    """
    try:
        # Wait for page to be fully loaded
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(1)
        
        # Look for breadcrumb to determine current level
        try:
            breadcrumb_xpath = "//p[contains(text(), 'Details Displayed for')]"
            breadcrumb = driver.find_element(By.XPATH, breadcrumb_xpath)
            if breadcrumb:
                links = breadcrumb.find_elements(By.TAG_NAME, "a")
                text = breadcrumb.text
                
                # Check navigation level based on breadcrumb content
                if expected_level == 'state':
                    # Should only have Tamil Nadu in breadcrumb
                    return len(links) <= 1 and 'Tamil Nadu' in text
                elif expected_level == 'district':
                    # Should have Tamil Nadu and district in breadcrumb
                    return len(links) == 2 and district and district in text
                elif expected_level == 'taluk':
                    # Should have Tamil Nadu, district, and taluk in breadcrumb
                    return len(links) == 3 and district and taluk and district in text and taluk in text
                elif expected_level == 'shop':
                    # Should have Tamil Nadu, district, taluk, and shop ID in breadcrumb
                    return len(links) == 3 and district and taluk and district in text and taluk in text
        except:
            pass
        
        # Check based on page content/elements
        if expected_level == 'state':
            try:
                # State level has district table
                state_table = driver.find_element(By.ID, 'StateLevelDetailsForm:StateLevelDetailsTable')
                return True
            except:
                pass
        elif expected_level == 'district':
            try:
                # District level has taluk table
                taluk_table = driver.find_element(By.CSS_SELECTOR, '.ui-datatable')
                # Check if district name is in page title or header
                return district and district in driver.page_source
            except:
                pass
        elif expected_level == 'taluk':
            try:
                # Taluk level has shop table
                shop_table = driver.find_element(By.CSS_SELECTOR, '.ui-datatable')
                # Check if taluk name is in page title or header
                return taluk and taluk in driver.page_source
            except:
                pass
        elif expected_level == 'shop':
            try:
                # Shop level has multiple data tables
                tables = driver.find_elements(By.CSS_SELECTOR, '.ui-datatable')
                return len(tables) >= 3  # Shop pages typically have multiple tables
            except:
                pass
                
        return False
    except Exception as e:
        print(f"Error checking navigation state: {str(e)}")
        return False

def navigate_to_main_page(driver, wait):
    """
    Navigate to the main page of the Tamil Nadu PDS website
    """
    try:
        print("Navigating to main page...")
        driver.get("https://www.tnpds.gov.in")
        time.sleep(2)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        
        # Switch to English if needed
        switch_to_english(driver, wait)
        
        print("Successfully navigated to main page")
        return True
    except Exception as e:
        print(f"Error navigating to main page: {str(e)}")
        return False

def navigate_to_pds_reports_and_get_districts(driver, wait):
    """Navigate to PDS Reports page and extract district data"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Go back to the main page first to ensure consistent navigation
            if attempt > 0:
                print(f"Retry attempt {attempt+1}/{max_retries}")
                navigate_to_main_page(driver, wait)
                time.sleep(2)
            
            # Find and click PDS Reports link
            print("Looking for PDS Reports link...")
            pds_reports_clicked = False
            
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                if 'PDS Reports' in link.text:
                    print("Found PDS Reports link")
                    try:
                        link.click()
                        pds_reports_clicked = True
                        break
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", link)
                            pds_reports_clicked = True
                            break
                        except Exception as e:
                            print(f"Error clicking PDS Reports link: {str(e)}")
            
            if not pds_reports_clicked:
                print("Could not find or click PDS Reports link")
                if attempt == max_retries - 1:
                    return None
                else:
                    time.sleep(2)
                    continue
            
            # Wait for page to load
            time.sleep(2)
            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            print("PDS Reports page loaded")
            
            # Page loaded successfully
            
            # Look for district table
            print("Looking for district table...")
            try:
                # Wait for the district table to be present
                district_table = wait.until(EC.presence_of_element_located(
                    (By.ID, 'StateLevelDetailsForm:StateLevelDetailsTable')
                ))
                print("Found district table")
                
                # Found district table successfully
                
                # Extract district data
                rows = district_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                print(f"Found {len(rows)} district rows")
                
                districts = []
                for row in rows:
                    try:
                        district_cell = row.find_element(By.CSS_SELECTOR, 'td:first-child')
                        district_name = district_cell.text.strip()
                        if district_name:
                            districts.append(district_name)
                    except Exception as e:
                        print(f"Error extracting district: {str(e)}")
                
                print(f"Extracted {len(districts)} districts")
                if districts:
                    print(f"Sample districts: {districts[:3]}" + ("..." if len(districts) > 3 else ""))
                
                return districts
                
            except Exception as e:
                print(f"Error finding district table: {str(e)}")
                if attempt == max_retries - 1:
                    return None
                continue
                
        except Exception as e:
            print(f"Error navigating to PDS Reports: {str(e)}")
            import traceback
            traceback.print_exc()
            if attempt == max_retries - 1:
                return None
            continue
    
    return None

def navigate_to_district_and_get_taluks(driver, wait, district_name):
    """Navigate to a specific district and extract taluk data"""
    try:
        # Find district table
        print(f"Looking for district table to find {district_name}...")
        district_table = wait.until(EC.presence_of_element_located(
            (By.ID, 'StateLevelDetailsForm:StateLevelDetailsTable')
        ))
        
        # Find the row with the target district
        rows = district_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
        district_row = None
        district_link = None
        
        for row in rows:
            try:
                cell = row.find_element(By.CSS_SELECTOR, 'td:first-child')
                if cell.text.strip().lower() == district_name.lower():
                    district_row = row
                    # Find the link in this row
                    district_link = cell.find_element(By.TAG_NAME, 'a')
                    break
            except Exception as e:
                continue
        
        if not district_link:
            print(f"Could not find district: {district_name}")
            return None
        
        # Click on the district link
        print(f"Clicking on district: {district_name}")
        try:
            driver.execute_script("arguments[0].click();", district_link)
        except Exception as e:
            print(f"Error clicking district link: {str(e)}")
            return None
        
        # Wait for page to load
        time.sleep(2)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        print("Page updated after district click")
        
        # Look for taluk table
        print("Looking for taluk table...")
        try:
            
            # Try multiple possible selectors for the taluk table
            taluk_table_selectors = [
                '[id$="TalukLevelDetailsTable"]',  # Ends with TalukLevelDetailsTable
                '[id*="Taluk"][id*="Table"]',     # Contains both 'Taluk' and 'Table'
                '.ui-datatable',                  # PrimeFaces datatable class
                'table.dataTable',                # Common datatable class
                'table:not(.ui-menu-list)'       # Any table that's not a menu
            ]
            
            taluk_table = None
            for selector in taluk_table_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Filter out small tables that might be menus or other UI elements
                    valid_tables = []
                    for table in elements:
                        try:
                            rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                            if len(rows) > 1:  # Table should have multiple rows
                                valid_tables.append(table)
                        except:
                            continue
                    
                    if valid_tables:
                        taluk_table = valid_tables[0]
                        print(f"Found taluk table with selector: {selector}")
                        break
            
            if not taluk_table:
                print("Could not find taluk table")
                return None
            
            # Extract taluk data
            rows = taluk_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            print(f"Found {len(rows)} taluk rows")
            
            taluks = []
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                    if cells:
                        taluk_name = cells[0].text.strip()
                        if taluk_name:
                            taluks.append(taluk_name)
                except Exception as e:
                    print(f"Error extracting taluk name: {str(e)}")
            
            print(f"Extracted {len(taluks)} taluks")
            if taluks:
                print(f"Sample taluks: {taluks[:3]}" + ("..." if len(taluks) > 3 else ""))
            
            return taluks
            
        except Exception as e:
            print(f"Error processing taluk table: {str(e)}")
            import traceback
            traceback.print_exc()
            driver.save_screenshot(os.path.join(screenshots_dir, "taluk_processing_error.png"))
            return None
            
    except Exception as e:
        print(f"Error navigating to district: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def navigate_to_taluk_and_get_shops(driver, wait, taluk_name):
    """Navigate to a specific taluk and extract shop data"""
    try:
        # Find taluk table
        print(f"Looking for taluk table to find {taluk_name}...")
        
        # Try multiple possible selectors for the taluk table
        taluk_table_selectors = [
            '[id$="TalukLevelDetailsTable"]',  # Ends with TalukLevelDetailsTable
            '[id*="Taluk"][id*="Table"]',     # Contains both 'Taluk' and 'Table'
            '.ui-datatable',                  # PrimeFaces datatable class
            'table.dataTable',                # Common datatable class
            'table:not(.ui-menu-list)'       # Any table that's not a menu
        ]
        
        taluk_table = None
        for selector in taluk_table_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                # Filter out small tables
                valid_tables = []
                for table in elements:
                    try:
                        rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                        if len(rows) > 1:  # Table should have multiple rows
                            valid_tables.append(table)
                    except:
                        continue
                
                if valid_tables:
                    taluk_table = valid_tables[0]
                    print(f"Found taluk table with selector: {selector}")
                    break
        
        if not taluk_table:
            print("Could not find taluk table")
            return None
        
        # Find the row with the target taluk
        rows = taluk_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
        taluk_row = None
        taluk_link = None
        
        for row in rows:
            try:
                cells = row.find_elements(By.CSS_SELECTOR, 'td')
                if cells and cells[0].text.strip().lower() == taluk_name.lower():
                    taluk_row = row
                    # Find the link in this row
                    links = row.find_elements(By.TAG_NAME, 'a')
                    if links:
                        taluk_link = links[0]
                    break
            except Exception as e:
                continue
        
        if not taluk_link:
            print(f"Could not find taluk: {taluk_name}")
            return None
        
        # Click on the taluk link
        print(f"Clicking on taluk: {taluk_name}")
        try:
            driver.execute_script("arguments[0].click();", taluk_link)
        except Exception as e:
            print(f"Error clicking taluk link: {str(e)}")
            return None
        
        # Wait for page to load
        time.sleep(2)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        print("Page updated after taluk click")
        
        # Look for shop table
        print("Looking for shop table...")
        try:
            
            # Try multiple possible selectors for the shop table
            shop_table_selectors = [
                '[id$="ShopLevelDetailsTable"]',  # Ends with ShopLevelDetailsTable
                '[id*="Shop"][id*="Table"]',     # Contains both 'Shop' and 'Table'
                '.ui-datatable',                 # PrimeFaces datatable class
                'table.dataTable',               # Common datatable class
                'table:not(.ui-menu-list)'      # Any table that's not a menu
            ]
            
            shop_table = None
            for selector in shop_table_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Filter out small tables
                    valid_tables = []
                    for table in elements:
                        try:
                            rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                            if len(rows) > 1:  # Table should have multiple rows
                                valid_tables.append(table)
                        except:
                            continue
                    
                    if valid_tables:
                        shop_table = valid_tables[0]
                        print(f"Found shop table with selector: {selector}")
                        break
            
            if not shop_table:
                print("Could not find shop table")
                return None
            
            # Extract shop data
            rows = shop_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            print(f"Found {len(rows)} shop rows")
            
            # Get headers
            headers = shop_table.find_elements(By.CSS_SELECTOR, 'th')
            header_texts = [h.text.strip() for h in headers]
            print(f"Shop table headers: {header_texts}")
            
            shops = []
            for row in rows:
                try:
                    cells = row.find_elements(By.CSS_SELECTOR, 'td')
                    if cells:
                        shop_data = {}
                        for i, cell in enumerate(cells):
                            if i < len(header_texts):
                                header = header_texts[i] if header_texts[i] else f"Column{i}"
                                shop_data[header] = cell.text.strip()
                        if shop_data:
                            shops.append(shop_data)
                except Exception as e:
                    print(f"Error extracting shop data: {str(e)}")
            
            print(f"Extracted {len(shops)} shops")
            if shops:
                print(f"Sample shop: {shops[0]}")
            
            return shops
            
        except Exception as e:
            print(f"Error processing shop table: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    except Exception as e:
        print(f"Error navigating to taluk: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def navigate_back_using_breadcrumbs(driver, wait, level):
    """
    Navigate back using the breadcrumb links
    level: 'state', 'district', or 'taluk' - which level to go back to
    """
    try:
        print(f"Attempting to navigate back to {level} level using breadcrumbs...")
        
        # Wait for page to be fully loaded
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(1)
        
        # First try the specific Tamil Nadu PDS format with the "Details Displayed for" text
        try:
            # Using XPath to find the paragraph with "Details Displayed for" text
            breadcrumb_xpath = "//p[contains(text(), 'Details Displayed for')]" 
            breadcrumb = driver.find_element(By.XPATH, breadcrumb_xpath)
            
            if breadcrumb:
                print("Found Tamil Nadu PDS breadcrumb navigation")
                links = breadcrumb.find_elements(By.TAG_NAME, "a")
                
                # Debug info
                print(f"Found {len(links)} links in breadcrumb")
                for i, link in enumerate(links):
                    print(f"Link {i}: {link.text} - {link.get_attribute('onclick')}")
                
                target_link = None
                if level == 'state':
                    # Tamil Nadu link (first)
                    if links and len(links) > 0:
                        target_link = links[0]
                elif level == 'district':
                    # District link (second)
                    if links and len(links) > 1:
                        target_link = links[1]
                elif level == 'taluk':
                    # Taluk link (third)
                    if links and len(links) > 2:
                        target_link = links[2]
                
                if target_link:
                    print(f"Clicking on {level} breadcrumb link: {target_link.text}")
                    try:
                        # Use JavaScript to click since these are JSF links with onclick handlers
                        driver.execute_script("arguments[0].click();", target_link)
                        time.sleep(3)  # Give more time for JSF page update
                        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                        print(f"Successfully navigated back to {level} level")
                        return True
                    except Exception as e:
                        print(f"Error clicking breadcrumb link: {str(e)}")
                else:
                    print(f"Could not find {level} link in breadcrumb")
                
                return False
        except Exception as e:
            print(f"Error finding Tamil Nadu PDS breadcrumb: {str(e)}")
        
        # Try generic breadcrumb selectors as fallback
        breadcrumb_selectors = [
            ".breadcrumb",
            ".navigation-path",
            "nav[aria-label='breadcrumb']",
            "ol.breadcrumb"
        ]
        
        for selector in breadcrumb_selectors:
            try:
                breadcrumb = driver.find_element(By.CSS_SELECTOR, selector)
                if breadcrumb:
                    print(f"Found generic breadcrumb using selector: {selector}")
                    links = breadcrumb.find_elements(By.TAG_NAME, "a")
                    
                    target_index = 0  # Default to first (home)
                    if level == 'state':
                        target_index = 0
                    elif level == 'district':
                        target_index = 1
                    elif level == 'taluk':
                        target_index = 2
                    
                    if links and len(links) > target_index:
                        target_link = links[target_index]
                        print(f"Clicking on {level} breadcrumb link: {target_link.text}")
                        try:
                            driver.execute_script("arguments[0].click();", target_link)
                            time.sleep(2)
                            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                            print(f"Successfully navigated back to {level} level")
                            return True
                        except Exception as e:
                            print(f"Error clicking breadcrumb link: {str(e)}")
                    else:
                        print(f"Could not find {level} link in breadcrumb")
                    
                    break
            except Exception as e:
                continue
        
        print("Could not find any usable breadcrumb navigation")
        return False
        
    except Exception as e:
        print(f"Error navigating back using breadcrumbs: {str(e)}")
        return False

def navigate_to_shop_and_get_details(driver, wait, shop_id, district, taluk, output_dir, shop_name_from_search=None):
    """Navigate to a specific shop, extract detailed shop data, save JSON details, and navigate back using breadcrumbs"""
    try:

        # Create screenshots directory if it doesn't exist
        screenshots_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        # Find shop table
        print(f"Looking for shop table to find shop ID: {shop_id}...")

        # Try multiple possible selectors for the shop table
        shop_table_selectors = [
            '[id$="ShopLevelDetailsTable"]',  # Ends with ShopLevelDetailsTable
            '[id*="Shop"][id*="Table"]',     # Contains both 'Shop' and 'Table'
            '.ui-datatable',                 # PrimeFaces datatable class
            'table.dataTable',               # Common datatable class
            'table:not(.ui-menu-list)'      # Any table that's not a menu
        ]
        
        shop_table = None
        for selector in shop_table_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                # Filter out small tables
                valid_tables = []
                for table in elements:
                    try:
                        rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                        if len(rows) > 1:  # Table should have multiple rows
                            valid_tables.append(table)
                    except:
                        continue
                
                if valid_tables:
                    shop_table = valid_tables[0]
                    print(f"Found shop table with selector: {selector}")
                    break
        
        if not shop_table:
            print("Could not find shop table")
            driver.save_screenshot(os.path.join(screenshots_dir, "shop_table_not_found.png"))
            return False
        
        # Find the row with the target shop ID
        rows = shop_table.find_elements(By.CSS_SELECTOR, 'tbody tr')
        shop_row = None
        shop_link = None
        
        for row in rows:
            try:
                cells = row.find_elements(By.CSS_SELECTOR, 'td')
                if cells:
                    # Check if any cell contains the shop ID
                    for cell in cells:
                        if shop_id.lower() in cell.text.strip().lower():
                            shop_row = row
                            # Find the link in this row
                            links = row.find_elements(By.TAG_NAME, 'a')
                            if links:
                                shop_link = links[0]
                            break
                if shop_link:
                    break
            except Exception as e:
                continue
        
        if not shop_link:
            print(f"Could not find shop with ID: {shop_id}")
            driver.save_screenshot(os.path.join(screenshots_dir, "shop_not_found.png"))
            return False
        
        # Click on the shop link
        print(f"Clicking on shop with ID: {shop_id}")
        try:
            driver.execute_script("arguments[0].click();", shop_link)
        except Exception as e:
            print(f"Error clicking shop link: {str(e)}")
            driver.save_screenshot(os.path.join(screenshots_dir, "shop_click_error.png"))
            return False
        
        # Wait for page to load
        time.sleep(2)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        print("Page updated after shop click")
        
        # Take screenshot
        driver.save_screenshot(os.path.join(screenshots_dir, "after_shop_click.png"))
        
        # Extract shop details
        print("Extracting shop details...")
        try:
            # Save page source for analysis
            with open(os.path.join(screenshots_dir, "shop_details_source.html"), "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            # Extract all data from the page
            shop_details = {}
            
            # Specifically look for shop status (online/offline)
            try:
                status_elements = driver.find_elements(By.CSS_SELECTOR, '.shop-status, .status-indicator, .status, span[class*="status"], div[class*="status"]')
                for element in status_elements:
                    text = element.text.strip().lower()
                    if 'online' in text or 'offline' in text or 'status' in text:
                        shop_details['status'] = element.text.strip()
                        print(f"Found shop status: {shop_details['status']}")
                        break
                
                # If no specific status element found, try looking for text containing status
                if 'status' not in shop_details:
                    page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
                    if 'online status' in page_text:
                        # Find the index and extract nearby text
                        idx = page_text.find('online status')
                        context = page_text[max(0, idx-20):idx+30]
                        shop_details['status_context'] = context
                        print(f"Found status context: {context}")
                        
                    if 'offline' in page_text:
                        shop_details['status'] = 'Offline'
                        print("Shop appears to be offline")
                    elif 'online' in page_text:
                        shop_details['status'] = 'Online'
                        print("Shop appears to be online")
            except Exception as e:
                print(f"Error extracting shop status: {str(e)}")
            
            # Look for tables
            tables = driver.find_elements(By.CSS_SELECTOR, 'table')
            print(f"Found {len(tables)} tables on the shop details page")
            
            # Process each table
            for i, table in enumerate(tables):
                try:
                    # Get table headers
                    headers = [h.text.strip() for h in table.find_elements(By.CSS_SELECTOR, 'th')]
                    
                    # Get table rows
                    rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                    
                    # Process rows
                    table_data = []
                    for row in rows:
                        cells = row.find_elements(By.CSS_SELECTOR, 'td')
                        row_data = {}
                        for j, cell in enumerate(cells):
                            if j < len(headers):
                                header = headers[j] if headers[j] else f"Column{j}"
                                row_data[header] = cell.text.strip()
                        if row_data:
                            table_data.append(row_data)
                    
                    if table_data:
                        shop_details[f"Table{i+1}"] = table_data
                except Exception as e:
                    print(f"Error processing table {i+1}: {str(e)}")
            
            # Look for labels and values
            labels = driver.find_elements(By.CSS_SELECTOR, 'label, .label, .field-label')
            for label in labels:
                try:
                    key = label.text.strip().replace(':', '')
                    if not key:
                        continue
                        
                    # Try to find the value next to this label
                    value_element = driver.execute_script("return arguments[0].nextElementSibling;", label)
                    value = value_element.text.strip() if value_element else ""
                    
                    if key and value:
                        shop_details[key] = value
                except Exception as e:
                    pass
            
            print("Successfully extracted shop details")
            if shop_details:
                print(f"Found {len(shop_details)} data points")
                
            # Save shop details to the proper directory
            shop_data = {
                "district": district,
                "taluk": taluk,
                "shop": shop_id,
                "details": shop_details
            }
            
            # Save to the taluk directory
            shop_file = os.path.join(output_dir, f"pds_shop_details_{shop_id}.json")
            with open(shop_file, 'w') as f:
                json.dump(shop_data, f, indent=4)
            
            print(f"Saved shop details to {shop_file}")
            
            # Extract last bill transaction and try to click on View link
            last_bill = {}
            bill_details = {}
            if "Table6" in shop_details and shop_details["Table6"] and len(shop_details["Table6"]) > 0:
                try:
                    bill_row = shop_details["Table6"][0]
                    last_bill = {
                        "bill_number": bill_row.get("Bill Number", ""),
                        "transaction_number": bill_row.get("Transaction Number", ""),
                        "date_time": bill_row.get("Date & Time", ""),
                        "amount": bill_row.get("Amount", "")
                    }
                    
                    # Try to find and click the View button on the shop details page
                    print("Looking for View button on shop details page...")
                    # First scroll down to make sure the transaction table is visible
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    
                    # Take a screenshot after scrolling
                    os.makedirs("screenshots", exist_ok=True)
                    driver.save_screenshot(os.path.join("screenshots", f"{shop_id}_after_scroll.png"))
                    print(f"Saved screenshot after scrolling: screenshots/{shop_id}_after_scroll.png")
                    
                    # Try different XPaths to find the View link
                    view_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'link-view') and text()='View']")
                    if not view_links or len(view_links) == 0:
                        view_links = driver.find_elements(By.XPATH, "//a[contains(@onclick, 'billItemWidget') and text()='View']")
                    if not view_links or len(view_links) == 0:
                        view_links = driver.find_elements(By.XPATH, "//a[text()='View']")
                    
                    if view_links and len(view_links) > 0:
                        print(f"Found {len(view_links)} View links. Clicking the first one...")
                        # Try to click using JavaScript
                        try:
                            driver.execute_script("arguments[0].scrollIntoView(true);", view_links[0])
                            time.sleep(1)  # Wait for scroll to complete
                            
                            # First, save a screenshot of the page before clicking
                            os.makedirs("screenshots", exist_ok=True)
                            driver.save_screenshot(os.path.join("screenshots", f"{shop_id}_before_click.png"))
                            print(f"Saved screenshot before clicking View link: screenshots/{shop_id}_before_click.png")
                            
                            # Get the page source to check for View links
                            page_source = driver.page_source
                            with open(os.path.join("screenshots", f"{shop_id}_page_source.html"), "w", encoding="utf-8") as f:
                                f.write(page_source)
                            print(f"Saved page source to screenshots/{shop_id}_page_source.html")
                            
                            # Try to click the View link
                            view_links[0].click()
                            print("Clicked on View link")
                            
                            # Wait for the bill details dialog to appear
                            WebDriverWait(driver, 15).until(
                                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'ui-dialog')]//span[contains(@class, 'ui-dialog-title') and contains(text(), 'Transactions')]"))
                            )
                            print("Bill details dialog opened")
                            
                            # Take a screenshot of the dialog for debugging
                            driver.save_screenshot(os.path.join("screenshots", f"{shop_id}_bill_dialog.png"))
                            print(f"Saved bill dialog screenshot to screenshots/{shop_id}_bill_dialog.png")
                            
                            # Extract bill details from the dialog
                            bill_details_table = driver.find_elements(By.XPATH, "//div[contains(@class, 'ui-dialog')]//form[@id='billForm']//table")
                            if not bill_details_table or len(bill_details_table) == 0:
                                bill_details_table = driver.find_elements(By.XPATH, "//div[contains(@class, 'ui-dialog')]//table")
                            
                            if bill_details_table and len(bill_details_table) > 0:
                                print(f"Found bill details table with {len(bill_details_table)} tables")
                                # Extract all rows from the bill details table
                                bill_items = []
                                rows = bill_details_table[0].find_elements(By.TAG_NAME, "tr")
                                print(f"Found {len(rows)} rows in bill details table")
                                
                                # Get the header row to identify columns
                                header_cells = rows[0].find_elements(By.TAG_NAME, "th") if rows else []
                                headers = [cell.text.strip() for cell in header_cells]
                                print(f"Found headers: {headers}")
                                
                                # Process data rows
                                for row in rows[1:]:  # Skip header row
                                    cells = row.find_elements(By.TAG_NAME, "td")
                                    print(f"Row has {len(cells)} cells")
                                    if len(cells) >= 6:  # Based on the provided HTML
                                        item = {
                                            "sno": cells[0].text.strip(),
                                            "product_name": cells[1].text.strip(),
                                            "quantity": cells[2].text.strip(),
                                            "unit_price": cells[3].text.strip(),
                                            "total": cells[4].text.strip(),
                                            "unit": cells[5].text.strip()
                                        }
                                        bill_items.append(item)
                                        print(f"Added item: {item}")
                                
                                bill_details["items"] = bill_items
                                print(f"Extracted {len(bill_items)} bill items")
                            else:
                                print("Could not find bill details table in dialog")
                            
                            # Close the dialog
                            close_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'ui-dialog-titlebar')]//a[contains(@class, 'ui-dialog-titlebar-close')]")
                            if not close_buttons or len(close_buttons) == 0:
                                close_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'ui-dialog')]//a[contains(@class, 'ui-dialog-titlebar-close')]")
                            
                            if close_buttons and len(close_buttons) > 0:
                                close_buttons[0].click()
                                print("Closed bill details dialog")
                                time.sleep(1)  # Wait for dialog to close
                            else:
                                print("Could not find close button for dialog")
                                # Try pressing Escape key to close dialog
                                webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                                print("Sent Escape key to close dialog")
                                time.sleep(1)
                        except Exception as e:
                            print(f"Error clicking View link or extracting bill details: {str(e)}")
                    else:
                        print("No View links found on shop details page")
                except (IndexError, AttributeError, KeyError) as e:
                    print(f"Could not extract last bill transaction: {str(e)}")
                    
                # Add bill details to last_bill if available
                if bill_details:
                    last_bill["details"] = bill_details
            
            # Create a simplified shop details dictionary for return
            simplified_details = {
                "name": shop_name_from_search or shop_data.get("details", {}).get("shop_name", "") or "",
                "status": shop_data.get("details", {}).get("status", "Unknown"),
                "last_transaction": last_bill
            }
            
            # Add bill details if available
            if bill_details and "items" in bill_details and bill_details["items"]:
                simplified_details["last_transaction"]["details"] = bill_details
            
            # Add other useful fields if available
            for key in ["district", "taluk", "shop"]:
                if key in shop_data:
                    simplified_details[key] = shop_data[key]
                    
            return simplified_details
            
        except Exception as e:
            print(f"Error extracting shop details: {str(e)}")
            import traceback
            traceback.print_exc()
            driver.save_screenshot(os.path.join(screenshots_dir, "shop_details_extraction_error.png"))
            return False
            
    except Exception as e:
        print(f"Error navigating to shop: {str(e)}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot(os.path.join(screenshots_dir, "shop_navigation_error.png"))
        return False

def save_data_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f)

def main():
    """Main function to run the crawler"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Tamil Nadu PDS Website Crawler')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--district', type=str, help='Specify a district to crawl (default: all districts)')
    parser.add_argument('--taluk', type=str, help='Specify a taluk to crawl (default: all taluks)')
    parser.add_argument('--shop', type=str, help='Specify a shop code to crawl (default: all shops)')
    parser.add_argument('--output-dir', type=str, default='pds_data', help='Directory to save output files')
    parser.add_argument('--screenshots-dir', type=str, default='screenshots', help='Directory to save screenshots')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum number of retries for operations')
    parser.add_argument('--limit-districts', type=int, default=0, help='Limit number of districts to crawl (0 = all)')
    parser.add_argument('--limit-taluks', type=int, default=0, help='Limit number of taluks per district to crawl (0 = all)')
    parser.add_argument('--limit-shops', type=int, default=0, help='Limit number of shops per taluk to crawl (0 = all)')
    parser.add_argument('--shop-list-json', type=str, help='JSON file containing a list of shop IDs to check')
    parser.add_argument('--output-json', type=str, help='JSON file to save results when using --shop-list-json')
    args = parser.parse_args()
    
    # Check if we're in shop list JSON mode
    if args.shop_list_json:
        if not args.output_json:
            args.output_json = 'shop_status_results.json'
        print(f"Starting shop status check from JSON list: {args.shop_list_json}")
        process_shop_list_json(args.shop_list_json, args.output_json, args.headless)
        return
    
    # Regular crawling mode
    print("Starting PDS website navigation with Selenium...")
    
    # Create output directories
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.screenshots_dir, exist_ok=True)
    
    # Initialize WebDriver
    print("Initializing WebDriver...")
    options = Options()
    if args.headless:
        options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)
    
    try:
        # Navigate to main page
        success = navigate_to_main_page(driver, wait)
        if not success:
            print("Failed to navigate to main page")
            return
        
        # Navigate to PDS reports page and get districts
        all_districts = navigate_to_pds_reports_and_get_districts(driver, wait)
        if not all_districts:
            print("Failed to get districts")
            return
        
        # Create a summary file to track progress
        summary_file = os.path.join(args.output_dir, "crawl_summary.json")
        summary = {
            "total_districts": 0,
            "total_taluks": 0,
            "total_shops": 0,
            "online_shops": 0,
            "offline_shops": 0,
            "districts": {}
        }
        
        # Filter districts if specified
        if args.district:
            if args.district in all_districts:
                districts_to_crawl = [args.district]
            else:
                print(f"District {args.district} not found")
                return
        else:
            districts_to_crawl = all_districts
            if args.limit_districts > 0:
                districts_to_crawl = districts_to_crawl[:args.limit_districts]
            print(f"Crawling {len(districts_to_crawl)} districts")
        
        # Process each district
        for district_idx, district in enumerate(districts_to_crawl):
            print(f"\n[{district_idx+1}/{len(districts_to_crawl)}] Processing district: {district}")
            
            # Create district directory
            district_dir = os.path.join(args.output_dir, district.replace(' ', '_'))
            os.makedirs(district_dir, exist_ok=True)
            
            # Navigate to district and get taluks
            all_taluks = navigate_to_district_and_get_taluks(driver, wait, district)
            if not all_taluks:
                print(f"Failed to get taluks for district {district}, skipping")
                continue
            
            # Add district to summary
            summary["districts"][district] = {
                "total_taluks": 0,
                "total_shops": 0,
                "online_shops": 0,
                "offline_shops": 0,
                "taluks": {}
            }
            summary["total_districts"] += 1
            
            # Filter taluks if specified
            if args.taluk:
                if args.taluk in all_taluks:
                    taluks_to_crawl = [args.taluk]
                else:
                    print(f"Taluk {args.taluk} not found in district {district}, skipping")
                    continue
            else:
                taluks_to_crawl = all_taluks
                if args.limit_taluks > 0:
                    taluks_to_crawl = taluks_to_crawl[:args.limit_taluks]
                print(f"Crawling {len(taluks_to_crawl)} taluks in district {district}")
            
            # Process each taluk
            for taluk_idx, taluk in enumerate(taluks_to_crawl):
                print(f"  [{taluk_idx+1}/{len(taluks_to_crawl)}] Processing taluk: {taluk}")
                
                # Create taluk directory
                taluk_dir = os.path.join(district_dir, taluk.replace(' ', '_').replace('(', '').replace(')', ''))
                os.makedirs(taluk_dir, exist_ok=True)
                
                # Navigate to taluk and get shops
                shops = navigate_to_taluk_and_get_shops(driver, wait, taluk)
                if not shops:
                    print(f"Failed to get shops for taluk {taluk}, skipping")
                    continue
                    
                # Verify we're on the correct taluk page
                if not check_navigation_state(driver, wait, 'taluk', district=district, taluk=taluk):
                    print(f"Navigation state verification failed for taluk {taluk}, resetting navigation")
                    navigate_to_district_and_get_taluks(driver, wait, district)
                    shops = navigate_to_taluk_and_get_shops(driver, wait, taluk)
                    if not shops:
                        print(f"Failed to get shops for taluk {taluk} after reset, skipping")
                        continue
                
                # Add taluk to summary
                summary["districts"][district]["taluks"][taluk] = {
                    "total_shops": len(shops),
                    "processed_shops": 0,
                    "online_shops": 0,
                    "offline_shops": 0,
                    "shops": {}
                }
                summary["districts"][district]["total_taluks"] += 1
                summary["total_taluks"] += 1
                
                # Filter shops if specified
                if args.shop:
                    shop_found = False
                    shops_to_crawl = []
                    for shop in all_shops:
                        if shop['SHOP CODE'] == args.shop:
                            shops_to_crawl = [shop]
                            shop_found = True
                            break
                    if not shop_found:
                        print(f"Shop {args.shop} not found in taluk {taluk}, skipping")
                        continue
                else:
                    shops_to_crawl = shops
                    if args.limit_shops > 0:
                        shops_to_crawl = shops_to_crawl[:args.limit_shops]
                    print(f"    Crawling {len(shops_to_crawl)} shops in taluk {taluk}")
                
                # Process each shop
                for shop_idx, shop in enumerate(shops_to_crawl):
                    shop_id = shop['SHOP CODE']
                    print(f"    [{shop_idx+1}/{len(shops_to_crawl)}] Processing shop: {shop_id} - {shop['SHOP NAME']}")
                    
                    # Navigate to shop and get details
                    success = navigate_to_shop_and_get_details(driver, wait, shop_id, district, taluk, taluk_dir)
                    
                    if success:
                        # Read the shop details file to get status
                        shop_file = os.path.join(taluk_dir, f"pds_shop_details_{shop_id}.json")
                        try:
                            with open(shop_file, 'r') as f:
                                shop_data = json.load(f)
                                shop_status = shop_data.get('details', {}).get('shop_status', 'Unknown')
                                
                                # Add shop to summary
                                summary["districts"][district]["taluks"][taluk]["shops"][shop_id] = {
                                    "name": shop['SHOP NAME'],
                                    "status": shop_status,
                                    "incharge": shop['SHOP INCHARGE'],
                                    "cards": shop['TOTAL NUMBER OF CARDS'],
                                    "beneficiaries": shop['TOTAL NUMBER OF BENEFICIARIES']
                                }
                                
                                summary["districts"][district]["taluks"][taluk]["total_shops"] += 1
                                summary["districts"][district]["total_shops"] += 1
                                summary["total_shops"] += 1
                                
                                if shop_status.lower() == 'online':
                                    summary["districts"][district]["taluks"][taluk]["online_shops"] += 1
                                    summary["districts"][district]["online_shops"] += 1
                                    summary["online_shops"] += 1
                                elif shop_status.lower() == 'offline':
                                    summary["districts"][district]["taluks"][taluk]["offline_shops"] += 1
                                    summary["districts"][district]["offline_shops"] += 1
                                    summary["offline_shops"] += 1
                        except Exception as e:
                            print(f"Error processing shop details for {shop_id}: {str(e)}")
                    else:
                        print(f"Failed to get details for shop {shop_id}, skipping")
                    
                    # Save summary after each shop to track progress
                    with open(summary_file, 'w') as f:
                        json.dump(summary, f, indent=2)
                    
                    # Navigate back to taluk page to continue with next shop
                    navigate_to_district_and_get_taluks(driver, wait, district)
                    navigate_to_taluk_and_get_shops(driver, wait, taluk)
                
                # After processing all shops for a taluk, try to go back to district page using breadcrumbs
                if not navigate_back_using_breadcrumbs(driver, wait, 'district'):
                    print("Failed to navigate back to district using breadcrumbs, using regular navigation")
                    navigate_to_pds_reports_and_get_districts(driver, wait)
                    navigate_to_district_and_get_taluks(driver, wait, district)
                
                # Verify we're on the correct district page
                if not check_navigation_state(driver, wait, 'district', district=district):
                    print(f"Navigation state verification failed for district {district}, resetting navigation")
                    navigate_to_pds_reports_and_get_districts(driver, wait)
                    navigate_to_district_and_get_taluks(driver, wait, district)
            
            # Navigate back to districts page to continue with next district
            if not navigate_back_using_breadcrumbs(driver, wait, 'state'):
                print("Failed to navigate back to state level using breadcrumbs, using regular navigation")
                navigate_to_pds_reports_and_get_districts(driver, wait)
            
            # Verify we're on the correct state page
            if not check_navigation_state(driver, wait, 'state'):
                print("Navigation state verification failed for state level, resetting navigation")
                navigate_to_pds_reports_and_get_districts(driver, wait)
        
        print("\nCrawling completed successfully!")
        print(f"Data saved to {args.output_dir}/")
        print(f"Summary saved to {summary_file}")
        print(f"Screenshots saved to {args.screenshots_dir}/")
        
        # Print summary statistics
        print(f"\nSummary Statistics:")
        print(f"Total Districts: {summary['total_districts']}")
        print(f"Total Taluks: {summary['total_taluks']}")
        print(f"Total Shops: {summary['total_shops']}")
        print(f"Online Shops: {summary['online_shops']}")
        print(f"Offline Shops: {summary['offline_shops']}")
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Take final screenshot
        driver.save_screenshot("final_state.png")
        print("Final screenshot saved")
        driver.quit()

if __name__ == "__main__":
    main()
