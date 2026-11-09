"""TaskFlow desktop palette: white surfaces, black ink and neutral separators."""

class Colors:
    BG_DARKEST = "#FFFFFF"
    BG_DARK = "#FFFFFF"
    BG_CARD = "#FFFFFF"
    BG_CARD_HOVER = "#F5F5F5"
    BG_SURFACE = "#FFFFFF"
    BG_INPUT = "#FFFFFF"
    BG_OVERLAY = "#40000000"
    PRIMARY = "#111111"
    PRIMARY_LIGHT = "#333333"
    PRIMARY_DARK = "#000000"
    PRIMARY_BG = "#F5F5F5"
    PRIMARY_BG_MED = "#EEEEEE"
    PRIMARY_BORDER = "#DDDDDD"
    PRIMARY_SHADOW = "#00000000"
    SECONDARY = "#666666"
    SECONDARY_LIGHT = "#767676"
    ACCENT_WARM = "#F5F5F5"
    ACCENT_WARM_LIGHT = "#FFFFFF"
    ACCENT_TEAL = "#111111"
    ACCENT_CYAN = "#111111"
    ACCENT_BLUE = "#111111"
    ACCENT_GRAY = "#666666"
    TEXT_PRIMARY = "#111111"
    TEXT_SECONDARY = "#555555"
    TEXT_MUTED = "#666666"
    TEXT_ON_PRIMARY = "#FFFFFF"
    SUCCESS = "#111111"
    WARNING = "#111111"
    ERROR = "#111111"
    INFO = "#111111"
    BORDER = "#E5E5E5"
    BORDER_LIGHT = "#F1F1F1"
    BORDER_GLOW = "#DDDDDD"
    PRIORITY_HIGH = "#111111"
    PRIORITY_MEDIUM = "#555555"
    PRIORITY_LOW = "#666666"
    CAT_WORK = "#111111"
    CAT_PERSONAL = "#111111"
    CAT_HEALTH = "#111111"
    CAT_FINANCE = "#111111"
    CAT_EDUCATION = "#111111"
    VIOLET = "#111111"
    CYAN = "#111111"
    EMERALD = "#111111"
    ROSE = "#111111"
    AMBER = "#111111"
    GRAY = "#666666"


class Typography:
    DISPLAY  = 28
    H1       = 24
    H2       = 20
    H3       = 18
    H4       = 16
    BODY     = 17
    SMALL    = 16
    TINY     = 14

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
               "bg": "#F0F0F0", "border_light": "#CCCCCC", "shadow": "#18000000"},
    "medium": {"color": Colors.PRIORITY_MEDIUM, "label": "Vừa", "icon": "🟡",
               "bg": "#F5F5F5", "border_light": "#DDDDDD", "shadow": "#10000000"},
    "low":    {"color": Colors.PRIORITY_LOW,    "label": "Thấp", "icon": "🟢",
               "bg": "#FAFAFA", "border_light": "#E5E5E5", "shadow": "#08000000"},
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
