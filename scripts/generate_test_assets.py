"""
Generates synthetic, realistic social media screenshots & video clips for testing OCR
and multimodal investment tip auditing across India, Singapore, and Australia.
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT_DIR / "test_assets"

# Directories for each jurisdiction
DIR_IN = TEST_DIR / "india"
DIR_SG = TEST_DIR / "singapore"
DIR_AU = TEST_DIR / "australia"

for d in [DIR_IN, DIR_SG, DIR_AU]:
    d.mkdir(parents=True, exist_ok=True)


def get_font(size: int = 18, bold: bool = False):
    """Attempts to load a standard system font, falls back to default."""
    candidates = [
        "C:\\Windows\\Fonts\\segoeui.ttf" if not bold else "C:\\Windows\\Fonts\\segoeuib.ttf",
        "C:\\Windows\\Fonts\\arial.ttf" if not bold else "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf" if not bold else "C:\\Windows\\Fonts\\calibrib.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ==============================================================================
# 1. INDIA ASSETS
# ==============================================================================
def create_india_telegram_tip():
    """Multi-stock Telegram VIP screenshot (Adani Ent & Suzlon Energy) with Hinglish hype."""
    w, h = 800, 1000
    img = Image.new("RGB", (w, h), color="#17212b") # Telegram dark theme
    draw = ImageDraw.Draw(img)

    f_title = get_font(26, bold=True)
    f_sub = get_font(16)
    f_msg = get_font(20)
    f_msg_bold = get_font(21, bold=True)
    f_time = get_font(14)

    # Top Header Bar
    draw.rectangle([(0, 0), (w, 85)], fill="#0e1621")
    draw.text((30, 20), "DALAL STREET JACKPOT VIP 🚀", fill="#ffffff", font=f_title)
    draw.text((30, 55), "184,290 subscribers • @DalalStreet_Jackpot", fill="#6c7883", font=f_sub)

    # Message Bubble 1 - ADANIENT
    b1_top = 120
    draw.rounded_rectangle([(40, b1_top), (760, b1_top + 340)], radius=16, fill="#1e2c3a")
    draw.text((65, b1_top + 20), "🚨 OPERATOR BREAKOUT CALL 🚨", fill="#e65252", font=f_msg_bold)
    draw.text((65, b1_top + 60), "STOCK: ADANI ENTERPRISES (ADANIENT)", fill="#4fa3ff", font=f_msg_bold)
    draw.text((65, b1_top + 100), "ACTION: BUY | CMP: 2720", fill="#4cd964", font=f_msg_bold)
    draw.text((65, b1_top + 140), "TARGET: ₹3,800.00 (Target in 14 days)", fill="#ffcc00", font=f_msg_bold)
    draw.text((65, b1_top + 180), "STOPLOSS: ₹2,600", fill="#ffffff", font=f_msg)
    draw.text((65, b1_top + 225), "🔥 100% Sure-Shot Profit Pakka!", fill="#ff9900", font=f_msg_bold)
    draw.text((65, b1_top + 265), "Big operator entry confirmed! Don't miss this rocket move!", fill="#dcdfe4", font=f_msg)
    draw.text((680, b1_top + 305), "09:42 AM", fill="#6c7883", font=f_time)

    # Message Bubble 2 - SUZLON
    b2_top = 490
    draw.rounded_rectangle([(40, b2_top), (760, b2_top + 340)], radius=16, fill="#1e2c3a")
    draw.text((65, b2_top + 20), "⚡ SECOND JACKPOT STOCK FOR TODAY ⚡", fill="#00d4ff", font=f_msg_bold)
    draw.text((65, b2_top + 60), "STOCK: SUZLON ENERGY (SUZLON)", fill="#4fa3ff", font=f_msg_bold)
    draw.text((65, b2_top + 100), "ACTION: STRONG BUY | CURRENT PRICE: ₹58", fill="#4cd964", font=f_msg_bold)
    draw.text((65, b2_top + 140), "TARGET: ₹95.00 (Short term / 10 days)", fill="#ffcc00", font=f_msg_bold)
    draw.text((65, b2_top + 180), "GAIN POTENTIAL: +65% Guaranteed return!", fill="#ff3b30", font=f_msg_bold)
    draw.text((65, b2_top + 225), "Join Premium VIP Telegram group for daily 10x multibaggers!", fill="#ffffff", font=f_msg)
    draw.text((65, b2_top + 265), "Disclosed: Not SEBI registered / For educational purpose 😉", fill="#8e9ba8", font=f_sub)
    draw.text((680, b2_top + 305), "09:45 AM", fill="#6c7883", font=f_time)

    out_path = DIR_IN / "telegram_adanient_suzlon_tip.png"
    img.save(out_path, quality=95)
    print(f"Created India Image 1: {out_path.name}")


def create_india_whatsapp_zomato_tip():
    """WhatsApp chat screenshot promoting Zomato (Eternal) with 1-day urgency."""
    w, h = 800, 700
    img = Image.new("RGB", (w, h), color="#0b141a") # WhatsApp dark background
    draw = ImageDraw.Draw(img)

    f_title = get_font(24, bold=True)
    f_sub = get_font(15)
    f_msg = get_font(21)
    f_msg_bold = get_font(22, bold=True)
    f_time = get_font(13)

    # Header
    draw.rectangle([(0, 0), (w, 80)], fill="#1f2c34")
    draw.text((30, 25), "📈 Intraday Stock Hunters 🎯", fill="#e9edef", font=f_title)

    # Message Bubble
    b_top = 110
    draw.rounded_rectangle([(40, b_top), (760, b_top + 450)], radius=14, fill="#005c4b") # WhatsApp outgoing green bubble
    draw.text((60, b_top + 20), "Forwarded many times", fill="#8696a0", font=f_sub)
    draw.text((60, b_top + 60), "🚀 TOMORROW'S UPPER CIRCUIT BLAST!", fill="#ffd700", font=f_msg_bold)
    draw.text((60, b_top + 110), "Company: ZOMATO (Eternal Limited)", fill="#ffffff", font=f_msg_bold)
    draw.text((60, b_top + 155), "Ticker: ZOMATO.NS", fill="#70dbb8", font=f_msg_bold)
    draw.text((60, b_top + 200), "Current Market Price: ₹316", fill="#ffffff", font=f_msg)
    draw.text((60, b_top + 245), "Target Price: ₹350.00 (1 Day Horizon / Tomorrow)", fill="#ffff66", font=f_msg_bold)
    draw.text((60, b_top + 295), "Claimed Move: +11% Guaranteed Upper Circuit!", fill="#ff6b6b", font=f_msg_bold)
    draw.text((60, b_top + 345), "Abhi kharido! Last chance before market opens tomorrow!", fill="#ffffff", font=f_msg)
    draw.text((60, b_top + 395), "Shared by @StockWhiz_ZeeAnalyst", fill="#8696a0", font=f_sub)
    draw.text((680, b_top + 415), "10:14 PM ✓✓", fill="#8696a0", font=f_time)

    out_path = DIR_IN / "whatsapp_zomato_tip.png"
    img.save(out_path, quality=95)
    print(f"Created India Image 2: {out_path.name}")


def create_india_video_clip():
    """Generates an MP4 video clip featuring Reliance Industries and TCS with animated overlays."""
    out_path = DIR_IN / "video_reliance_tcs_breakout.mp4"
    w, h = 1280, 720
    fps = 24
    seconds = 5
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

    # Base Frame using PIL
    for i in range(fps * seconds):
        img = Image.new("RGB", (w, h), color="#0f172a")
        draw = ImageDraw.Draw(img)

        # Pulsing color accent
        pulse = int(180 + 75 * np.sin(i / 10.0))
        draw.rectangle([(0, 0), (w, 90)], fill="#020617")
        draw.text((40, 25), "⚡ DALAL STREET BREAKOUT RADAR (LIVE TIP) ⚡", fill=(255, pulse, 50), font=get_font(28, bold=True))

        # Stock 1 Card: RELIANCE.NS
        draw.rounded_rectangle([(60, 130), (600, 620)], radius=20, fill="#1e293b", outline="#3b82f6", width=2)
        draw.text((90, 160), "RELIANCE INDUSTRIES (RELIANCE.NS)", fill="#60a5fa", font=get_font(22, bold=True))
        draw.text((90, 220), "Current Price: ₹1,175", fill="#94a3b8", font=get_font(20))
        draw.text((90, 270), "Target Price: ₹1,850.00", fill="#4ade80", font=get_font(24, bold=True))
        draw.text((90, 330), "Horizon: 30 Days (+57% Move)", fill="#fbbf24", font=get_font(20, bold=True))
        draw.text((90, 390), "🔥 100% Sure-Shot Mega Call", fill="#f87171", font=get_font(20, bold=True))
        draw.text((90, 450), "Heavy institutional delivery spike!", fill="#cbd5e1", font=get_font(18))
        draw.text((90, 540), "Source: @FinGuru_India", fill="#64748b", font=get_font(16))

        # Stock 2 Card: TCS.NS
        draw.rounded_rectangle([(680, 130), (1220, 620)], radius=20, fill="#1e293b", outline="#10b981", width=2)
        draw.text((710, 160), "TCS LIMITED (TCS.NS)", fill="#34d399", font=get_font(22, bold=True))
        draw.text((710, 220), "Current Price: ₹3,010", fill="#94a3b8", font=get_font(20))
        draw.text((710, 270), "Target Price: ₹4,800.00", fill="#4ade80", font=get_font(24, bold=True))
        draw.text((710, 330), "Horizon: 45 Days (+59% Move)", fill="#fbbf24", font=get_font(20, bold=True))
        draw.text((710, 390), "🚀 Breakout to the Moon Guaranteed", fill="#f87171", font=get_font(20, bold=True))
        draw.text((710, 450), "AI mega-contracts won! Buy today!", fill="#cbd5e1", font=get_font(18))
        draw.text((710, 540), "Source: @FinGuru_India", fill="#64748b", font=get_font(16))

        # Ticker Banner at bottom
        draw.rectangle([(0, 650), (w, h)], fill="#020617")
        offset = (i * 8) % w
        draw.text((w - offset, 665), "ALERT: JOIN VIP TELEGRAM FOR INSIDER PUMP NOTICES • NOT SEBI REGISTERED • NO RISK ZERO RISK •", fill="#e2e8f0", font=get_font(18, bold=True))

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        out.write(frame)

    out.release()
    print(f"Created India Video: {out_path.name}")


# ==============================================================================
# 2. SINGAPORE ASSETS
# ==============================================================================
def create_singapore_telegram_tip():
    """Multi-stock Singapore tip screenshot: DBS (D05.SI) & Singtel (Z74.SI)."""
    w, h = 800, 950
    img = Image.new("RGB", (w, h), color="#1b1e2b")
    draw = ImageDraw.Draw(img)

    f_title = get_font(26, bold=True)
    f_sub = get_font(16)
    f_msg = get_font(20)
    f_msg_bold = get_font(21, bold=True)
    f_time = get_font(14)

    # Header
    draw.rectangle([(0, 0), (w, 85)], fill="#11131c")
    draw.text((30, 20), "🦁 SGX ALPHA TRADERS (VIP CHAT)", fill="#ffffff", font=f_title)
    draw.text((30, 55), "Singapore Community • @SGX_Insider_Desk", fill="#758296", font=f_sub)

    # Bubble 1 - DBS Bank (D05.SI)
    b1_top = 110
    draw.rounded_rectangle([(40, b1_top), (760, b1_top + 350)], radius=16, fill="#232738")
    draw.text((65, b1_top + 20), "🇸🇬 BLUE CHIP DIVIDEND SURGE CALL 🇸🇬", fill="#00e5ff", font=f_msg_bold)
    draw.text((65, b1_top + 65), "Ticker: DBS GROUP HOLDINGS (D05.SI)", fill="#4fa3ff", font=f_msg_bold)
    draw.text((65, b1_top + 110), "Action: STRONG BUY | Entry: SGD 44.50", fill="#4cd964", font=f_msg_bold)
    draw.text((65, b1_top + 155), "Target Price: SGD 58.00 (Target in 30 days)", fill="#ffd700", font=f_msg_bold)
    draw.text((65, b1_top + 200), "Expected Move: +30% Guaranteed Return before Ex-Date!", fill="#ff5252", font=f_msg_bold)
    draw.text((65, b1_top + 245), "Special dividend pump confirmed by institutional desk.", fill="#d8e2ec", font=f_msg)
    draw.text((65, b1_top + 290), "⚠️ Unregulated Singapore Tip Group - Not MAS Licensed", fill="#9aa8ba", font=f_sub)
    draw.text((680, b1_top + 315), "14:15", fill="#758296", font=f_time)

    # Bubble 2 - Singtel (Z74.SI)
    b2_top = 490
    draw.rounded_rectangle([(40, b2_top), (760, b2_top + 350)], radius=16, fill="#232738")
    draw.text((65, b2_top + 20), "📡 5G BREAKOUT ROCKET ALERT 📡", fill="#ff9900", font=f_msg_bold)
    draw.text((65, b2_top + 65), "Ticker: SINGTEL (Z74.SI)", fill="#4fa3ff", font=f_msg_bold)
    draw.text((65, b2_top + 110), "Action: BUY | CMP: SGD 3.20", fill="#4cd964", font=f_msg_bold)
    draw.text((65, b2_top + 155), "Target Price: SGD 4.80 (21 Days Horizon)", fill="#ffd700", font=f_msg_bold)
    draw.text((65, b2_top + 200), "Claimed Profit: +50% sure-shot gain!", fill="#ff5252", font=f_msg_bold)
    draw.text((65, b2_top + 245), "Major asset monetization announcement leaking soon!", fill="#d8e2ec", font=f_msg)
    draw.text((65, b2_top + 290), "Join our private VIP channel for SGX jackpot tips!", fill="#ffffff", font=f_msg)
    draw.text((680, b2_top + 315), "14:20", fill="#758296", font=f_time)

    out_path = DIR_SG / "telegram_dbs_singtel_tip.png"
    img.save(out_path, quality=95)
    print(f"Created Singapore Image: {out_path.name}")


def create_singapore_video_clip():
    """Generates an MP4 video clip for Singapore Airlines (C6L.SI)."""
    out_path = DIR_SG / "video_singapore_airlines.mp4"
    w, h = 1280, 720
    fps = 24
    seconds = 5
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

    for i in range(fps * seconds):
        img = Image.new("RGB", (w, h), color="#091428")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (w, 90)], fill="#040b17")
        draw.text((40, 25), "✈️ SGX BREAKOUT WATCH: SINGAPORE AIRLINES ✈️", fill="#38bdf8", font=get_font(28, bold=True))

        # Main Card
        draw.rounded_rectangle([(140, 130), (1140, 620)], radius=24, fill="#112240", outline="#0284c7", width=3)
        draw.text((180, 170), "STOCK: SINGAPORE AIRLINES (C6L.SI)", fill="#67e8f9", font=get_font(28, bold=True))
        draw.text((180, 235), "Current Price: SGD $6.45", fill="#cbd5e1", font=get_font(22))
        draw.text((180, 290), "TARGET PRICE: SGD $9.50.00", fill="#4ade80", font=get_font(30, bold=True))
        draw.text((180, 355), "TIME HORIZON: 14 Days (+47% Surge Claimed)", fill="#facc15", font=get_font(24, bold=True))
        draw.text((180, 420), "🔥 Guaranteed 100% Sure-Shot Travel Boom Trade!", fill="#f87171", font=get_font(24, bold=True))
        draw.text((180, 480), "Record earnings & dividend surge! Buy before tomorrow!", fill="#e2e8f0", font=get_font(20))
        draw.text((180, 550), "Creator: @SG_MarketGuru • Not MAS Registered", fill="#94a3b8", font=get_font(18))

        # Bottom Bar
        draw.rectangle([(0, 660), (w, h)], fill="#040b17")
        offset = (i * 7) % w
        draw.text((w - offset, 675), "SINGAPORE AIRLINES C6L.SI • BUY NOW • LIMITED TIME WINDOW • OPERATOR SURGE DETECTED •", fill="#e2e8f0", font=get_font(18, bold=True))

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        out.write(frame)

    out.release()
    print(f"Created Singapore Video: {out_path.name}")


# ==============================================================================
# 3. AUSTRALIA ASSETS
# ==============================================================================
def create_australia_discord_tip():
    """Discord dark-theme screenshot promoting BHP Group & Pilbara Minerals."""
    w, h = 800, 950
    img = Image.new("RGB", (w, h), color="#313338") # Discord dark theme
    draw = ImageDraw.Draw(img)

    f_title = get_font(24, bold=True)
    f_sub = get_font(15)
    f_msg = get_font(20)
    f_msg_bold = get_font(21, bold=True)
    f_time = get_font(13)

    # Discord Channel Header
    draw.rectangle([(0, 0), (w, 80)], fill="#2b2d31")
    draw.text((30, 25), "# 🦘-asx-pump-alerts-vip", fill="#ffffff", font=f_title)
    draw.text((380, 28), "ASX 200 Multi-Baggers & Tips", fill="#949ba4", font=f_sub)

    # Post 1 - BHP (BHP.AX)
    b1_top = 110
    draw.rounded_rectangle([(40, b1_top), (760, b1_top + 340)], radius=12, fill="#2b2d31")
    draw.text((65, b1_top + 20), "AussieTrades_Admin — Today at 10:18 AM", fill="#f2f3f5", font=f_msg_bold)
    draw.text((65, b1_top + 60), "🇦🇺 ASX BLUE CHIP SQUEEZE: BHP GROUP (BHP.AX)", fill="#e5c07b", font=f_msg_bold)
    draw.text((65, b1_top + 105), "Action: IMMEDIATE BUY | Price: AUD $41.50", fill="#57f287", font=f_msg_bold)
    draw.text((65, b1_top + 150), "Target Price: AUD $58.00 (20 Days Horizon)", fill="#fee75c", font=f_msg_bold)
    draw.text((65, b1_top + 195), "Move: +40% Guaranteed gain before mining summit!", fill="#ed4245", font=f_msg_bold)
    draw.text((65, b1_top + 240), "Chinese copper stimulus unlocked! Sure-shot breakout!", fill="#dbdee1", font=f_msg)
    draw.text((65, b1_top + 285), "⚠️ Unlicensed financial tip channel • Subject to ASIC scrutiny", fill="#949ba4", font=f_sub)

    # Post 2 - PLS (PLS.AX)
    b2_top = 480
    draw.rounded_rectangle([(40, b2_top), (760, b2_top + 350)], radius=12, fill="#2b2d31")
    draw.text((65, b2_top + 20), "AussieTrades_Admin — Today at 10:25 AM", fill="#f2f3f5", font=f_msg_bold)
    draw.text((65, b2_top + 60), "🚀 10X MULTIBAGGER LITHIUM ROCKET: PILBARA MINERALS (PLS.AX)", fill="#eb459e", font=f_msg_bold)
    draw.text((65, b2_top + 105), "Action: STRONG BUY | Entry: AUD $2.85", fill="#57f287", font=f_msg_bold)
    draw.text((65, b2_top + 150), "Target Price: AUD $5.50 (Target in 14 days)", fill="#fee75c", font=f_msg_bold)
    draw.text((65, b2_top + 195), "Potential: +93% Move! Lithium to the moon! 100% sure-shot!", fill="#ed4245", font=f_msg_bold)
    draw.text((65, b2_top + 240), "Short squeeze imminent! Join our paid Discord VIP tier!", fill="#dbdee1", font=f_msg)
    draw.text((65, b2_top + 290), "Disclose: DYOR / Not financial advice fig leaf disclaimer", fill="#949ba4", font=f_sub)

    out_path = DIR_AU / "discord_bhp_pilbara_tip.png"
    img.save(out_path, quality=95)
    print(f"Created Australia Image: {out_path.name}")


def create_australia_video_clip():
    """Generates an MP4 video clip for Commonwealth Bank of Australia (CBA.AX)."""
    out_path = DIR_AU / "video_cba_bank_alert.mp4"
    w, h = 1280, 720
    fps = 24
    seconds = 5
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

    for i in range(fps * seconds):
        img = Image.new("RGB", (w, h), color="#18181b")
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (w, 90)], fill="#09090b")
        draw.text((40, 25), "🦘 ASX 200 ALERT: COMMONWEALTH BANK OF AUSTRALIA 🦘", fill="#facc15", font=get_font(26, bold=True))

        # Main Card
        draw.rounded_rectangle([(140, 130), (1140, 620)], radius=24, fill="#27272a", outline="#eab308", width=3)
        draw.text((180, 170), "STOCK: COMMONWEALTH BANK (CBA.AX)", fill="#fde047", font=get_font(28, bold=True))
        draw.text((180, 235), "Current Trading Price: AUD $142.50", fill="#d4d4d8", font=get_font(22))
        draw.text((180, 290), "TARGET PRICE: AUD $190.00", fill="#4ade80", font=get_font(30, bold=True))
        draw.text((180, 355), "TIME HORIZON: 30 Days (+33% Move)", fill="#fb923c", font=get_font(24, bold=True))
        draw.text((180, 420), "⚡ 100% Sure-Shot Profit! Operator Volume Confirmed!", fill="#ef4444", font=get_font(24, bold=True))
        draw.text((180, 480), "Buy before tomorrow's rate cut announcement!", fill="#f4f4f5", font=get_font(20))
        draw.text((180, 550), "Source: @AussieFinfluencer • Unlicensed tip provider", fill="#a1a1aa", font=get_font(18))

        # Bottom Bar
        draw.rectangle([(0, 660), (w, h)], fill="#09090b")
        offset = (i * 7) % w
        draw.text((w - offset, 675), "CBA.AX TO THE MOON • SURE-SHOT • GUARANTEED PROFIT • JOIN VIP DISCORD •", fill="#fef08a", font=get_font(18, bold=True))

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        out.write(frame)

    out.release()
    print(f"Created Australia Video: {out_path.name}")


if __name__ == "__main__":
    print("Generating OCR and Multimodal Test Assets...")
    create_india_telegram_tip()
    create_india_whatsapp_zomato_tip()
    create_india_video_clip()
    create_singapore_telegram_tip()
    create_singapore_video_clip()
    create_australia_discord_tip()
    create_australia_video_clip()
    print("\nAll test assets successfully created in test_assets/!")
