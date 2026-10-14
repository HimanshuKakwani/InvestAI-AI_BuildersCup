"""Matplotlib Chart Generator for InvestPI PDF Reports."""
import io
import base64
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def generate_price_target_chart(
    prices_df: Optional[pd.DataFrame],
    ticker: str,
    target_price: Optional[float] = None,
    current_price: Optional[float] = None
) -> Optional[str]:
    """
    Generates a high-contrast 5-year historical price chart with the influencer's
    claimed target price overlaid as an empirical reference line.
    Returns: Base64-encoded PNG image string or None.
    """
    if prices_df is None or prices_df.empty or "Close" not in prices_df.columns:
        return None

    try:
        fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=150)
        fig.patch.set_facecolor("#0f172a") # Slate-900 background
        ax.set_facecolor("#0f172a")

        # Plot 5-year closing prices
        ax.plot(prices_df.index, prices_df["Close"], color="#38bdf8", linewidth=1.8, label=f"{ticker} 5-Yr Price")

        # Current Price Line
        if current_price:
            ax.axhline(current_price, color="#94a3b8", linestyle="--", linewidth=1.0, label=f"Current: {current_price:.1f}")

        # Claimed Target Line
        if target_price:
            ax.axhline(target_price, color="#f43f5e", linestyle="-.", linewidth=1.5, label=f"Claimed Target: {target_price:.1f}")

        # Format axes
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(colors="#94a3b8", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#334155")
        ax.grid(True, linestyle=":", alpha=0.3, color="#64748b")

        ax.set_title(f"{ticker} — 5-Year Empirical Historical Price vs Claimed Target", color="#f8fafc", fontsize=10, fontweight="bold", pad=10)
        ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc", fontsize=8, loc="upper left")

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None
