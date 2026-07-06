"""
AI Assistant Service.

Architecture:
- We inject real user data (balance, transactions, withdrawals) into
  the AI prompt as context before every request.
- This means the AI always responds with the user's ACTUAL data,
  not hallucinated numbers.
- If AI is disabled or API key is missing, we return rule-based
  responses so the platform never breaks.
"""

from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.models.user import User
from app.models.wallet import Wallet, Transaction
from app.models.withdrawal import Withdrawal
from app.models.fx import FXConversion
from app.services.fx_service import MOCK_INTERBANK_RATES, CURRENCY_SYMBOLS


def get_ai_client() -> Optional[OpenAI]:
    """
    Initialize AI client.
    Returns None if AI is disabled or key is missing.
    """
    if not settings.AI_ENABLED or not settings.AI_API_KEY:
        return None

    return OpenAI(
        api_key=settings.AI_API_KEY,
        base_url=settings.AI_BASE_URL
    )


def get_live_ngn_rate() -> Decimal:
    """
    Get live NGN rate. Falls back to mock if API fails.
    """
    try:
        from app.providers.fx_provider import get_live_rate
        rate = get_live_rate("NGN")
        if rate and rate > Decimal("0"):
            return rate
    except Exception:
        pass
    return MOCK_INTERBANK_RATES.get("NGN", Decimal("1595"))


def build_user_context(db: Session, user: User) -> str:
    """
    Build a detailed context string about the user's financial state.
    This gets injected into every AI prompt so responses are personalized
    and grounded in real data — not hallucinations.
    """
    # Get wallet
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    balance = wallet.balance if wallet else Decimal("0.00")

    # Get recent transactions (last 10)
    recent_transactions = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id
    ).order_by(
        Transaction.created_at.desc()
    ).limit(10).all() if wallet else []

    # Get recent withdrawals (last 5)
    recent_withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id
    ).order_by(
        Withdrawal.created_at.desc()
    ).limit(5).all()

    # Get FX conversions (last 5)
    recent_fx = db.query(FXConversion).filter(
        FXConversion.user_id == user.id
    ).order_by(
        FXConversion.created_at.desc()
    ).limit(5).all()

    # Calculate totals
    total_deposited = sum(
        t.amount for t in recent_transactions
        if t.transaction_type == "credit" and t.category == "deposit"
    )
    total_withdrawn = sum(
        t.amount for t in recent_transactions
        if t.transaction_type == "debit" and t.category == "withdrawal"
    )

    # Get live NGN rate
    ngn_rate = get_live_ngn_rate()

    # Build context string
    context = f"""
USER FINANCIAL PROFILE:
- Name: {user.full_name}
- Country: {user.country or "Not set"}
- Business Type: {user.business_type or "Not set"}
- KYC Verified: {"Yes" if user.is_kyc_verified else "No"}

WALLET STATUS:
- Current Balance: ${balance:.2f} USD
- Total Deposited (recent): ${total_deposited:.2f} USD
- Total Withdrawn (recent): ${total_withdrawn:.2f} USD

RECENT TRANSACTIONS (last 10):
"""
    for t in recent_transactions:
        context += (
            f"- {t.created_at.strftime('%Y-%m-%d')} | "
            f"{t.transaction_type.upper()} | "
            f"${t.amount:.2f} | "
            f"{t.category} | "
            f"{t.description}\n"
        )

    context += "\nRECENT WITHDRAWALS (last 5):\n"
    for w in recent_withdrawals:
        context += (
            f"- {w.created_at.strftime('%Y-%m-%d')} | "
            f"${w.amount:.2f} via {w.provider} to {w.bank_name} | "
            f"Status: {w.status} | "
            f"Delivery: {w.estimated_delivery}\n"
        )

    context += "\nRECENT FX CONVERSIONS (last 5):\n"
    for fx in recent_fx:
        symbol = CURRENCY_SYMBOLS.get(fx.to_currency, "")
        context += (
            f"- {fx.created_at.strftime('%Y-%m-%d')} | "
            f"${fx.from_amount:.2f} USD → "
            f"{symbol}{fx.to_amount:.2f} {fx.to_currency} | "
            f"Rate: {fx.platform_rate}\n"
        )

    context += f"\nCURRENT LIVE FX RATES (USD to African currencies):\n"
    context += f"- 1 USD = ₦{ngn_rate:,.2f} NGN (live rate)\n"
    for currency, rate in MOCK_INTERBANK_RATES.items():
        if currency != "NGN":
            symbol = CURRENCY_SYMBOLS.get(currency, "")
            context += f"- 1 USD = {symbol}{rate} {currency}\n"

    return context


def get_system_prompt(user_context: str) -> str:
    """
    The system prompt that defines the AI personality and rules.
    """
    return f"""You are PayBot, an intelligent financial assistant for an African fintech platform 
that provides USD virtual accounts and cross-border payments for African creators, 
Amazon KDP authors, and freelancers.

YOUR PERSONALITY:
- Friendly, clear, and professional
- You understand the challenges African freelancers face with payments
- You speak plainly — no confusing financial jargon
- You are honest about fees and delivery times
- You always give actionable advice

YOUR CAPABILITIES:
- Analyze the user's transaction history and wallet balance
- Recommend best withdrawal timing and providers
- Explain FX rates and how the platform makes money (spreads)
- Help users understand their payment patterns
- Flag if something looks unusual
- Give tips on maximizing earnings from Amazon KDP, Upwork, Fiverr

YOUR RULES:
- NEVER make up numbers — only use the data provided in the user context
- NEVER promise specific exchange rates (they change)
- ALWAYS recommend the user verify important financial decisions
- If you don't know something, say so clearly
- Keep responses concise — under 200 words unless a detailed breakdown is requested
- Format responses clearly with bullet points when listing multiple items
- NEVER expose or mention any API endpoint paths in your responses
- Always refer to platform features by their name (Wallet, Withdraw, FX Convert, Virtual Account) not by technical paths

AVAILABLE PROVIDERS ON THIS PLATFORM:
- Grey: Best for NGN/GHS/KES, 1-3 hours
- Chipper Cash: Fastest for small amounts, instant to 30 mins
- Flutterwave: Wide African coverage, 15 mins to 2 hours
- LemFi: Good NGN rates, 1-2 hours
- Wise: Best for large global transfers, cheapest percentage fee
- Wire Transfer: Most reliable for large amounts, same day
- ACH: Cheapest for US banks, 2-3 business days

USER CURRENT FINANCIAL DATA:
{user_context}

Always reference the user's actual data when giving advice.
Start responses warmly but get to the point quickly.
Never mention API paths, endpoints, or technical URLs in any response."""


def chat_with_ai(
    db: Session,
    user: User,
    message: str,
    conversation_history: list = None
) -> str:
    """
    Main chat function. Sends user message to AI with full context.
    Falls back to rule-based response if AI is unavailable.
    """
    client = get_ai_client()

    # Build user context
    user_context = build_user_context(db, user)
    system_prompt = get_system_prompt(user_context)

    # If AI is not configured, use rule-based fallback
    if not client:
        return generate_fallback_response(message, user, db)

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history if provided (for multi-turn chat)
    if conversation_history:
        for msg in conversation_history[-6:]:  # last 6 messages only to save tokens
            messages.append(msg)

    # Add current message
    messages.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception:
        # Never crash the app because AI failed — use fallback
        return generate_fallback_response(message, user, db)


def generate_insights(db: Session, user: User) -> dict:
    """
    Generate automatic financial insights for the user's dashboard.
    These are always generated — with or without AI.
    """
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    balance = wallet.balance if wallet else Decimal("0.00")

    # Get all transactions
    transactions = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id
    ).order_by(Transaction.created_at.desc()).limit(50).all() if wallet else []

    # Get all withdrawals
    withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id
    ).all()

    # Calculate metrics
    total_credits = sum(t.amount for t in transactions if t.transaction_type == "credit")
    total_debits = sum(t.amount for t in transactions if t.transaction_type == "debit")
    total_fees_paid = sum(w.fee for w in withdrawals)
    total_withdrawals = len(withdrawals)

    # Most used provider
    provider_counts = {}
    for w in withdrawals:
        provider_counts[w.provider] = provider_counts.get(w.provider, 0) + 1
    most_used_provider = (
        max(provider_counts, key=provider_counts.get)
        if provider_counts
        else "None yet"
    )

    # Get live NGN rate
    ngn_rate = get_live_ngn_rate()

    # Build insights
    insights = []

    # Balance insight
    if balance > Decimal("1000"):
        insights.append({
            "type": "info",
            "title": "Strong Balance",
            "message": (
                f"You have ${balance:.2f} available. "
                f"Consider withdrawing to take advantage of current FX rates."
            )
        })
    elif balance < Decimal("10") and balance > Decimal("0"):
        insights.append({
            "type": "warning",
            "title": "Low Balance",
            "message": (
                f"Your balance is ${balance:.2f}. "
                f"You may want to deposit more funds soon."
            )
        })

    # Live NGN rate insight
    if ngn_rate > Decimal("1500"):
        insights.append({
            "type": "opportunity",
            "title": "Good NGN Rate",
            "message": (
                f"Current live USD/NGN rate is ₦{ngn_rate:,.2f}. "
                f"This is a good time to convert or withdraw to Nigeria."
            )
        })

    # Fee insight
    if total_fees_paid > Decimal("50"):
        insights.append({
            "type": "tip",
            "title": "Save on Fees",
            "message": (
                f"You have paid ${total_fees_paid:.2f} in fees. "
                f"Consolidating withdrawals into fewer larger transfers "
                f"can reduce your total fees."
            )
        })

    # KYC insight
    if not user.is_kyc_verified:
        insights.append({
            "type": "action",
            "title": "Complete KYC",
            "message": (
                "Your account is not KYC verified. "
                "Complete verification to unlock higher withdrawal limits "
                "and faster processing."
            )
        })

    # No withdrawals yet
    if total_withdrawals == 0:
        insights.append({
            "type": "info",
            "title": "No Withdrawals Yet",
            "message": (
                "You have not made any withdrawals yet. "
                "When you are ready, we will automatically pick the best "
                "provider for your country."
            )
        })

    return {
        "balance": balance,
        "total_money_in": total_credits,
        "total_money_out": total_debits,
        "total_fees_paid": total_fees_paid,
        "total_withdrawals": total_withdrawals,
        "most_used_provider": most_used_provider,
        "current_ngn_rate": ngn_rate,
        "insights": insights,
    }


def generate_monthly_summary(db: Session, user: User) -> dict:
    """
    Generate a plain English monthly summary of the user's activity.
    """
    from datetime import datetime, timezone
    from sqlalchemy import extract

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    now = datetime.now(timezone.utc)

    if not wallet:
        return {
            "month": now.strftime("%B %Y"),
            "summary": "No activity yet. Make your first deposit to get started.",
            "stats": {}
        }

    # This month's transactions
    monthly_transactions = db.query(Transaction).filter(
        Transaction.wallet_id == wallet.id,
        extract("month", Transaction.created_at) == now.month,
        extract("year", Transaction.created_at) == now.year
    ).all()

    monthly_withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == user.id,
        extract("month", Withdrawal.created_at) == now.month,
        extract("year", Withdrawal.created_at) == now.year
    ).all()

    monthly_in = sum(
        t.amount for t in monthly_transactions
        if t.transaction_type == "credit"
    )
    monthly_out = sum(
        t.amount for t in monthly_transactions
        if t.transaction_type == "debit"
    )
    monthly_fees = sum(w.fee for w in monthly_withdrawals)

    summary_text = (
        f"In {now.strftime('%B %Y')}, you received ${monthly_in:.2f} "
        f"and withdrew ${monthly_out:.2f}. "
    )

    if monthly_fees > 0:
        summary_text += f"You paid ${monthly_fees:.2f} in transfer fees. "

    if monthly_withdrawals:
        providers_used = list(set(w.provider for w in monthly_withdrawals))
        summary_text += (
            f"You used {', '.join(providers_used)} for your payouts. "
        )

    if monthly_in > monthly_out:
        summary_text += (
            f"Your net savings this month: ${(monthly_in - monthly_out):.2f}."
        )
    elif monthly_out > monthly_in:
        summary_text += "You withdrew more than you received this month."

    return {
        "month": now.strftime("%B %Y"),
        "summary": summary_text,
        "stats": {
            "total_received": monthly_in,
            "total_withdrawn": monthly_out,
            "total_fees": monthly_fees,
            "transaction_count": len(monthly_transactions),
            "withdrawal_count": len(monthly_withdrawals),
        }
    }


def generate_fallback_response(message: str, user: User, db: Session) -> str:
    """
    Rule-based responses when AI API is not available.
    This ensures the platform never breaks even without an AI key.
    Never expose API paths or technical endpoints in responses.
    """
    message_lower = message.lower()

    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    balance = wallet.balance if wallet else Decimal("0.00")

    # Get live NGN rate
    ngn_rate = get_live_ngn_rate()

    # Balance questions
    if any(word in message_lower for word in [
        "balance", "how much do i have", "how much money", "my money"
    ]):
        return (
            f"Hi {user.full_name.split()[0]}! "
            f"Your current wallet balance is ${balance:.2f} USD. "
            f"You can deposit more funds or initiate a withdrawal anytime "
            f"from your dashboard."
        )

    # Fee and cost questions
    if any(word in message_lower for word in [
        "fee", "fees", "charge", "charges", "cost", "costs",
        "how much does it", "how much will it", "how much to withdraw",
        "how much to send", "what does it cost", "pricing", "price"
    ]):
        return (
            f"Here is a breakdown of our withdrawal fees:\n\n"
            f"🔹 Chipper Cash — 1.3% (fastest, instant to 30 mins)\n"
            f"🔹 Grey — 1.0% (best NGN/GHS/KES rate, 1-3 hours)\n"
            f"🔹 LemFi — 1.5% (good for Nigeria/Ghana/Kenya, 1-2 hours)\n"
            f"🔹 Flutterwave — 1.4% + $1.50 flat (wide African coverage)\n"
            f"🔹 Wise — 0.65% (cheapest for large global transfers)\n"
            f"🔹 Wire Transfer — flat $25 (best for amounts above $5,000)\n"
            f"🔹 ACH — 0.8% + $0.25 (US banks only, 2-3 business days)\n\n"
            f"The routing engine automatically picks the cheapest and fastest "
            f"option for your country. For Nigeria, amounts under $500 go via "
            f"Chipper Cash and amounts $500-$5,000 go via Grey."
        )

    # Withdrawal questions
    if any(word in message_lower for word in [
        "withdraw", "send money", "payout", "transfer money",
        "how do i withdraw", "how to withdraw", "send to bank"
    ]):
        return (
            f"To withdraw funds from your PayFlow wallet:\n\n"
            f"1️⃣ Click Withdraw in the left menu\n"
            f"2️⃣ Enter the amount you want to send in USD\n"
            f"3️⃣ Select your destination country\n"
            f"4️⃣ Our system automatically picks the best provider\n"
            f"5️⃣ Enter your bank name and account number\n"
            f"6️⃣ Your account name will be verified automatically\n"
            f"7️⃣ Confirm the withdrawal\n\n"
            f"Your current balance is ${balance:.2f} USD. "
            f"For Nigeria, we recommend Grey (1-3 hours) or "
            f"Chipper Cash (instant for amounts under $500)."
        )

    # FX rate questions — uses live rate
    if any(word in message_lower for word in [
        "rate", "exchange", "ngn", "naira", "cedi", "ghs",
        "convert", "conversion", "dollar to", "usd to"
    ]):
        platform_ngn = ngn_rate * Decimal("0.985")
        return (
            f"Current platform FX rates (includes 1.5% platform fee):\n\n"
            f"🇳🇬 USD/NGN — ₦{platform_ngn:,.2f} per $1 "
            f"(live mid-market: ₦{ngn_rate:,.2f})\n\n"
            f"Use the FX Convert section in your dashboard to get an exact "
            f"quote before converting. Rates are refreshed every 5 minutes."
        )

    # Amazon KDP questions
    if any(word in message_lower for word in [
        "kdp", "amazon", "royalt", "kindle", "book"
    ]):
        return (
            f"To receive Amazon KDP royalties:\n\n"
            f"1️⃣ Log in to kdp.amazon.com\n"
            f"2️⃣ Go to Your Account then Payment Information\n"
            f"3️⃣ Select Bank Transfer as your payment method\n"
            f"4️⃣ Go to Virtual Account in your PayFlow dashboard\n"
            f"5️⃣ Copy your routing number and account number\n"
            f"6️⃣ Paste those details into KDP and set currency to USD\n\n"
            f"Amazon pays on the last business day of each month. "
            f"Funds appear in your PayFlow wallet within 1-2 business days."
        )

    # Upwork/Fiverr questions
    if any(word in message_lower for word in [
        "upwork", "fiverr", "freelance", "client payment"
    ]):
        return (
            f"To receive freelance payments:\n\n"
            f"📌 Upwork: Go to Settings then Get Paid then Add Direct to Local Bank\n"
            f"📌 Fiverr: Go to Selling then Earnings then Withdraw then Direct Deposit\n"
            f"📌 Any client: Share your PayFlow virtual account details\n\n"
            f"Get your account details from the Virtual Account section "
            f"in your dashboard. Payments usually arrive within 1-2 business "
            f"days after release."
        )

    # Best time to withdraw
    if any(word in message_lower for word in [
        "best time", "when should", "should i withdraw", "wait",
        "timing", "right time"
    ]):
        return (
            f"Based on your balance of ${balance:.2f} USD:\n\n"
            f"✅ The current live NGN rate is ₦{ngn_rate:,.2f} which is strong.\n"
            f"✅ For amounts under $500 — withdraw anytime via Chipper Cash.\n"
            f"✅ For amounts $500-$5,000 — Grey gives the best NGN rate.\n"
            f"✅ For amounts above $5,000 — Wire transfer is most reliable.\n\n"
            f"Avoid withdrawing on Nigerian public holidays as banks "
            f"may delay processing by 1 business day."
        )

    # Virtual account questions
    if any(word in message_lower for word in [
        "virtual account", "account number", "routing number",
        "account details", "bank details", "usd account"
    ]):
        return (
            f"Your PayFlow USD virtual account details are in the "
            f"Virtual Account section of your dashboard.\n\n"
            f"You will find:\n"
            f"• Your US account number\n"
            f"• Your routing number\n"
            f"• SWIFT code for international wires\n"
            f"• Step-by-step guides for Amazon KDP, Upwork, and Fiverr\n\n"
            f"You can copy all your account details with one click and "
            f"share them with any client or payment platform."
        )

    # Greeting
    if any(word in message_lower for word in [
        "hi", "hello", "hey", "good morning", "good evening",
        "good afternoon", "how are you"
    ]):
        return (
            f"Hello {user.full_name.split()[0]}! 👋 I am PayBot, your financial assistant.\n\n"
            f"Your current balance is ${balance:.2f} USD.\n"
            f"Live USD/NGN rate today: ₦{ngn_rate:,.2f}\n\n"
            f"I can help you with:\n"
            f"• Withdrawal options and fees\n"
            f"• FX rates and conversion\n"
            f"• Amazon KDP and freelance payment setup\n"
            f"• Best time to withdraw\n"
            f"• Account insights\n\n"
            f"What would you like to know?"
        )

    # Default fallback
    return (
        f"Hi {user.full_name.split()[0]}! I am PayBot, your financial assistant.\n\n"
        f"Your current balance is ${balance:.2f} USD.\n"
        f"Live USD/NGN rate: ₦{ngn_rate:,.2f}\n\n"
        f"I can help you with:\n"
        f"• Checking your balance and transaction history\n"
        f"• Finding the best withdrawal option for your country\n"
        f"• Understanding FX rates and fees\n"
        f"• Setting up Amazon KDP or freelance payments\n\n"
        f"What would you like to know?"
    )