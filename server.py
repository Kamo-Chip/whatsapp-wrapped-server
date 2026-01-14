from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import Counter
import re
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="WhatsApp Wrapped API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



HEADER_RE = re.compile(
    r"^\[(\d{4}/\d{2}/\d{2}),\s(\d{2}:\d{2}:\d{2})\]\s([^:]+?):\s(.*)$"
)

ADMIN_ACTION_RE = re.compile(
    r"(created this group|added|removed|changed|promoted|omitted|made.*admin)",
    re.IGNORECASE
)

MEDIA_PLACEHOLDERS = {
    "<Media omitted>",
    "‎<Media omitted>",
    "image omitted",
    "video omitted",
    "sticker omitted",
}

STOPWORDS = {
    "the","a","an","and","or","but","to","of","in","on","for","with","is","it","this","that",
    "i","you","he","she","we","they","me","my","your","our","us","at","as","be","are","was",
    "were","so","not","do","does","did","from","by","if","then","im","i'm","u","ur","lol",
    "bro","brev"
}

DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# Rough emoji regex covering common emoji ranges. This should catch most emojis used in chats.
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
    "\u2600-\u26FF\u2700-\u27BF]",
    flags=re.UNICODE,
)


class WrappedResponse(BaseModel):
    total_records: int
    total_user_messages: int
    total_system_events: int

    top_talkers: List[Dict[str, Any]]
    quietest_sender: Optional[Dict[str, Any]]

    busiest_hour: Dict[str, Any]
    busiest_day_of_week: Dict[str, Any]
    peak_month: Dict[str, Any]

    night_owl: Dict[str, Any]

    longest_message: Optional[Dict[str, Any]]
    most_used_word: Optional[Dict[str, Any]]
    most_used_emoji: Optional[Dict[str, Any]]


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9']+", text)
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def is_media_message(message: str) -> bool:
    cleaned = message.replace("\u200e", "").strip()
    return cleaned in MEDIA_PLACEHOLDERS


def parse_chat_text(content: str):
    records = []
    current = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\n")

        m = HEADER_RE.match(line)
        if m:
            if current is not None:
                records.append(current)

            date_str, time_str, sender, msg = m.groups()
            ts = datetime.strptime(f"{date_str} {time_str}", "%Y/%m/%d %H:%M:%S")

            current = {
                "timestamp": ts,
                "sender": sender.strip(),
                "message": msg.strip(),
            }
        else:
            if current is not None and line.strip() != "":
                current["message"] += "\n" + line.strip()

    if current is not None:
        records.append(current)

    return records


def compute_stats(records):
    records = [r for r in records if r["timestamp"].year == 2025]

    system_events = []
    user_msgs = []

    for r in records:
        if ADMIN_ACTION_RE.search(r["message"]):
            system_events.append(r)
        else:
            user_msgs.append(r)

    total_records = len(records)
    total_user = len(user_msgs)
    total_sys = len(system_events)

    if total_user == 0:
        return WrappedResponse(
            total_records=total_records,
            total_user_messages=0,
            total_system_events=total_sys,
            top_talkers=[],
            quietest_sender=None,
            busiest_hour={"hour": None, "count": 0},
            busiest_day_of_week={"day": None, "count": 0},
            peak_month={"year": None, "month": None, "label": None, "count": 0},
            night_owl={"count": 0, "percent": 0.0},
            longest_message=None,
            most_used_word=None,
        )

    sender_counts = Counter(r["sender"] for r in user_msgs)

    top_talkers = [
        {"sender": s, "count": c}
        for s, c in sender_counts.most_common(10)
    ]

    quiet_sender, quiet_count = min(sender_counts.items(), key=lambda kv: kv[1])

    hour_counts = Counter(r["timestamp"].hour for r in user_msgs)
    busiest_hour, busiest_hour_count = hour_counts.most_common(1)[0]

    dow_counts = Counter(r["timestamp"].weekday() for r in user_msgs)
    busiest_dow, busiest_dow_count = dow_counts.most_common(1)[0]

    month_counts = Counter((r["timestamp"].year, r["timestamp"].month) for r in user_msgs)
    (peak_year, peak_month), peak_month_count = month_counts.most_common(1)[0]
    peak_label = datetime(peak_year, peak_month, 1).strftime("%B %Y")

    def is_night(ts: datetime) -> bool:
        return ts.hour >= 22 or ts.hour <= 4

    night_count = sum(1 for r in user_msgs if is_night(r["timestamp"]))
    night_percent = (night_count / total_user) * 100

    user_non_media = [r for r in user_msgs if not is_media_message(r["message"])]
    longest = None
    if user_non_media:
        lr = max(user_non_media, key=lambda r: len(r["message"]))
        longest = {
            "sender": lr["sender"],
            "timestamp": lr["timestamp"].isoformat(),
            "length_chars": len(lr["message"]),
            "preview": lr["message"].replace("\n", " ")[:200],
        }

    word_counter = Counter()
    for r in user_non_media:
        word_counter.update(tokenize(r["message"]))

    most_word = None
    if word_counter:
        w, c = word_counter.most_common(1)[0]
        most_word = {"word": w, "count": c}

    emoji_counter = Counter()
    for r in user_non_media:
        emojis = EMOJI_RE.findall(r["message"])
        if emojis:
            emoji_counter.update(emojis)

    most_emoji = None
    if emoji_counter:
        e, ec = emoji_counter.most_common(1)[0]
        most_emoji = {"emoji": e, "count": ec}

    return WrappedResponse(
        total_records=total_records,
        total_user_messages=total_user,
        total_system_events=total_sys,

        top_talkers=top_talkers,
        quietest_sender={"sender": quiet_sender, "count": quiet_count},

        busiest_hour={"hour": busiest_hour, "count": busiest_hour_count},
        busiest_day_of_week={"day": DOW_NAMES[busiest_dow], "count": busiest_dow_count},
        peak_month={"year": peak_year, "month": peak_month, "label": peak_label, "count": peak_month_count},

        night_owl={"count": night_count, "percent": round(night_percent, 2)},

        longest_message=longest,
        most_used_word=most_word,
        most_used_emoji=most_emoji,
    )


@app.post("/wrapped", response_model=WrappedResponse)
async def wrapped(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Please upload a .txt WhatsApp export file.")

    raw = await file.read()

    if len(raw) > 5 * 1024 * 1024:  # 5 MB
        raise HTTPException(status_code=413, detail="File too large (max 5MB).")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode file. Try exporting again or use UTF-8.")

    records = parse_chat_text(text)

    if not records:
        raise HTTPException(
            status_code=400,
            detail="No WhatsApp messages detected. Make sure this is the raw exported chat .txt."
        )

    return compute_stats(records)
