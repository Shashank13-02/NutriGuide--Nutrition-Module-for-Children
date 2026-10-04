"""Previous-day feeding indicators, separate from clinical diagnosis or risk scoring.

WHO/UNICEF (2021), feeding-indicator definitions and calculation methods. These are population indicators;
the summary labels below are workflow outcomes, not validated severity classes.
"""
from nutrition_engine import FOOD_GROUPS, validate_selection
from screening_constants import SCREENING_DISCLAIMER

RULE_VERSION = "iycf-2021-v1"
SOURCE_URL = "https://data.unicef.org/wp-content/uploads/2021/04/Indicators-for-assessing-infant-and-young-child-feeding-practices.pdf"
EMERGENCY_FLAGS = ("active_choking", "breathing_difficulty", "blue_colour", "unresponsive")
REVIEW_FLAGS = ("swallowing_difficulty", "feeding_pain", "growth_concern", "dehydration", "persistent_vomiting", "allergy_concern")


def screen_intake(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Intake must be a JSON object.")
    age = data.get("age_months")
    if type(age) is not int or not 0 <= age <= 72:
        raise ValueError("age_months must be a whole number from 0 to 72.")
    for name in ("confirmed", "recall_complete", "breastfed", "honey_consumed", "sweet_beverage_consumed", "added_sugar_consumed", "use_model"):
        if name in data and data[name] is not None and type(data[name]) is not bool:
            raise ValueError(f"{name} must be true, false, or null (unknown).")
    for name in ("solid_feeds", "milk_feeds", "yogurt_feeds"):
        value = data.get(name)
        if value is not None and (type(value) is not int or not 0 <= value <= 50):
            raise ValueError(f"{name} must be a whole number from 0 to 50, or null.")
    groups = data.get("daily_groups")
    if groups is not None:
        if not isinstance(groups, list) or any(not isinstance(g, str) for g in groups):
            raise ValueError("daily_groups must be a list of food group names, or null.")
        groups = validate_selection(groups, FOOD_GROUPS, "daily food group")
    flags = data.get("red_flags", [])
    if not isinstance(flags, list) or any(not isinstance(f, str) for f in flags):
        raise ValueError("red_flags must be a list of supported symptom flags.")
    flags = validate_selection(flags, EMERGENCY_FLAGS + REVIEW_FLAGS, "symptom flag")
    if data.get("recall_period", "previous_day") != "previous_day":
        raise ValueError("Use a previous-day recall including daytime and night-time.")

    result = {
        "age_months": age, "rule_version": RULE_VERSION,
        "screening_result": "INSUFFICIENT_DATA", "findings": [], "next_steps": [],
        "missing_fields": [], "indicators": {}, "professional_review_flag": False,
        "emergency": False, "diagnostic": False, "screening_notice": SCREENING_DISCLAIMER,
        "sources": [{"id": "WHO-UNICEF-IYCF-2021", "url": SOURCE_URL}],
        "limitations": ["Previous-day feeding indicators do not establish nutritional adequacy or diagnose a deficiency.",
                        "No validated individual Low/Moderate/High severity score is calculated."],
    }
    if flags:
        result.update(screening_result="PROFESSIONAL_REVIEW_FLAG", professional_review_flag=True,
                      emergency=bool(set(flags) & set(EMERGENCY_FLAGS)))
        result["findings"] = ["Reported concern: " + flag.replace("_", " ") for flag in flags]
        result["next_steps"] = ["Seek emergency help now." if result["emergency"] else "Contact a pediatric clinician promptly for the reported concern."]
        return result
    if data.get("confirmed") is not True:
        result["missing_fields"] = ["confirmed"]
        result["next_steps"] = ["Review and confirm the intake record before calculating indicators."]
        return result
    if not 6 <= age <= 23:
        result["findings"] = ["The implemented minimum dietary diversity and meal-frequency indicators apply only to ages 6–23 months."]
        result["next_steps"] = ["Use age-specific feeding guidance and professional assessment for this age band."]
        result["limitations"].append("Structured intake indicators for 0–5 and 24–72 months are not implemented.")
        return result
    if data.get("recall_complete") is not True:
        result["missing_fields"] = ["recall_complete"]
        result["next_steps"] = ["Complete the previous-day recall, including food and milk consumed at night. A meal photo is not a full-day record."]
        return result

    breastfed = data.get("breastfed")
    solids, milk = data.get("solid_feeds"), data.get("milk_feeds")
    yogurt = data.get("yogurt_feeds")
    missing = result["missing_fields"]
    if groups is None:
        missing.append("daily_groups")
    if breastfed is None:
        missing.append("breastfed")
    if solids is None:
        missing.append("solid_feeds")
    if breastfed is False and milk is None:
        missing.append("milk_feeds")
    if breastfed is False and yogurt is None:
        missing.append("yogurt_feeds")
    if groups is not None and breastfed is not None and ("Breast milk" in groups) != breastfed:
        raise ValueError("breastfed must agree with the Breast milk group in the previous-day record.")
    if groups is not None and milk is not None and milk > 0 and "Dairy" not in groups:
        raise ValueError("Infant formula and other non-human milk feeds count in Dairy, not Breast milk.")
    if yogurt is not None and yogurt > 0:
        if groups is not None and "Dairy" not in groups:
            raise ValueError("Semi-solid yogurt feeds require the Dairy food group.")
        if solids is not None and yogurt > solids:
            raise ValueError("Semi-solid yogurt feeds must also be included in the solid/semi-solid/soft feeding count.")
    if groups is not None and solids is not None:
        solid_groups = set(groups) - {"Breast milk", "Dairy"}
        if solids == 0 and solid_groups:
            raise ValueError("Solid food groups conflict with zero solid/semi-solid/soft feedings.")
        if solids > 0 and not (set(groups) - {"Breast milk"}):
            raise ValueError("Record the food groups consumed in the solid/semi-solid/soft feedings.")

    def indicator(name, value, threshold, met):
        result["indicators"][name] = {"value": value, "threshold": threshold, "met": met}

    if groups is not None:
        indicator("minimum_dietary_diversity", len(groups), 5, len(groups) >= 5)
        result["findings"].append(f"Previous-day dietary diversity: {len(groups)} of 8 groups; minimum indicator {'met' if len(groups) >= 5 else 'not met'}.")
        indicator("egg_or_flesh_food_consumption", bool(set(groups) & {"Eggs", "Flesh foods"}), None, None)
        indicator("zero_fruit_or_vegetable_consumption", not bool(set(groups) & {FOOD_GROUPS[6], FOOD_GROUPS[7]}), None, None)
    mmf = None
    if breastfed is not None and solids is not None and (breastfed or milk is not None):
        threshold = (2 if age <= 8 else 3) if breastfed else 4
        count = solids if breastfed else solids + milk
        mmf = count >= threshold and (breastfed or solids >= 1)
        indicator("minimum_meal_frequency", count, threshold, mmf)
        result["findings"].append(f"Previous-day feeding frequency: {count}; minimum indicator {'met' if mmf else 'not met'} (threshold {threshold}{'; at least one non-milk feed required' if not breastfed else ''}).")
    mmff = None
    if breastfed is False and milk is not None and yogurt is not None:
        milk_total = milk + yogurt
        mmff = milk_total >= 2
        indicator("minimum_milk_feeding_frequency", milk_total, 2, mmff)
        result["findings"].append(f"Milk-frequency count: {milk_total} (fluid milk feeds {milk}, semi-solid yogurt feeds {yogurt}); minimum milk-frequency indicator {'met' if mmff else 'not met'}.")
    if not missing:
        mdd = len(groups) >= 5
        mad = mdd and mmf and (breastfed or mmff)
        indicator("minimum_acceptable_diet", None, None, bool(mad))
        result["findings"].append(f"Minimum acceptable diet indicator: {'met' if mad else 'not met'} in this previous-day recall.")
        result["screening_result"] = "INDICATORS_MET" if mad else "FEEDING_PATTERN_REVIEW"
        if not mdd:
            result["next_steps"].append("Review variety across the day and offer age-appropriate foods from additional groups.")
        if not mmf:
            result["next_steps"].append("Review the number of food feedings across the day against the age and breastfeeding-specific indicator.")
        if breastfed is False and not mmff:
            result["next_steps"].append("Discuss the reported milk-feeding pattern with a pediatric clinician.")
        if mad:
            result["next_steps"].append("Continue varied, responsive feeding; this recall alone does not establish overall nutritional adequacy.")
    else:
        result["next_steps"].append("Complete the missing fields: " + ", ".join(missing) + ".")
    for name, text in (("honey_consumed", "Honey was reported before 12 months; review with a pediatric clinician."),
                       ("sweet_beverage_consumed", "Sweet beverage consumption was reported; review drink choices."),
                       ("added_sugar_consumed", "Added sugar consumption was reported before 24 months; review food choices.")):
        if data.get(name) is True and (name != "honey_consumed" or age < 12):
            if not any(source["id"] == "CDC-LIMITS" for source in result["sources"]):
                result["sources"].append({"id": "CDC-LIMITS", "url": "https://www.cdc.gov/infant-toddler-nutrition/foods-and-drinks/foods-and-drinks-to-avoid-or-limit.html"})
            result["findings"].append(text)
            result["next_steps"].append(text)
            if not missing:
                result["screening_result"] = "FEEDING_PATTERN_REVIEW"
    return result


def format_screening(result: dict) -> str:
    lines = ["Screening result: " + result["screening_result"], "", *result["findings"], "", "Next steps:"]
    lines.extend("- " + s for s in result["next_steps"])
    lines.extend(["", *result["limitations"], result["screening_notice"], "[Source IDs: " + ", ".join(source["id"] for source in result["sources"]) + "]"])
    return "\n".join(lines)
