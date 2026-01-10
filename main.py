import os
import sys
import time
import random
import traceback
from dotenv import load_dotenv
import groq
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rich.console import Console
from rich.progress import track  
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Load environment variables
load_dotenv()
console = Console()

# Initialize Groq client
try:
    if hasattr(groq, 'Client'):
        client = groq.Client(api_key=os.getenv("GROQ_API_KEY"))
    elif hasattr(groq, 'Groq'):
        client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    else:
        console.print("[yellow]Warning: Using experimental groq client initialization[/yellow]")
        client = groq.client(api_key=os.getenv("GROQ_API_KEY"))
    console.print("[green]Successfully initialized Groq client[/green]")
except Exception as e:
    console.print(f"[red]Error initializing Groq client: {str(e)}[/red]")
    exit(1)

def random_delay(min_seconds=1, max_seconds=3):
    time.sleep(random.uniform(min_seconds, max_seconds))

def retry(max_attempts=3, delay_seconds=5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    console.print(f"[yellow]Attempt {attempts}/{max_attempts} failed: {str(e)}[/yellow]")
                    if attempts == max_attempts:
                        console.print(f"[red]All attempts failed. Error: {str(e)}[/red]")
                        return False
                    time.sleep(delay_seconds)
            return False
        return wrapper
    return decorator

def generate_linkedin_content(topic=None, role=None, industry=None):
    if not topic:
        topics = ["hiring top talent", "building a strong team", "recruitment strategies", "remote work culture", "leadership in tech"]
        topic = random.choice(topics)
    if not role:
        roles = ["software engineer", "product manager", "data scientist", "UX designer", "DevOps specialist"]
        role = random.choice(roles)
    if not industry:
        industries = ["tech", "healthcare", "finance", "education", "e-commerce"]
        industry = random.choice(industries)

    console.print(f"[bold]Generating content about: {topic} for {role} in {industry}[/bold]")
    prompt = f"""
    Create a LinkedIn post about {topic} focusing on hiring {role}s in the {industry} industry.
    The post should:
    - Be between 150-250 words
    - Include 3-5 relevant hashtags at the end
    - Have a strong opening hook
    - Include a specific call to action
    - Sound professional but conversational
    - No placeholders like [Your Name]
    """
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.6,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        console.print(f"[red]Error generating content: {str(e)}[/red]")
        return None

@retry(max_attempts=3, delay_seconds=10)
def post_to_linkedin(driver, content):
    console.print("[bold]Posting content to LinkedIn...[/bold]")
    try:
        driver.get("https://www.linkedin.com/feed/")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)
        
        # 1. CLICK 'START A POST'
        console.print("[cyan]Opening post dialog...[/cyan]")
        start_post_selectors = [
            (By.XPATH, "//span[contains(text(), 'Start a post')]"),
            (By.XPATH, "//button[contains(., 'Start a post')]"),
            (By.CLASS_NAME, "share-box-feed-entry__trigger"),
            (By.CSS_SELECTOR, "button.share-box-feed-entry__trigger")
        ]
        
        opened = False
        for method, selector in start_post_selectors:
            try:
                elem = driver.find_element(method, selector)
                elem.click()
                opened = True
                break
            except: continue
            
        if not opened:
            # Fallback: Click the visual center area where the box usually is
            console.print("[yellow]Using visual click fallback...[/yellow]")
            try:
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.HOME)
                time.sleep(1)
                webdriver.ActionChains(driver).move_by_offset(300, 250).click().perform()
                time.sleep(2)
            except: pass

        # 2. WAIT FOR DIALOG & ENTER TEXT
        console.print("[cyan]Waiting for editor...[/cyan]")
        time.sleep(3)
        
        # Try to find the specific editor div
        editor_selectors = [
            (By.CSS_SELECTOR, ".ql-editor"),
            (By.CSS_SELECTOR, "div[data-test-ql-editor-content='true']"),
            (By.CSS_SELECTOR, "div[role='textbox']"),
            (By.CSS_SELECTOR, "div[contenteditable='true']")
        ]
        
        editor = None
        for method, selector in editor_selectors:
            try:
                editor = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((method, selector)))
                break
            except: continue
            
        if not editor:
            editor = driver.switch_to.active_element

        # Clear and type
        editor.click()
        time.sleep(1)
        editor.send_keys(content)
        time.sleep(2)
        
        # 3. CLICK POST
        console.print("[cyan]Looking for Post button...[/cyan]")
        
        post_btn_selectors = [
            (By.CSS_SELECTOR, "div.share-box_actions button.artdeco-button--primary"),
            (By.XPATH, "//button[contains(@class, 'artdeco-button--primary') and contains(., 'Post')]"),
            (By.XPATH, "//div[@role='dialog']//button[contains(., 'Post')]"),
            (By.CSS_SELECTOR, "button.share-actions__primary-action")
        ]
        
        clicked_post = False
        for method, selector in post_btn_selectors:
            try:
                btn = driver.find_element(method, selector)
                if btn.is_enabled():
                    btn.click()
                    clicked_post = True
                    console.print(f"[green]Clicked Post button using {selector}[/green]")
                    break
                else:
                    console.print(f"[yellow]Found button {selector} but it is disabled[/yellow]")
            except: continue
        

        # 4. VERIFY
        time.sleep(5)
        if "/feed/" in driver.current_url:
            console.print("[bold green]✓ Post submitted successfully![/bold green]")
            return True
        return True

    except Exception as e:
        console.print(f"[red]Error posting: {str(e)}[/red]")
        # driver.save_screenshot("post_error.png") 
        raise

def login_to_linkedin(driver):
    console.print("[bold]Logging in...[/bold]")
    try:
        driver.get("https://www.linkedin.com/login")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
        
        driver.find_element(By.ID, "username").send_keys(os.getenv("LINKEDIN_USER"))
        driver.find_element(By.ID, "password").send_keys(os.getenv("LINKEDIN_PASS"))
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        time.sleep(5)
        if "challenge" in driver.current_url or "security" in driver.current_url:
            console.print("[bold yellow]Security check needed! Solve it manually now.[/bold yellow]")
            time.sleep(60)

        return True
    except Exception as e:
        console.print(f"[red]Login Error: {str(e)}[/red]")
        return False

# ---  PROGRESS BAR ---
def generate_and_post_content(custom_topic=None, custom_role=None, custom_industry=None, schedule_posts=False, num_posts=1, interval_hours=24):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = None
    try:
        # Use ChromeDriverManager to automatically install valid driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        if not login_to_linkedin(driver): return
        
        if schedule_posts:
            for i in range(num_posts):
                # 1. Generate FRESH content for this specific post
                console.print(f"\n[bold cyan]--- Processing Post {i+1}/{num_posts} ---[/bold cyan]")
                content = generate_linkedin_content(custom_topic, custom_role, custom_industry)
                
                if not content: 
                    console.print("[red]Skipping this post due to generation failure.[/red]")
                    continue

                # 2. Post it
                if post_to_linkedin(driver, content):
                    console.print(f"[green]Successfully posted #{i+1}[/green]")
                
                # 3. Wait (Countdown) if it's not the last post
                if i < num_posts - 1:
                    seconds_to_wait = int(interval_hours * 3600)
                    console.print(f"[yellow]Next post in {interval_hours} hours ({seconds_to_wait} seconds)...[/yellow]")
                    
                    # Visual Countdown Bar using Rich
                    for _ in track(range(seconds_to_wait), description="Waiting..."):
                        time.sleep(1)
        else:
            # Single post logic
            content = generate_linkedin_content(custom_topic, custom_role, custom_industry)
            if content:
                post_to_linkedin(driver, content)

    except Exception as e:
        console.print(f"[red]Critical Error: {str(e)}[/red]")
    finally:
        if driver:
            driver.quit() 
            pass

def main():
    console.print("[bold]===== LinkedIn Automation =====[/bold]")
    print("1. One-time Post")
    print("2. Custom Post")
    print("3. Schedule Posts")
    print("4. Exit")
    
    choice = input("\nOption: ").strip()
    
    if choice == "1":
        generate_and_post_content()
    elif choice == "2":
        t = input("Topic: ").strip()
        r = input("Role: ").strip()
        i = input("Industry: ").strip()
        generate_and_post_content(custom_topic=t, custom_role=r, custom_industry=i)
    elif choice == "3":
        n = int(input("Count: "))
        h = float(input("Hours gap: "))
        generate_and_post_content(schedule_posts=True, num_posts=n, interval_hours=h)
    elif choice == "4":
        console.print("[bold]Exiting program.[/bold]")
        return
    else:
        console.print("[red]Invalid choice. Exiting.[/red]")

if __name__ == "__main__":
    main()