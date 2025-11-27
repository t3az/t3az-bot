import threading
import os

# Bot'u çalıştıran fonksiyon
def run_bot():
    os.system("python bot.py")

# Web servisini çalıştıran fonksiyon
def run_web():
    os.system("python web.py")

# İki programı aynı anda çalıştır
if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    run_web()
