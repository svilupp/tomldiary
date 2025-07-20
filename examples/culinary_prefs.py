#!/usr/bin/env python3
"""
Culinary Preference Table for Cooking Memory System

This module defines a comprehensive preference schema specifically designed for
culinary applications and cooking show memory systems. Each category includes
detailed instructions for AI agents on what information to capture and store.
"""

from pydantic import BaseModel, Field

from tomldiary.models import PreferenceItem


class CulinaryPrefTable(BaseModel):
    """
    Comprehensive culinary preference schema for cooking applications.

    This schema is specifically designed for culinary memory systems where AI agents
    need to extract, categorize, and store cooking-related preferences from conversations.
    Each field includes detailed instructions for what constitutes valid information.
    """

    favorite_foods: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Specific dishes, cuisines, ingredients, or food categories the person genuinely enjoys.

        EXAMPLES TO SAVE:
        - "pasta carbonara" - specific dish preference
        - "japanese cuisine" - cuisine style preference
        - "aged cheeses" - ingredient category preference
        - "dark chocolate" - specific ingredient with qualifier
        - "fresh herbs" - ingredient category with quality preference

        EXAMPLES TO IGNORE:
        - "food" - too generic
        - "cooking" - this is a technique, not a food
        - "ingredients" - too vague without specifics
        - Temporary mentions like "tonight's dinner"

        FOCUS: Genuine food preferences that would influence menu planning or recipe selection.
        Only record items mentioned with clear positive sentiment (love, enjoy, favorite, prefer, best).
        """,
    )

    cooking_techniques: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Specific cooking methods, culinary techniques, or preparation styles they prefer or specialize in.

        EXAMPLES TO SAVE:
        - "sous vide cooking" - modern precision technique
        - "wood-fired grilling" - specific cooking method with detail
        - "knife work" - fundamental skill they excel at
        - "french classical techniques" - cooking tradition/style
        - "molecular gastronomy" - specialized cooking approach
        - "fermentation" - food preparation technique

        EXAMPLES TO IGNORE:
        - "cooking" - too basic/generic
        - "chopping" - universal basic skill
        - "heating" - too fundamental
        - "using a stove" - basic equipment use

        FOCUS: Distinctive techniques that define their cooking style or expertise.
        Look for methods that require skill, training, or represent their culinary philosophy.
        """,
    )

    flavor_preferences: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Specific flavor profiles, taste preferences, or seasoning styles they favor.

        EXAMPLES TO SAVE:
        - "umami-rich flavors" - specific taste profile
        - "bright acidic notes" - flavor characteristic preference
        - "complex spice blends" - seasoning style preference
        - "subtle herb combinations" - flavor building approach
        - "bold smoky flavors" - specific taste preference

        EXAMPLES TO IGNORE:
        - "good taste" - too subjective/vague
        - "flavor" - too generic
        - "salt" - unless specifically mentioned as preference

        FOCUS: Specific flavor profiles that guide their cooking decisions and taste preferences.
        """,
    )

    dislikes: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Foods, flavors, techniques, or cooking practices they consistently avoid or dislike.

        EXAMPLES TO SAVE:
        - "overcooked vegetables" - technique-related dislike
        - "processed ingredients" - ingredient quality preference
        - "microwave cooking" - technique avoidance
        - "overly sweet desserts" - flavor profile dislike
        - "factory-farmed meat" - ethical/quality concern

        EXAMPLES TO IGNORE:
        - "bad food" - too subjective/vague
        - "mistakes" - not specific enough
        - Temporary situational dislikes

        FOCUS: Consistent patterns of avoidance that would influence cooking or menu decisions.
        Only record clear negative sentiment (hate, dislike, avoid, can't stand).
        """,
    )

    dietary_restrictions: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Medical allergies, religious restrictions, ethical choices, or health-related dietary limitations.

        EXAMPLES TO SAVE:
        - "severe nut allergy" - medical restriction (critical for safety)
        - "lactose intolerant" - medical condition affecting cooking
        - "kosher diet" - religious dietary law
        - "vegan lifestyle" - ethical dietary choice
        - "gluten sensitivity" - health-related restriction
        - "low-sodium diet" - medical dietary requirement

        EXAMPLES TO IGNORE:
        - "trying to eat healthy" - temporary preference
        - "avoiding carbs this week" - short-term diet
        - "don't usually eat..." - preference, not restriction

        FOCUS: Permanent or long-term restrictions that absolutely must be considered in cooking.
        These affect ingredient selection and cooking methods fundamentally.
        """,
    )

    cooking_habits: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Regular cooking routines, consistent behaviors, or personal rituals in the kitchen.

        EXAMPLES TO SAVE:
        - "always does mise en place" - consistent preparation routine
        - "tastes and adjusts throughout cooking" - quality control habit
        - "makes fresh pasta weekly" - regular cooking routine
        - "grows own herbs" - ingredient sourcing habit
        - "reads recipes three times before starting" - preparation ritual

        EXAMPLES TO IGNORE:
        - "cooked dinner tonight" - one-time action
        - "used a recipe" - basic cooking activity
        - "turned on the oven" - basic equipment use

        FOCUS: Repeated patterns and personal systems that characterize their cooking approach.
        Look for words like "always," "every," "daily," "routinely," "never fails to."
        """,
    )

    ingredient_preferences: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="""
        CAPTURE: Specific ingredients, sourcing preferences, or quality standards they consistently seek.

        EXAMPLES TO SAVE:
        - "organic vegetables only" - sourcing preference with quality standard
        - "locally-sourced meat" - sourcing preference with geographical constraint
        - "heirloom tomatoes" - specific ingredient variety preference
        - "european-style butter" - ingredient origin/style preference
        - "single-origin vanilla" - ingredient quality/sourcing specificity

        EXAMPLES TO IGNORE:
        - "good ingredients" - too vague
        - "food from the store" - too generic
        - "whatever's available" - no preference indicated

        FOCUS: Specific sourcing standards and ingredient quality preferences that guide purchasing decisions.
        """,
    )
