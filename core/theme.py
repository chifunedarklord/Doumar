"""
TaskFlow - Modern Mobile App Theme
Clean, vibrant design with harmonious color palette
"""

# ─── COLOR PALETTE ────────────────────────────────────────────────────────────
class Colors:
    # Backgrounds - Dark gray theme
    BG_DARKEST   = "#141414"  # Deepest background
    BG_DARK      = "#1E1E1E"  # Secondary background
    BG_CARD      = "#252525"  # Card background
    BG_CARD_HOVER= "#2E2E2E"  # Card hover
    BG_SURFACE   = "#2A2A2A"  # Surface elements
    BG_INPUT     = "#1E1E1E"  # Input background
    BG_OVERLAY   = "#14141499" # Overlay

    # Primary - Soft white/light gray (active accent)
    PRIMARY      = "#E8E8E8"   # Near-white — active/highlight
    PRIMARY_LIGHT = "#F5F5F5"  # White
    PRIMARY_DARK = "#B0B0B0"   # Dimmed

    # Secondary - Medium gray
    SECONDARY    = "#6B6B6B"   # Medium gray
    SECONDARY_LIGHT = "#8A8A8A" # Light gray

    # Accent warm — subtle warm tint for highlights
    ACCENT_WARM  = "#C8C0B8"   # Warm off-white
    ACCENT_WARM_LIGHT = "#DDD8D2" # Lighter warm

    # Supporting colors
    ACCENT_TEAL  = "#7EAAB8"   # Muted teal (status: in progress)
    ACCENT_CYAN  = "#7EAAB8"   # alias
    ACCENT_BLUE  = "#6B8FA8"   # Muted blue
    ACCENT_GRAY  = "#6B6B6B"   # Neutral gray

    # Text colors
    TEXT_PRIMARY   = "#F0F0F0"  # Primary text
    TEXT_SECONDARY = "#B8B8B8"  # Secondary text
    TEXT_MUTED     = "#6B6B6B"  # Muted/placeholder
    TEXT_ON_PRIMARY = "#141414" # Text on bright bg

    # Status colors — visible but muted
    SUCCESS      = "#6BAF7A"   # Muted green
    WARNING      = "#C8A86B"   # Muted amber
    ERROR        = "#B86B6B"   # Muted red
    INFO         = "#6B8FA8"   # Muted blue

    # Borders
    BORDER       = "#333333"   # Subtle border
    BORDER_LIGHT = "#444444"   # Light border
    BORDER_GLOW  = "#555555"   # Glow border

    # Priority colors — clearly distinct
    PRIORITY_HIGH   = "#B86B6B" # Red-ish
    PRIORITY_MEDIUM = "#C8A86B" # Amber-ish
    PRIORITY_LOW    = "#6BAF7A" # Green-ish

    # Category colors — muted but distinct
    CAT_WORK      = "#6B8FA8"   # Blue-gray
    CAT_PERSONAL  = "#9A7AB8"   # Purple-gray
    CAT_HEALTH    = "#6BAF7A"   # Green-gray
    CAT_FINANCE   = "#C8A86B"   # Amber-gray
    CAT_EDUCATION = "#7EAAB8"   # Teal-gray

    # Aliases for compatibility
    VIOLET       = "#9A7AB8"   # Muted violet
    CYAN         = "#7EAAB8"   # Muted cyan
    EMERALD      = "#6BAF7A"   # Muted green
    ROSE         = "#B86B6B"   # Muted rose
    AMBER        = "#C8A86B"   # Muted amber
    GRAY         = "#6B6B6B"   # Neutral gray


class Typography:
    # Font sizes - Mobile optimized
    DISPLAY  = 28  # Large headers
    H1       = 24  # Screen titles
    H2       = 20  # Section headers
    H3       = 18  # Subsection headers
    H4       = 16  # Card titles
    BODY     = 14  # Body text
    SMALL    = 13  # Secondary text
    TINY     = 11  # Labels, badges

    # Font weights
    THIN     = "w100"
    LIGHT    = "w300"
    REGULAR  = "w400"
    MEDIUM   = "w500"
    SEMIBOLD = "w600"
    BOLD     = "w700"
    EXTRABOLD= "w800"


class Spacing:
    # Mobile-friendly spacing
    XS  = 4
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 20
    XXL = 24
    XXXL= 32


class Radius:
    # Rounded corners for mobile
    SM  = 8
    MD  = 12
    LG  = 16
    XL  = 20
    FULL= 999


PRIORITY_MAP = {
    "high":   {"color": Colors.PRIORITY_HIGH,   "label": "Cao",   "icon": "🔴"},
    "medium": {"color": Colors.PRIORITY_MEDIUM, "label": "Vừa",  "icon": "🟡"},
    "low":    {"color": Colors.PRIORITY_LOW,    "label": "Thấp",  "icon": "🟢"},
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
