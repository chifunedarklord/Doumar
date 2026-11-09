"""Product-owner approved VND prices. Quotes do not grant paid access."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    monthly_vnd: int
    introductory_month_vnd: int

    @property
    def annual_vnd(self):
        return self.monthly_vnd * 12 * 80 // 100


PLANS = (Plan("plus", "Plus", 149_000, 67_000), Plan("pro", "Pro", 499_000, 399_000))


def format_vnd(amount):
    return f"{amount:,}".replace(",", ".") + "đ"


def quote(plan_key, cycle, first_purchase=False):
    plan = next((plan for plan in PLANS if plan.key == plan_key), None)
    if plan is None or cycle not in ("monthly", "annual"):
        raise ValueError("Gói hoặc chu kỳ không hợp lệ.")
    return {
        "plan": plan.key, "cycle": cycle, "currency": "VND",
        "amount": plan.annual_vnd if cycle == "annual" else plan.introductory_month_vnd if first_purchase else plan.monthly_vnd,
        "renewal_amount": plan.annual_vnd if cycle == "annual" else plan.monthly_vnd,
        "checkout_available": False,
    }
