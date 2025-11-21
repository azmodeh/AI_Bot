#!/usr/bin/env python3
"""
AI Bot Launcher
===================
Cross-platform launcher with GUI for AI Telegram Bot

Features:
- Auto virtual environment setup
- Package installation
- Configuration validation
- GUI interface
- Logging
- Error handling
"""

import os
import sys
import subprocess
import platform
import logging
from pathlib import Path
from typing import Optional, Tuple
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue


# تنظیمات
PROJECT_DIR = Path(__file__).parent.absolute()
VENV_DIR = PROJECT_DIR / "data" / "venv"
BOT_DIR = PROJECT_DIR
CONFIG_FILE = PROJECT_DIR / "config" / "config.env"
LOG_FILE = PROJECT_DIR / "data" / "logs" / "launcher.log"

# رنگ‌ها برای GUI
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "success": "#4caf50",
    "error": "#f44336",
    "warning": "#ff9800",
    "info": "#2196f3",
    "button": "#2196f3",
    "button_hover": "#1976d2",
}


class LauncherGUI:
    """رابط گرافیکی Launcher"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Bot Launcher")
        self.root.geometry("800x600")
        self.root.configure(bg=COLORS["bg"])
        
        # Queue برای ارتباط بین thread‌ها
        self.log_queue = queue.Queue()
        
        # وضعیت
        self.is_running = False
        self.bot_process = None
        
        self.setup_ui()
        self.setup_logging()
        
        # شروع چک کردن queue
        self.root.after(100, self.process_log_queue)
    
    def setup_ui(self):
        """ساخت رابط کاربری"""
        # Header
        header_frame = tk.Frame(self.root, bg=COLORS["bg"])
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title = tk.Label(
            header_frame,
            text="🤖  Bot Launcher",
            font=("Arial", 20, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"]
        )
        title.pack()
        
        subtitle = tk.Label(
            header_frame,
            text="Telegram Bot for Lash Extension Analysis",
            font=("Arial", 10),
            bg=COLORS["bg"],
            fg=COLORS["info"]
        )
        subtitle.pack()
        
        # Status Frame
        status_frame = tk.Frame(self.root, bg=COLORS["bg"])
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(
            status_frame,
            text="● آماده",
            font=("Arial", 12),
            bg=COLORS["bg"],
            fg=COLORS["success"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Buttons Frame
        button_frame = tk.Frame(self.root, bg=COLORS["bg"])
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_button = tk.Button(
            button_frame,
            text="▶ Start Bot",
            command=self.start_bot,
            bg=COLORS["button"],
            fg=COLORS["fg"],
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="⏹ Stop Bot",
            command=self.stop_bot,
            bg=COLORS["error"],
            fg=COLORS["fg"],
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.setup_button = tk.Button(
            button_frame,
            text="⚙ Setup",
            command=self.run_setup,
            bg=COLORS["warning"],
            fg=COLORS["fg"],
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.setup_button.pack(side=tk.LEFT, padx=5)
        
        self.config_button = tk.Button(
            button_frame,
            text="📝 Config",
            command=self.open_config,
            bg=COLORS["info"],
            fg=COLORS["fg"],
            font=("Arial", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.config_button.pack(side=tk.LEFT, padx=5)
        
        # Log Frame
        log_frame = tk.Frame(self.root, bg=COLORS["bg"])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        log_label = tk.Label(
            log_frame,
            text="📋 Logs:",
            font=("Arial", 10, "bold"),
            bg=COLORS["bg"],
            fg=COLORS["fg"]
        )
        log_label.pack(anchor=tk.W)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            bg="#2d2d2d",
            fg=COLORS["fg"],
            font=("Consolas", 9),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # تنظیم رنگ‌های tag برای لاگ
        self.log_text.tag_config("INFO", foreground=COLORS["info"])
        self.log_text.tag_config("SUCCESS", foreground=COLORS["success"])
        self.log_text.tag_config("WARNING", foreground=COLORS["warning"])
        self.log_text.tag_config("ERROR", foreground=COLORS["error"])
    
    def setup_logging(self):
        """تنظیم logging"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(LOG_FILE, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message: str, level: str = "INFO"):
        """اضافه کردن لاگ به queue"""
        self.log_queue.put((message, level))
        self.logger.info(f"[{level}] {message}")
    
    def process_log_queue(self):
        """پردازش لاگ‌ها از queue"""
        try:
            while True:
                message, level = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"{message}\n", level)
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_log_queue)
    
    def update_status(self, text: str, color: str):
        """بروزرسانی وضعیت"""
        self.status_label.config(text=f"● {text}", fg=color)
    
    def check_python(self) -> bool:
        """بررسی نصب Python"""
        try:
            result = subprocess.run(
                [sys.executable, "--version"],
                capture_output=True,
                text=True
            )
            version = result.stdout.strip()
            self.log(f"✓ Python found: {version}", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"✗ Python not found: {e}", "ERROR")
            return False
    
    def check_venv(self) -> bool:
        """بررسی محیط مجازی"""
        if VENV_DIR.exists():
            self.log("✓ Virtual environment exists", "SUCCESS")
            return True
        else:
            self.log("✗ Virtual environment not found", "WARNING")
            return False
    
    def create_venv(self):
        """ساخت محیط مجازی"""
        self.log("Creating virtual environment...", "INFO")
        self.log(f"Command: {sys.executable} -m venv {VENV_DIR}", "INFO")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
                self.log(result.stdout, "INFO")
            if result.stderr:
                self.log(result.stderr, "WARNING")
            
            # بررسی که واقعاً ساخته شده
            if VENV_DIR.exists():
                self.log("✓ Virtual environment created", "SUCCESS")
                return True
            else:
                self.log("✗ venv directory not created!", "ERROR")
                return False
        except subprocess.CalledProcessError as e:
            self.log(f"✗ Failed to create venv: {e}", "ERROR")
            if e.stdout:
                self.log(f"stdout: {e.stdout}", "ERROR")
            if e.stderr:
                self.log(f"stderr: {e.stderr}", "ERROR")
            return False
        except Exception as e:
            self.log(f"✗ Unexpected error: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def get_pip_path(self) -> Path:
        """دریافت مسیر pip"""
        if platform.system() == "Windows":
            return VENV_DIR / "Scripts" / "pip.exe"
        else:
            return VENV_DIR / "bin" / "pip"
    
    def get_python_path(self) -> Path:
        """دریافت مسیر Python در venv"""
        if platform.system() == "Windows":
            return VENV_DIR / "Scripts" / "python.exe"
        else:
            return VENV_DIR / "bin" / "python"
    
    def install_packages(self):
        """نصب پکیج‌ها"""
        pip_path = self.get_pip_path()
        
        if not pip_path.exists():
            self.log(f"✗ pip not found at: {pip_path}", "ERROR")
            return False
        
        requirements = [
            PROJECT_DIR / "requirements.txt"
        ]
        
        for req_file in requirements:
            if not req_file.exists():
                self.log(f"✗ Requirements file not found: {req_file}", "ERROR")
                continue
            
            self.log(f"Installing packages from {req_file.name}...", "INFO")
            self.log(f"Command: {pip_path} install -r {req_file}", "INFO")
            try:
                result = subprocess.run(
                    [str(pip_path), "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            self.log(line.strip(), "INFO")
                self.log(f"✓ Packages installed from {req_file.name}", "SUCCESS")
            except subprocess.CalledProcessError as e:
                self.log(f"✗ Failed to install packages: {e}", "ERROR")
                if e.stdout:
                    for line in e.stdout.split('\n'):
                        if line.strip():
                            self.log(f"  {line.strip()}", "ERROR")
                if e.stderr:
                    for line in e.stderr.split('\n'):
                        if line.strip():
                            self.log(f"  {line.strip()}", "ERROR")
                # Don't return False, continue with setup
            except Exception as e:
                self.log(f"✗ Unexpected error: {e}", "ERROR")
        
        return True
    
    def check_config(self) -> bool:
        """بررسی فایل config"""
        if not CONFIG_FILE.exists():
            self.log("✗ config.env not found", "ERROR")
            return False
        
        # خواندن و بررسی کلیدهای مهم
        required_keys = [
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
            "TELEGRAM_BOT_TOKEN"
        ]
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            
            missing = []
            for key in required_keys:
                if f"{key}=" not in content or f"{key}=\n" in content:
                    missing.append(key)
            
            if missing:
                self.log(f"✗ Missing config: {', '.join(missing)}", "ERROR")
                return False
            
            self.log("✓ Configuration valid", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"✗ Failed to read config: {e}", "ERROR")
            return False
    
    def run_setup(self):
        """اجرای setup"""
        self.log("=== Starting Setup ===", "INFO")
        self.update_status("در حال راه‌اندازی...", COLORS["warning"])
        
        # بررسی Python
        if not self.check_python():
            messagebox.showerror("Error", "Python not found!")
            self.update_status("خطا", COLORS["error"])
            return
        
        # بررسی/ساخت venv
        if not self.check_venv():
            self.log("Creating virtual environment...", "INFO")
            if not self.create_venv():
                messagebox.showerror("Error", "Failed to create virtual environment!")
                self.update_status("خطا", COLORS["error"])
                return
        
        # نصب پکیج‌ها
        self.log("Installing packages...", "INFO")
        self.install_packages()
        
        # بررسی config
        if not self.check_config():
            messagebox.showwarning(
                "Configuration",
                "Please edit config.env file with your Telegram credentials!"
            )
        
        self.log("=== Setup Complete ===", "SUCCESS")
        self.update_status("آماده", COLORS["success"])
        messagebox.showinfo("Success", "Setup completed successfully!")
    
    def start_bot(self):
        """شروع ربات"""
        if self.is_running:
            messagebox.showwarning("Warning", "Bot is already running!")
            return
        
        # بررسی‌های اولیه
        if not self.check_venv():
            messagebox.showerror("Error", "Virtual environment not found! Run Setup first.")
            return
        
        if not self.check_config():
            messagebox.showerror("Error", "Configuration invalid! Please edit config.env")
            return
        
        self.update_status("در حال اجرا...", COLORS["success"])
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.is_running = True
        
        def bot_thread():
            python_path = self.get_python_path()
            bot_main = PROJECT_DIR / "src" / "main.py"
            
            self.log("=== Starting Bot ===", "INFO")
            self.log(f"Python: {python_path}", "INFO")
            self.log(f"Working dir: {PROJECT_DIR}", "INFO")
            
            try:
                self.bot_process = subprocess.Popen(
                    [str(python_path), str(bot_main)],
                    cwd=str(PROJECT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # خواندن output
                for line in self.bot_process.stdout:
                    if line.strip():
                        self.log(line.strip(), "INFO")
                
                self.bot_process.wait()
                
            except Exception as e:
                self.log(f"✗ Bot error: {e}", "ERROR")
            finally:
                self.is_running = False
                self.root.after(0, self._bot_stopped)
        
        thread = threading.Thread(target=bot_thread, daemon=True)
        thread.start()
    
    def _bot_stopped(self):
        """callback وقتی ربات متوقف شد"""
        self.update_status("متوقف شد", COLORS["warning"])
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.log("=== Bot Stopped ===", "WARNING")
    
    def stop_bot(self):
        """توقف ربات"""
        if not self.is_running or not self.bot_process:
            return
        
        self.log("Stopping bot...", "WARNING")
        try:
            self.bot_process.terminate()
            self.bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.bot_process.kill()
        
        self.is_running = False
        self._bot_stopped()
    
    def open_config(self):
        """باز کردن فایل config"""
        if not CONFIG_FILE.exists():
            messagebox.showerror("Error", "config.env not found!")
            return
        
        try:
            if platform.system() == "Windows":
                os.startfile(CONFIG_FILE)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(CONFIG_FILE)])
            else:  # Linux
                subprocess.run(["xdg-open", str(CONFIG_FILE)])
            
            self.log("✓ Config file opened", "INFO")
        except Exception as e:
            self.log(f"✗ Failed to open config: {e}", "ERROR")
            messagebox.showerror("Error", f"Failed to open config file: {e}")
    
    def run(self):
        """اجرای GUI"""
        self.log("=== AI Bot Launcher Started ===", "INFO")
        self.log(f"Project directory: {PROJECT_DIR}", "INFO")
        
        # بررسی اولیه
        self.check_python()
        self.check_venv()
        
        # اجرای GUI
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """هنگام بستن پنجره"""
        if self.is_running:
            if messagebox.askokcancel("Quit", "Bot is running. Stop and quit?"):
                self.stop_bot()
                self.root.destroy()
        else:
            self.root.destroy()


class LauncherCLI:
    """رابط خط فرمان Launcher برای سرورهای بدون GUI"""
    
    def __init__(self):
        self.setup_logging()
    
    def setup_logging(self):
        """تنظیم logging"""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(LOG_FILE, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message: str, level: str = "INFO"):
        """لاگ پیام"""
        if level == "INFO":
            self.logger.info(message)
        elif level == "SUCCESS":
            self.logger.info(f"✓ {message}")
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
    
    def check_python(self) -> bool:
        """بررسی نصب Python"""
        try:
            result = subprocess.run(
                [sys.executable, "--version"],
                capture_output=True,
                text=True
            )
            version = result.stdout.strip()
            self.log(f"Python found: {version}", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Python not found: {e}", "ERROR")
            return False
    
    def check_venv(self) -> bool:
        """بررسی محیط مجازی"""
        if VENV_DIR.exists():
            self.log("Virtual environment exists", "SUCCESS")
            return True
        else:
            self.log("Virtual environment not found", "WARNING")
            return False
    
    def create_venv(self):
        """ساخت محیط مجازی"""
        self.log("Creating virtual environment...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=True,
                capture_output=True,
                text=True
            )
            if VENV_DIR.exists():
                self.log("Virtual environment created", "SUCCESS")
                return True
            else:
                self.log("venv directory not created!", "ERROR")
                return False
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to create venv: {e}", "ERROR")
            return False
    
    def get_pip_path(self) -> Path:
        """دریافت مسیر pip"""
        if platform.system() == "Windows":
            return VENV_DIR / "Scripts" / "pip.exe"
        else:
            return VENV_DIR / "bin" / "pip"
    
    def get_python_path(self) -> Path:
        """دریافت مسیر Python در venv"""
        if platform.system() == "Windows":
            return VENV_DIR / "Scripts" / "python.exe"
        else:
            return VENV_DIR / "bin" / "python"
    
    def install_packages(self):
        """نصب پکیج‌ها"""
        pip_path = self.get_pip_path()
        
        if not pip_path.exists():
            self.log(f"pip not found at: {pip_path}", "ERROR")
            return False
        
        requirements = [
            PROJECT_DIR / "requirements.txt"
        ]
        
        for req_file in requirements:
            if not req_file.exists():
                self.log(f"Requirements file not found: {req_file}", "ERROR")
                continue
            
            self.log(f"Installing packages from {req_file.name}...")
            try:
                result = subprocess.run(
                    [str(pip_path), "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                self.log(f"Packages installed from {req_file.name}", "SUCCESS")
            except subprocess.CalledProcessError as e:
                self.log(f"Failed to install packages: {e}", "ERROR")
        
        return True
    
    def check_config(self) -> bool:
        """بررسی فایل config"""
        if not CONFIG_FILE.exists():
            self.log("config.env not found", "ERROR")
            return False
        
        required_keys = [
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
            "TELEGRAM_BOT_TOKEN"
        ]
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            
            missing = []
            for key in required_keys:
                if f"{key}=" not in content or f"{key}=\n" in content:
                    missing.append(key)
            
            if missing:
                self.log(f"Missing config: {', '.join(missing)}", "ERROR")
                return False
            
            self.log("Configuration valid", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"Failed to read config: {e}", "ERROR")
            return False
    
    def setup_venv(self):
        """راه‌اندازی محیط مجازی"""
        self.log("=== Setting up virtual environment ===")
        
        if not self.check_python():
            return False
        
        if not self.check_venv():
            if not self.create_venv():
                return False
        
        self.log("=== Virtual environment ready ===", "SUCCESS")
        return True
    
    def setup_packages(self):
        """نصب پکیج‌ها"""
        self.log("=== Installing packages ===")
        
        if not self.check_venv():
            self.log("Virtual environment not found! Run --venv first", "ERROR")
            return False
        
        self.install_packages()
        self.log("=== Packages installation complete ===", "SUCCESS")
        return True
    
    def run_bot(self):
        """اجرای ربات"""
        self.log("=== Starting Bot ===")
        
        if not self.check_venv():
            self.log("Virtual environment not found! Run --venv first", "ERROR")
            return False
        
        if not self.check_config():
            self.log("Configuration invalid! Please edit config.env", "ERROR")
            return False
        
        python_path = self.get_python_path()
        
        try:
            self.log("Bot is running... Press Ctrl+C to stop")
            bot_main = PROJECT_DIR / "src" / "main.py"
            subprocess.run(
                [str(python_path), str(bot_main)],
                cwd=str(PROJECT_DIR)
            )
        except KeyboardInterrupt:
            self.log("\n=== Bot stopped by user ===", "WARNING")
        except Exception as e:
            self.log(f"Bot error: {e}", "ERROR")
            return False
        
        return True


def main():
    """نقطه ورود اصلی"""
    
    # بررسی آرگومان‌های CLI
    if len(sys.argv) > 1:
        cli = LauncherCLI()
        
        if sys.argv[1] == "--venv":
            print("Setting up virtual environment...")
            success = cli.setup_venv()
            sys.exit(0 if success else 1)
        
        elif sys.argv[1] == "--pkg":
            print("Installing packages...")
            success = cli.setup_packages()
            sys.exit(0 if success else 1)
        
        elif sys.argv[1] == "--run":
            print("Starting bot...")
            success = cli.run_bot()
            sys.exit(0 if success else 1)
        
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Available commands: --venv, --pkg, --run")
            sys.exit(1)
    
    # GUI mode
    try:
        app = LauncherGUI()
        app.run()
    except KeyboardInterrupt:
        print("\n\nLauncher stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
