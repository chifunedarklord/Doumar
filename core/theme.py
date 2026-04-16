"""
TaskFlow - Modern Mobile App Theme
Light, vibrant design with White and Blue (Primary) palette
"""

# ─── COLOR PALETTE ────────────────────────────────────────────────────────────
class Colors:
    # ── Backgrounds (Light Theme) ──
    BG_DARKEST   = "#F3F4F6"  # Light gray background (app background)
    BG_DARK      = "#F9FAFB"  # Slightly lighter background
    BG_CARD      = "#FFFFFF"  # Pure white card background
    BG_CARD_HOVER= "#F3F4F6"  # Card hover state
    BG_SURFACE   = "#FFFFFF"  # Surface elements
    BG_INPUT     = "#F9FAFB"  # Input background
    BG_OVERLAY   = "#40000000" # Overlay (darkened for modal)

    # ── Primary (Blue) ──
    PRIMARY      = "#2563EB"   # Tailwind Blue 600 - Main Brand Color
    PRIMARY_LIGHT  = "#3B82F6"  # Tailwind Blue 500
    PRIMARY_DARK   = "#1D4ED8"  # Tailwind Blue 700
    PRIMARY_BG     = "#EFF6FF"  # Blue-50 - very light tint (icon backgrounds)
    PRIMARY_BG_MED = "#DBEAFE"  # Blue-100 - slightly deeper tint
    PRIMARY_BORDER = "#BFDBFE"  # Blue-200 - border around primary elements
    PRIMARY_SHADOW = "#402563EB" # Blue shadow 25%

    # ── Secondary & Grays ──
    SECONDARY    = "#6B7280"   # Light Gray for sub-elements
    SECONDARY_LIGHT = "#9CA3AF"

    # ── Accent ──
    ACCENT_WARM  = "#F3F4F6"
    ACCENT_WARM_LIGHT = "#FFFFFF"
    ACCENT_TEAL  = "#0D9488"   # Teal
    ACCENT_CYAN  = "#0891B2"   # Cyan
    ACCENT_BLUE  = "#3B82F6"   # Blue
    ACCENT_GRAY  = "#9CA3AF"   # Neutral gray

    # ── Text Colors ──
    TEXT_PRIMARY   = "#111827"  # Very dark gray (almost black)
    TEXT_SECONDARY = "#4B5563"  # Medium-dark gray
    TEXT_MUTED     = "#9CA3AF"  # Light gray placeholder
    TEXT_ON_PRIMARY = "#FFFFFF" # White text on blue bg

    # ── Status Colors ──
    SUCCESS      = "#10B981"   # Emerald green
    WARNING      = "#F59E0B"   # Amber/Orange
    ERROR        = "#EF4444"   # Red
    INFO         = "#3B82F6"   # Blue

    # ── Borders ──
    BORDER       = "#E5E7EB"   # Very light gray border
    BORDER_LIGHT = "#F3F4F6"   # Extremely light border
    BORDER_GLOW  = "#93C5FD"   # Blue glow border

    # ── Priority colors ──
    PRIORITY_HIGH   = "#EF4444"
    PRIORITY_MEDIUM = "#F59E0B"
    PRIORITY_LOW    = "#10B981"

    # ── Category colors ──
    CAT_WORK      = "#3B82F6"   # Blue
    CAT_PERSONAL  = "#8B5CF6"   # Purple
    CAT_HEALTH    = "#10B981"   # Green
    CAT_FINANCE   = "#F59E0B"   # Amber
    CAT_EDUCATION = "#06B6D4"   # Cyan

    # ── Aliases ──
    VIOLET       = "#8B5CF6"
    CYAN         = "#06B6D4"
    EMERALD      = "#10B981"
    ROSE         = "#F43F5E"
    AMBER        = "#F59E0B"
    GRAY         = "#6B7280"


class Typography:
    DISPLAY  = 28
    H1       = 24
    H2       = 20
    H3       = 18
    H4       = 16
    BODY     = 14
    SMALL    = 13
    TINY     = 11

    THIN     = "w100"
    LIGHT    = "w300"
    REGULAR  = "w400"
    MEDIUM   = "w500"
    SEMIBOLD = "w600"
    BOLD     = "w700"
    EXTRABOLD= "w800"


class Spacing:
    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 20
    XXL = 24
    XXXL= 32


class Radius:
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 20
    FULL= 999


PRIORITY_MAP = {
    "high":   {"color": Colors.PRIORITY_HIGH,   "label": "Cao",  "icon": "🔴",
               "bg": "#FEE2E2", "border_light": "#FECACA", "shadow": "#30EF4444"},
    "medium": {"color": Colors.PRIORITY_MEDIUM, "label": "Vừa", "icon": "🟡",
               "bg": "#FEF3C7", "border_light": "#FDE68A", "shadow": "#30F59E0B"},
    "low":    {"color": Colors.PRIORITY_LOW,    "label": "Thấp", "icon": "🟢",
               "bg": "#D1FAE5", "border_light": "#A7F3D0", "shadow": "#3010B981"},
}

CATEGORY_MAP = {
    "work":      {"color": Colors.CAT_WORK,      "label": "Công việc",   "icon": "💼"},
    "personal":  {"color": Colors.CAT_PERSONAL,  "label": "Cá nhân",     "icon": "✨"},
    "health":    {"color": Colors.CAT_HEALTH,    "label": "Sức khỏe",    "icon": "🏃"},
    "finance":   {"color": Colors.CAT_FINANCE,   "label": "Tài chính",   "icon": "💳"},
    "education": {"color": Colors.CAT_EDUCATION, "label": "Học tập",     "icon": "📚"},
}

STATUS_MAP = {
    "todo":        {"color": Colors.TEXT_SECONDARY, "label": "Chưa làm",   "icon": "📋"},
    "in_progress": {"color": Colors.ACCENT_CYAN,    "label": "Đang làm",   "icon": "⚡"},
    "done":        {"color": Colors.SUCCESS,        "label": "Hoàn thành", "icon": "✅"},
    "cancelled":   {"color": Colors.ERROR,          "label": "Đã hủy",     "icon": "❌"},
}
