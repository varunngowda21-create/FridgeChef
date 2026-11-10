#!/usr/bin/env python3
"""
Seed Data Generator for FridgeChef AI
Creates:
- data/ingredients.json (>= 200 canonical ingredients)
- data/shelf_life.json (shelf-life entries for all ingredients across storage types)
- data/recipes.json (>= 150 authentic curated Indian recipes)
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. INGREDIENTS (215 canonical Indian ingredients)
# ---------------------------------------------------------------------------
INGREDIENTS = [
    # Vegetables (58)
    {"id": "potato", "display_name": "Potato", "category": "Vegetables", "aliases": ["potato", "aloo", "batata", "alu"], "default_unit": "piece", "grams_per_piece": 120, "price_inr_per_kg": 35, "allergen_group": None},
    {"id": "tomato", "display_name": "Tomato", "category": "Vegetables", "aliases": ["tomato", "tamatar", "thakkali"], "default_unit": "piece", "grams_per_piece": 90, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "onion", "display_name": "Onion", "category": "Vegetables", "aliases": ["onion", "pyaaz", "kanda", "vengayam"], "default_unit": "piece", "grams_per_piece": 100, "price_inr_per_kg": 45, "allergen_group": None},
    {"id": "garlic", "display_name": "Garlic", "category": "Vegetables", "aliases": ["garlic", "lehsun", "poondu", "lasun"], "default_unit": "piece", "grams_per_piece": 5, "price_inr_per_kg": 180, "allergen_group": None},
    {"id": "ginger", "display_name": "Ginger", "category": "Vegetables", "aliases": ["ginger", "adrak", "inji", "ale"], "default_unit": "g", "grams_per_piece": 40, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "green_chilli", "display_name": "Green Chilli", "category": "Vegetables", "aliases": ["green chilli", "hari mirch", "pachai milagai", "hirvi mirchi"], "default_unit": "piece", "grams_per_piece": 8, "price_inr_per_kg": 80, "allergen_group": None},
    {"id": "spinach", "display_name": "Spinach", "category": "Vegetables", "aliases": ["spinach", "palak", "pasalai keerai"], "default_unit": "g", "grams_per_piece": 250, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "cauliflower", "display_name": "Cauliflower", "category": "Vegetables", "aliases": ["cauliflower", "gobi", "phool gobi"], "default_unit": "piece", "grams_per_piece": 600, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "cabbage", "display_name": "Cabbage", "category": "Vegetables", "aliases": ["cabbage", "patta gobi", "muttakose", "bandhgobi"], "default_unit": "piece", "grams_per_piece": 500, "price_inr_per_kg": 35, "allergen_group": None},
    {"id": "green_peas", "display_name": "Green Peas", "category": "Vegetables", "aliases": ["green peas", "matar", "pattani"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "carrot", "display_name": "Carrot", "category": "Vegetables", "aliases": ["carrot", "gajar", "gajjara"], "default_unit": "piece", "grams_per_piece": 100, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "capsicum", "display_name": "Capsicum (Bell Pepper)", "category": "Vegetables", "aliases": ["capsicum", "bell pepper", "shimla mirch", "green pepper"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 80, "allergen_group": None},
    {"id": "beetroot", "display_name": "Beetroot", "category": "Vegetables", "aliases": ["beetroot", "chukandar", "beet"], "default_unit": "piece", "grams_per_piece": 130, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "bottle_gourd", "display_name": "Bottle Gourd", "category": "Vegetables", "aliases": ["bottle gourd", "lauki", "doodhi", "ghiya", "sorakkayi"], "default_unit": "piece", "grams_per_piece": 650, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "bitter_gourd", "display_name": "Bitter Gourd", "category": "Vegetables", "aliases": ["bitter gourd", "karela", "pavakkai"], "default_unit": "piece", "grams_per_piece": 100, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "ridge_gourd", "display_name": "Ridge Gourd", "category": "Vegetables", "aliases": ["ridge gourd", "turai", "peerkangai", "dodka"], "default_unit": "piece", "grams_per_piece": 200, "price_inr_per_kg": 55, "allergen_group": None},
    {"id": "snake_gourd", "display_name": "Snake Gourd", "category": "Vegetables", "aliases": ["snake gourd", "chichinda", "padavalanga", "pudalangai"], "default_unit": "piece", "grams_per_piece": 300, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "ivy_gourd", "display_name": "Ivy Gourd (Tindora)", "category": "Vegetables", "aliases": ["ivy gourd", "tindora", "kundru", "kovakkai", "tondekai"], "default_unit": "g", "grams_per_piece": 20, "price_inr_per_kg": 65, "allergen_group": None},
    {"id": "okra", "display_name": "Okra (Ladyfinger)", "category": "Vegetables", "aliases": ["okra", "lady finger", "bhindi", "vendakkai", "bhendi"], "default_unit": "g", "grams_per_piece": 15, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "brinjal", "display_name": "Brinjal (Eggplant)", "category": "Vegetables", "aliases": ["brinjal", "eggplant", "baingan", "kathirikai", "vangi"], "default_unit": "piece", "grams_per_piece": 180, "price_inr_per_kg": 45, "allergen_group": None},
    {"id": "fenugreek_leaves", "display_name": "Fenugreek Leaves (Methi)", "category": "Vegetables", "aliases": ["fenugreek leaves", "methi", "vendhaya keerai"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "coriander_leaves", "display_name": "Coriander Leaves", "category": "Vegetables", "aliases": ["coriander leaves", "dhaniya patta", "kothamalli", "cilantro", "kothmir"], "default_unit": "g", "grams_per_piece": 100, "price_inr_per_kg": 80, "allergen_group": None},
    {"id": "mint_leaves", "display_name": "Mint Leaves", "category": "Vegetables", "aliases": ["mint leaves", "pudina"], "default_unit": "g", "grams_per_piece": 100, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "curry_leaves", "display_name": "Curry Leaves", "category": "Vegetables", "aliases": ["curry leaves", "kadi patta", "kariveppilai", "kadi patta"], "default_unit": "g", "grams_per_piece": 30, "price_inr_per_kg": 100, "allergen_group": None},
    {"id": "drumstick", "display_name": "Drumstick", "category": "Vegetables", "aliases": ["drumstick", "murungakkai", "sahjan", "shevga"], "default_unit": "piece", "grams_per_piece": 80, "price_inr_per_kg": 80, "allergen_group": None},
    {"id": "radish", "display_name": "Radish", "category": "Vegetables", "aliases": ["radish", "mooli", "mullangi"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "sweet_potato", "display_name": "Sweet Potato", "category": "Vegetables", "aliases": ["sweet potato", "shakarkand", "sakkaravalli kizhangu"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "raw_banana", "display_name": "Raw Banana (Plantain)", "category": "Vegetables", "aliases": ["raw banana", "kaccha kela", "vazhakkai"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "elephant_foot_yam", "display_name": "Elephant Foot Yam (Suran)", "category": "Vegetables", "aliases": ["elephant foot yam", "suran", "jimikand", "senai kizhangu"], "default_unit": "g", "grams_per_piece": 400, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "colocasia", "display_name": "Colocasia (Arbi)", "category": "Vegetables", "aliases": ["colocasia", "arbi", "seppankizhangu", "taro root"], "default_unit": "g", "grams_per_piece": 50, "price_inr_per_kg": 65, "allergen_group": None},
    {"id": "ash_gourd", "display_name": "Ash Gourd", "category": "Vegetables", "aliases": ["ash gourd", "petha", "safed petha", "neer poosanikai"], "default_unit": "piece", "grams_per_piece": 1000, "price_inr_per_kg": 35, "allergen_group": None},
    {"id": "pumpkin", "display_name": "Pumpkin", "category": "Vegetables", "aliases": ["pumpkin", "kaddu", "parangikai", "bhopla"], "default_unit": "g", "grams_per_piece": 800, "price_inr_per_kg": 35, "allergen_group": None},
    {"id": "french_beans", "display_name": "French Beans", "category": "Vegetables", "aliases": ["french beans", "beans", "pharas bi", "beans"], "default_unit": "g", "grams_per_piece": 10, "price_inr_per_kg": 75, "allergen_group": None},
    {"id": "cluster_beans", "display_name": "Cluster Beans (Gwar Phali)", "category": "Vegetables", "aliases": ["cluster beans", "gwar phali", "kothavarangai"], "default_unit": "g", "grams_per_piece": 8, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "broad_beans", "display_name": "Broad Beans (Sem Phali)", "category": "Vegetables", "aliases": ["broad beans", "sem phali", "avaraikkai"], "default_unit": "g", "grams_per_piece": 12, "price_inr_per_kg": 65, "allergen_group": None},
    {"id": "cucumber", "display_name": "Cucumber", "category": "Vegetables", "aliases": ["cucumber", "kheera", "kakdi", "vellarikkai"], "default_unit": "piece", "grams_per_piece": 180, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "spring_onion", "display_name": "Spring Onion", "category": "Vegetables", "aliases": ["spring onion", "hara pyaaz", "scallions"], "default_unit": "g", "grams_per_piece": 80, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "mushroom", "display_name": "Mushroom (Button)", "category": "Vegetables", "aliases": ["mushroom", "khumb", "kalan"], "default_unit": "g", "grams_per_piece": 20, "price_inr_per_kg": 200, "allergen_group": None},
    {"id": "sweet_corn", "display_name": "Sweet Corn", "category": "Vegetables", "aliases": ["sweet corn", "makka", "bhutta"], "default_unit": "piece", "grams_per_piece": 200, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "baby_corn", "display_name": "Baby Corn", "category": "Vegetables", "aliases": ["baby corn", "chota makka"], "default_unit": "g", "grams_per_piece": 20, "price_inr_per_kg": 150, "allergen_group": None},
    {"id": "raw_mango", "display_name": "Raw Mango", "category": "Vegetables", "aliases": ["raw mango", "kaccha aam", "kairi", "mangai"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "lemon", "display_name": "Lemon", "category": "Vegetables", "aliases": ["lemon", "nimbu", "elumichai", "limbu"], "default_unit": "piece", "grams_per_piece": 50, "price_inr_per_kg": 80, "allergen_group": None},
    {"id": "pointed_gourd", "display_name": "Pointed Gourd (Parwal)", "category": "Vegetables", "aliases": ["pointed gourd", "parwal", "potol"], "default_unit": "g", "grams_per_piece": 35, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "knol_khol", "display_name": "Kohlrabi (Ganth Gobi)", "category": "Vegetables", "aliases": ["kohlrabi", "knol khol", "ganth gobi", "noolkol"], "default_unit": "piece", "grams_per_piece": 180, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "dill_leaves", "display_name": "Dill Leaves (Shepu)", "category": "Vegetables", "aliases": ["dill leaves", "suva bhaji", "shepu"], "default_unit": "g", "grams_per_piece": 150, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "mustard_greens", "display_name": "Mustard Greens (Sarson)", "category": "Vegetables", "aliases": ["mustard greens", "sarson ka saag"], "default_unit": "g", "grams_per_piece": 300, "price_inr_per_kg": 45, "allergen_group": None},
    {"id": "amaranth_leaves", "display_name": "Amaranth Leaves (Chaulikeerai)", "category": "Vegetables", "aliases": ["amaranth leaves", "chaulai", "thotakura"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "lotus_stem", "display_name": "Lotus Stem (Kamal Kakdi)", "category": "Vegetables", "aliases": ["lotus stem", "kamal kakdi", "bheen"], "default_unit": "g", "grams_per_piece": 250, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "red_bell_pepper", "display_name": "Red Bell Pepper", "category": "Vegetables", "aliases": ["red bell pepper", "red capsicum", "laal shimla mirch"], "default_unit": "piece", "grams_per_piece": 160, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "yellow_bell_pepper", "display_name": "Yellow Bell Pepper", "category": "Vegetables", "aliases": ["yellow bell pepper", "yellow capsicum", "peeli shimla mirch"], "default_unit": "piece", "grams_per_piece": 160, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "turnip", "display_name": "Turnip (Shalgam)", "category": "Vegetables", "aliases": ["turnip", "shalgam"], "default_unit": "piece", "grams_per_piece": 120, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "beetroot_greens", "display_name": "Beetroot Greens", "category": "Vegetables", "aliases": ["beetroot greens", "chukandar patta"], "default_unit": "g", "grams_per_piece": 100, "price_inr_per_kg": 30, "allergen_group": None},
    {"id": "radish_leaves", "display_name": "Radish Leaves (Mooli Patta)", "category": "Vegetables", "aliases": ["radish leaves", "mooli ke patte"], "default_unit": "g", "grams_per_piece": 150, "price_inr_per_kg": 25, "allergen_group": None},
    {"id": "sponge_gourd", "display_name": "Sponge Gourd (Ghiya Turai)", "category": "Vegetables", "aliases": ["sponge gourd", "chikni turai", "gilki"], "default_unit": "piece", "grams_per_piece": 180, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "zucchini", "display_name": "Zucchini", "category": "Vegetables", "aliases": ["zucchini", "courgette"], "default_unit": "piece", "grams_per_piece": 200, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "green_papaya", "display_name": "Green Raw Papaya", "category": "Vegetables", "aliases": ["raw papaya", "kaccha papita"], "default_unit": "piece", "grams_per_piece": 600, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "shallots", "display_name": "Shallots (Sambar Onion)", "category": "Vegetables", "aliases": ["shallots", "sambar onion", "chinna vengayam", "madras onion"], "default_unit": "g", "grams_per_piece": 20, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "jackfruit_raw", "display_name": "Raw Jackfruit (Kathal)", "category": "Vegetables", "aliases": ["raw jackfruit", "kathal", "pala kai"], "default_unit": "g", "grams_per_piece": 400, "price_inr_per_kg": 80, "allergen_group": None},

    # Fruits (22)
    {"id": "banana", "display_name": "Banana", "category": "Fruits", "aliases": ["banana", "kela", "vazhai pazham"], "default_unit": "piece", "grams_per_piece": 120, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "apple", "display_name": "Apple", "category": "Fruits", "aliases": ["apple", "seb", "apple"], "default_unit": "piece", "grams_per_piece": 150, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "mango", "display_name": "Ripe Mango", "category": "Fruits", "aliases": ["mango", "aam", "mambazham", "alphonso"], "default_unit": "piece", "grams_per_piece": 250, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "papaya", "display_name": "Ripe Papaya", "category": "Fruits", "aliases": ["papaya", "papita", "pappali"], "default_unit": "piece", "grams_per_piece": 900, "price_inr_per_kg": 45, "allergen_group": None},
    {"id": "pomegranate", "display_name": "Pomegranate", "category": "Fruits", "aliases": ["pomegranate", "anar", "mathulai"], "default_unit": "piece", "grams_per_piece": 250, "price_inr_per_kg": 180, "allergen_group": None},
    {"id": "orange", "display_name": "Orange", "category": "Fruits", "aliases": ["orange", "santra", "narangi", "kitchili"], "default_unit": "piece", "grams_per_piece": 140, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "guava", "display_name": "Guava", "category": "Fruits", "aliases": ["guava", "amrood", "koyyapazham"], "default_unit": "piece", "grams_per_piece": 130, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "watermelon", "display_name": "Watermelon", "category": "Fruits", "aliases": ["watermelon", "tarbooz", "tharpoosanikai"], "default_unit": "piece", "grams_per_piece": 2500, "price_inr_per_kg": 30, "allergen_group": None},
    {"id": "muskmelon", "display_name": "Muskmelon (Kharbuja)", "category": "Fruits", "aliases": ["muskmelon", "kharbuja", "cantaloupe"], "default_unit": "piece", "grams_per_piece": 800, "price_inr_per_kg": 40, "allergen_group": None},
    {"id": "grapes", "display_name": "Grapes", "category": "Fruits", "aliases": ["grapes", "angoor", "dhrakshai"], "default_unit": "g", "grams_per_piece": 5, "price_inr_per_kg": 100, "allergen_group": None},
    {"id": "pineapple", "display_name": "Pineapple", "category": "Fruits", "aliases": ["pineapple", "ananas"], "default_unit": "piece", "grams_per_piece": 900, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "sapodilla", "display_name": "Sapodilla (Chikoo)", "category": "Fruits", "aliases": ["chikoo", "sapota", "chiku"], "default_unit": "piece", "grams_per_piece": 80, "price_inr_per_kg": 75, "allergen_group": None},
    {"id": "sweet_lime", "display_name": "Sweet Lime (Mosambi)", "category": "Fruits", "aliases": ["mosambi", "mousambi", "sweet lime"], "default_unit": "piece", "grams_per_piece": 130, "price_inr_per_kg": 85, "allergen_group": None},
    {"id": "coconut_fresh", "display_name": "Fresh Coconut", "category": "Fruits", "aliases": ["coconut", "nariyal", "thengai", "fresh coconut"], "default_unit": "piece", "grams_per_piece": 400, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "custard_apple", "display_name": "Custard Apple (Sitaphal)", "category": "Fruits", "aliases": ["custard apple", "sitaphal", "seethaphal"], "default_unit": "piece", "grams_per_piece": 180, "price_inr_per_kg": 110, "allergen_group": None},
    {"id": "pears", "display_name": "Pear", "category": "Fruits", "aliases": ["pear", "nashpati"], "default_unit": "piece", "grams_per_piece": 140, "price_inr_per_kg": 130, "allergen_group": None},
    {"id": "strawberry", "display_name": "Strawberry", "category": "Fruits", "aliases": ["strawberry"], "default_unit": "g", "grams_per_piece": 18, "price_inr_per_kg": 300, "allergen_group": None},
    {"id": "dates", "display_name": "Dates (Khajoor)", "category": "Fruits", "aliases": ["dates", "khajoor", "pericham pazham"], "default_unit": "g", "grams_per_piece": 10, "price_inr_per_kg": 250, "allergen_group": None},
    {"id": "amla", "display_name": "Indian Gooseberry (Amla)", "category": "Fruits", "aliases": ["amla", "nellikai", "gooseberry"], "default_unit": "piece", "grams_per_piece": 30, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "fig_fresh", "display_name": "Fresh Fig (Anjeer)", "category": "Fruits", "aliases": ["fig", "anjeer", "athipazham"], "default_unit": "piece", "grams_per_piece": 45, "price_inr_per_kg": 220, "allergen_group": None},
    {"id": "kiwi", "display_name": "Kiwi Fruit", "category": "Fruits", "aliases": ["kiwi"], "default_unit": "piece", "grams_per_piece": 90, "price_inr_per_kg": 200, "allergen_group": None},
    {"id": "plum", "display_name": "Plum (Aloo Bukhara)", "category": "Fruits", "aliases": ["plum", "aloo bukhara"], "default_unit": "piece", "grams_per_piece": 60, "price_inr_per_kg": 160, "allergen_group": None},

    # Dairy and Eggs (15)
    {"id": "milk", "display_name": "Cow Milk", "category": "Dairy and Eggs", "aliases": ["milk", "doodh", "paal"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 65, "allergen_group": "Dairy"},
    {"id": "curd", "display_name": "Curd (Dahi)", "category": "Dairy and Eggs", "aliases": ["curd", "dahi", "thayir", "yogurt"], "default_unit": "g", "grams_per_piece": 400, "price_inr_per_kg": 70, "allergen_group": "Dairy"},
    {"id": "paneer", "display_name": "Paneer (Cottage Cheese)", "category": "Dairy and Eggs", "aliases": ["paneer", "cottage cheese"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 380, "allergen_group": "Dairy"},
    {"id": "butter", "display_name": "Butter", "category": "Dairy and Eggs", "aliases": ["butter", "makhan", "vennai"], "default_unit": "g", "grams_per_piece": 100, "price_inr_per_kg": 520, "allergen_group": "Dairy"},
    {"id": "ghee", "display_name": "Desi Ghee (Clarified Butter)", "category": "Dairy and Eggs", "aliases": ["ghee", "desi ghee", "neyyi"], "default_unit": "g", "grams_per_piece": 500, "price_inr_per_kg": 650, "allergen_group": "Dairy"},
    {"id": "cream", "display_name": "Fresh Cream (Malai)", "category": "Dairy and Eggs", "aliases": ["cream", "malai", "fresh cream"], "default_unit": "ml", "ml_per_piece": 250, "price_inr_per_kg": 260, "allergen_group": "Dairy"},
    {"id": "cheese_processed", "display_name": "Processed Cheese", "category": "Dairy and Eggs", "aliases": ["cheese", "processed cheese", "cheese cubes"], "default_unit": "g", "grams_per_piece": 25, "price_inr_per_kg": 500, "allergen_group": "Dairy"},
    {"id": "buttermilk", "display_name": "Buttermilk (Chaas)", "category": "Dairy and Eggs", "aliases": ["buttermilk", "chaas", "mor"], "default_unit": "ml", "ml_per_piece": 500, "price_inr_per_kg": 35, "allergen_group": "Dairy"},
    {"id": "condensed_milk", "display_name": "Condensed Milk (Mithai Mate)", "category": "Dairy and Eggs", "aliases": ["condensed milk", "mithai mate"], "default_unit": "g", "grams_per_piece": 400, "price_inr_per_kg": 300, "allergen_group": "Dairy"},
    {"id": "khoya", "display_name": "Khoya (Mawa)", "category": "Dairy and Eggs", "aliases": ["khoya", "mawa"], "default_unit": "g", "grams_per_piece": 250, "price_inr_per_kg": 380, "allergen_group": "Dairy"},
    {"id": "eggs", "display_name": "Eggs", "category": "Dairy and Eggs", "aliases": ["egg", "eggs", "anda", "muttai"], "default_unit": "piece", "grams_per_piece": 55, "price_inr_per_kg": 120, "allergen_group": "Eggs"},
    {"id": "hung_curd", "display_name": "Hung Curd (Chakka)", "category": "Dairy and Eggs", "aliases": ["hung curd", "chakka"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 150, "allergen_group": "Dairy"},
    {"id": "mozzarella_cheese", "display_name": "Mozzarella Cheese", "category": "Dairy and Eggs", "aliases": ["mozzarella", "pizza cheese"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 600, "allergen_group": "Dairy"},
    {"id": "goat_milk", "display_name": "Goat Milk", "category": "Dairy and Eggs", "aliases": ["goat milk", "bakri ka doodh"], "default_unit": "ml", "ml_per_piece": 500, "price_inr_per_kg": 110, "allergen_group": "Dairy"},
    {"id": "evaporated_milk", "display_name": "Evaporated Milk", "category": "Dairy and Eggs", "aliases": ["evaporated milk"], "default_unit": "ml", "ml_per_piece": 400, "price_inr_per_kg": 280, "allergen_group": "Dairy"},

    # Proteins (16)
    {"id": "chicken_breast", "display_name": "Boneless Chicken Breast", "category": "Proteins", "aliases": ["chicken breast", "boneless chicken", "murgi"], "default_unit": "g", "grams_per_piece": 220, "price_inr_per_kg": 320, "allergen_group": None},
    {"id": "chicken_curry_cut", "display_name": "Chicken Curry Cut (with bone)", "category": "Proteins", "aliases": ["chicken", "curry cut chicken", "murgh"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 240, "allergen_group": None},
    {"id": "chicken_thighs", "display_name": "Chicken Thighs", "category": "Proteins", "aliases": ["chicken thighs"], "default_unit": "g", "grams_per_piece": 180, "price_inr_per_kg": 300, "allergen_group": None},
    {"id": "mutton_curry_cut", "display_name": "Mutton (Goat Meat)", "category": "Proteins", "aliases": ["mutton", "goat meat", "gosht"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 750, "allergen_group": None},
    {"id": "mutton_keema", "display_name": "Mutton Keema (Minced Mutton)", "category": "Proteins", "aliases": ["mutton keema", "minced mutton"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 800, "allergen_group": None},
    {"id": "fish_rohu", "display_name": "Rohu Fish Fillet / Steaks", "category": "Proteins", "aliases": ["rohu fish", "machli", "meen"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 280, "allergen_group": "Fish"},
    {"id": "fish_pomfret", "display_name": "Pomfret Fish", "category": "Proteins", "aliases": ["pomfret", "paplet"], "default_unit": "piece", "grams_per_piece": 250, "price_inr_per_kg": 750, "allergen_group": "Fish"},
    {"id": "fish_surmai", "display_name": "Kingfish (Surmai)", "category": "Proteins", "aliases": ["surmai", "kingfish", "vanjaram"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 850, "allergen_group": "Fish"},
    {"id": "prawns", "display_name": "Prawns / Shrimp", "category": "Proteins", "aliases": ["prawns", "shrimp", "jheenga", "era"], "default_unit": "g", "grams_per_piece": 15, "price_inr_per_kg": 550, "allergen_group": "Shellfish"},
    {"id": "tofu", "display_name": "Tofu (Soy Paneer)", "category": "Proteins", "aliases": ["tofu", "soy paneer"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 180, "allergen_group": "Soy"},
    {"id": "soya_chunks", "display_name": "Soya Chunks (Nutrela)", "category": "Proteins", "aliases": ["soya chunks", "nutrela", "meal maker"], "default_unit": "g", "grams_per_piece": 10, "price_inr_per_kg": 150, "allergen_group": "Soy"},
    {"id": "soya_granules", "display_name": "Soya Granules", "category": "Proteins", "aliases": ["soya granules"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 160, "allergen_group": "Soy"},
    {"id": "fish_katla", "display_name": "Katla Fish", "category": "Proteins", "aliases": ["katla fish", "catla"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 270, "allergen_group": "Fish"},
    {"id": "fish_basa", "display_name": "Basa Fish Fillet", "category": "Proteins", "aliases": ["basa fish", "basa fillet"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 350, "allergen_group": "Fish"},
    {"id": "egg_whites", "display_name": "Egg Whites", "category": "Proteins", "aliases": ["egg white", "ande ki safedi"], "default_unit": "piece", "grams_per_piece": 35, "price_inr_per_kg": 110, "allergen_group": "Eggs"},
    {"id": "crab_meat", "display_name": "Crab Meat", "category": "Proteins", "aliases": ["crab", "khekda"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 600, "allergen_group": "Shellfish"},

    # Grains and Pulses (34)
    {"id": "basmati_rice", "display_name": "Basmati Rice", "category": "Grains and Pulses", "aliases": ["basmati rice", "chawal", "arisi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "sona_masoori_rice", "display_name": "Sona Masoori Rice", "category": "Grains and Pulses", "aliases": ["sona masoori", "raw rice", "pacharisi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 65, "allergen_group": None},
    {"id": "brown_rice", "display_name": "Brown Rice", "category": "Grains and Pulses", "aliases": ["brown rice"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 95, "allergen_group": None},
    {"id": "poha", "display_name": "Flattened Rice (Poha)", "category": "Grains and Pulses", "aliases": ["poha", "flattened rice", "aval", "avalakki", "chivda"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 55, "allergen_group": None},
    {"id": "puffed_rice", "display_name": "Puffed Rice (Kurmura / Murmura)", "category": "Grains and Pulses", "aliases": ["kurmura", "murmura", "pori", "puffed rice"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "wheat_flour", "display_name": "Whole Wheat Flour (Atta)", "category": "Grains and Pulses", "aliases": ["wheat flour", "atta", "gehu ka atta"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 45, "allergen_group": "Gluten"},
    {"id": "maida", "display_name": "Refined Wheat Flour (Maida)", "category": "Grains and Pulses", "aliases": ["maida", "all purpose flour", "refined flour"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 45, "allergen_group": "Gluten"},
    {"id": "semolina", "display_name": "Semolina (Sooji / Rava)", "category": "Grains and Pulses", "aliases": ["sooji", "rava", "semolina", "suji"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 55, "allergen_group": "Gluten"},
    {"id": "besan", "display_name": "Gram Flour (Besan)", "category": "Grains and Pulses", "aliases": ["besan", "gram flour", "chickpea flour", "kadala maavu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "ragi_flour", "display_name": "Finger Millet Flour (Ragi)", "category": "Grains and Pulses", "aliases": ["ragi", "finger millet", "nachni"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "jowar_flour", "display_name": "Sorghum Flour (Jowar)", "category": "Grains and Pulses", "aliases": ["jowar", "sorghum", "cholam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 65, "allergen_group": None},
    {"id": "bajra_flour", "display_name": "Pearl Millet Flour (Bajra)", "category": "Grains and Pulses", "aliases": ["bajra", "pearl millet", "kambu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 55, "allergen_group": None},
    {"id": "oats", "display_name": "Rolled Oats", "category": "Grains and Pulses", "aliases": ["oats", "rolled oats"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "yellow_moong_dal", "display_name": "Yellow Moong Dal (Split Petite)", "category": "Grains and Pulses", "aliases": ["moong dal", "yellow moong dal", "paasi paruppu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "split_green_moong_dal", "display_name": "Split Green Moong Dal (Chilka)", "category": "Grains and Pulses", "aliases": ["green moong dal", "chilka moong"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 130, "allergen_group": None},
    {"id": "whole_green_moong", "display_name": "Whole Green Gram (Sabut Moong)", "category": "Grains and Pulses", "aliases": ["whole green gram", "sabut moong", "green gram sprouts"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 135, "allergen_group": None},
    {"id": "toor_dal", "display_name": "Toor Dal (Arhar / Pigeon Pea)", "category": "Grains and Pulses", "aliases": ["toor dal", "arhar dal", "tuvar dal", "thuvaram paruppu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "chana_dal", "display_name": "Chana Dal (Bengal Gram)", "category": "Grains and Pulses", "aliases": ["chana dal", "bengal gram", "kadalai paruppu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 100, "allergen_group": None},
    {"id": "urad_dal_split", "display_name": "Urad Dal Split (White)", "category": "Grains and Pulses", "aliases": ["urad dal", "white urad dal", "ulutham paruppu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "urad_dal_whole", "display_name": "Urad Dal Whole Black (Sabut Urad)", "category": "Grains and Pulses", "aliases": ["sabut urad", "black gram", "kali dal"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 145, "allergen_group": None},
    {"id": "masoor_dal", "display_name": "Red Masoor Dal (Split Red Lentils)", "category": "Grains and Pulses", "aliases": ["masoor dal", "red lentils", "lal masoor"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 95, "allergen_group": None},
    {"id": "whole_masoor", "display_name": "Whole Brown Masoor", "category": "Grains and Pulses", "aliases": ["whole masoor", "sabut masoor", "brown lentils"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 100, "allergen_group": None},
    {"id": "kabuli_chana", "display_name": "Kabuli Chana (White Chickpeas)", "category": "Grains and Pulses", "aliases": ["chickpeas", "kabuli chana", "chole", "safed chana"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "kala_chana", "display_name": "Kala Chana (Brown Chickpeas)", "category": "Grains and Pulses", "aliases": ["kala chana", "black chickpeas", "desi chana"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "rajma", "display_name": "Rajma (Red Kidney Beans)", "category": "Grains and Pulses", "aliases": ["rajma", "kidney beans", "red kidney beans"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 160, "allergen_group": None},
    {"id": "white_peas", "display_name": "White Dried Peas (Safed Vatana)", "category": "Grains and Pulses", "aliases": ["safed vatana", "white peas", "ragda peas"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 75, "allergen_group": None},
    {"id": "cowpeas_lobia", "display_name": "Cowpeas (Lobia / Black-eyed Peas)", "category": "Grains and Pulses", "aliases": ["lobia", "black eyed peas", "karamani", "chawli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 110, "allergen_group": None},
    {"id": "moth_beans", "display_name": "Moth Beans (Matki)", "category": "Grains and Pulses", "aliases": ["matki", "moth beans"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "horse_gram", "display_name": "Horse Gram (Kulthi)", "category": "Grains and Pulses", "aliases": ["kulthi", "horse gram", "kollu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 85, "allergen_group": None},
    {"id": "sabudana", "display_name": "Tapioca Pearls (Sabudana)", "category": "Grains and Pulses", "aliases": ["sabudana", "tapioca pearls", "sago", "javvarisi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "vermicelli", "display_name": "Vermicelli (Seviyan / Semiya)", "category": "Grains and Pulses", "aliases": ["seviyan", "semiya", "vermicelli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 80, "allergen_group": "Gluten"},
    {"id": "broken_wheat", "display_name": "Broken Wheat (Daliya / Lapsi)", "category": "Grains and Pulses", "aliases": ["daliya", "broken wheat", "lapsi rava"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 65, "allergen_group": "Gluten"},
    {"id": "idli_rice", "display_name": "Idli Rice (Parboiled)", "category": "Grains and Pulses", "aliases": ["idli rice", "puzhungal arisi", "parboiled rice"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "quinoa", "display_name": "Quinoa", "category": "Grains and Pulses", "aliases": ["quinoa"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 320, "allergen_group": None},

    # Spices (40)
    {"id": "turmeric_powder", "display_name": "Turmeric Powder", "category": "Spices", "aliases": ["turmeric", "haldi", "manjal podi", "turmeric powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 240, "allergen_group": None},
    {"id": "red_chilli_powder", "display_name": "Red Chilli Powder", "category": "Spices", "aliases": ["red chilli powder", "lal mirch powder", "milagai thool"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 320, "allergen_group": None},
    {"id": "kashmiri_chilli_powder", "display_name": "Kashmiri Chilli Powder", "category": "Spices", "aliases": ["kashmiri lal mirch", "degungi mirch", "kashmiri chilli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 450, "allergen_group": None},
    {"id": "coriander_powder", "display_name": "Coriander Powder (Dhania Powder)", "category": "Spices", "aliases": ["coriander powder", "dhania powder", "malli thool"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 220, "allergen_group": None},
    {"id": "cumin_seeds", "display_name": "Cumin Seeds (Jeera)", "category": "Spices", "aliases": ["cumin seeds", "jeera", "seeragam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 380, "allergen_group": None},
    {"id": "cumin_powder", "display_name": "Cumin Powder (Jeera Powder)", "category": "Spices", "aliases": ["jeera powder", "roasted cumin powder", "cumin powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 400, "allergen_group": None},
    {"id": "mustard_seeds", "display_name": "Mustard Seeds (Rai / Sarson)", "category": "Spices", "aliases": ["mustard seeds", "rai", "sarson", "kadugu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 140, "allergen_group": "Mustard"},
    {"id": "fennel_seeds", "display_name": "Fennel Seeds (Saunf)", "category": "Spices", "aliases": ["fennel seeds", "saunf", "sombu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 260, "allergen_group": None},
    {"id": "fenugreek_seeds", "display_name": "Fenugreek Seeds (Methi Dana)", "category": "Spices", "aliases": ["fenugreek seeds", "methi dana", "vendhayam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 150, "allergen_group": None},
    {"id": "carom_seeds", "display_name": "Carom Seeds (Ajwain)", "category": "Spices", "aliases": ["carom seeds", "ajwain", "omam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 340, "allergen_group": None},
    {"id": "nigella_seeds", "display_name": "Nigella Seeds (Kalonji)", "category": "Spices", "aliases": ["kalonji", "nigella seeds", "black cumin"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 350, "allergen_group": None},
    {"id": "cardamom_green", "display_name": "Green Cardamom (Choti Elaichi)", "category": "Spices", "aliases": ["green cardamom", "elaichi", "elakkai"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 2400, "allergen_group": None},
    {"id": "cardamom_black", "display_name": "Black Cardamom (Badi Elaichi)", "category": "Spices", "aliases": ["black cardamom", "badi elaichi", "moti elaichi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 1800, "allergen_group": None},
    {"id": "cloves", "display_name": "Cloves (Laung)", "category": "Spices", "aliases": ["cloves", "laung", "lavangam", "lavang"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 1200, "allergen_group": None},
    {"id": "cinnamon_stick", "display_name": "Cinnamon Stick (Dalchini)", "category": "Spices", "aliases": ["cinnamon", "dalchini", "pattai"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 800, "allergen_group": None},
    {"id": "bay_leaf", "display_name": "Bay Leaf (Tejpatta)", "category": "Spices", "aliases": ["bay leaf", "tejpatta", "biryani aaku"], "default_unit": "piece", "grams_per_piece": 1, "price_inr_per_kg": 400, "allergen_group": None},
    {"id": "star_anise", "display_name": "Star Anise (Chakra Phool)", "category": "Spices", "aliases": ["star anise", "chakra phool", "annasi poo"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 900, "allergen_group": None},
    {"id": "mace", "display_name": "Mace (Javitri)", "category": "Spices", "aliases": ["mace", "javitri", "jadipathri"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 2500, "allergen_group": None},
    {"id": "nutmeg", "display_name": "Nutmeg (Jaiphal)", "category": "Spices", "aliases": ["nutmeg", "jaiphal", "jadhikkai"], "default_unit": "piece", "grams_per_piece": 8, "price_inr_per_kg": 1200, "allergen_group": None},
    {"id": "black_peppercorns", "display_name": "Black Peppercorns (Kali Mirch)", "category": "Spices", "aliases": ["black pepper", "kali mirch", "milagu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 850, "allergen_group": None},
    {"id": "black_pepper_powder", "display_name": "Black Pepper Powder", "category": "Spices", "aliases": ["black pepper powder", "kali mirch powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 900, "allergen_group": None},
    {"id": "asafoetida", "display_name": "Asafoetida (Hing)", "category": "Spices", "aliases": ["hing", "asafoetida", "perungayam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 2000, "allergen_group": None},
    {"id": "amchur", "display_name": "Dry Mango Powder (Amchur)", "category": "Spices", "aliases": ["amchur", "amchoor", "dry mango powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 350, "allergen_group": None},
    {"id": "garam_masala", "display_name": "Garam Masala Powder", "category": "Spices", "aliases": ["garam masala", "garam masala powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 600, "allergen_group": None},
    {"id": "chaat_masala", "display_name": "Chaat Masala", "category": "Spices", "aliases": ["chaat masala", "chat masala"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 380, "allergen_group": None},
    {"id": "kasuri_methi", "display_name": "Dried Fenugreek Leaves (Kasuri Methi)", "category": "Spices", "aliases": ["kasuri methi", "kasoori methi", "dried methi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 400, "allergen_group": None},
    {"id": "dry_ginger_powder", "display_name": "Dry Ginger Powder (Saunth)", "category": "Spices", "aliases": ["saunth", "dry ginger powder", "sukku podi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 450, "allergen_group": None},
    {"id": "saffron", "display_name": "Saffron (Kesar)", "category": "Spices", "aliases": ["saffron", "kesar", "zafran", "kungumapoo"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 150000, "allergen_group": None},
    {"id": "white_sesame_seeds", "display_name": "White Sesame Seeds (Safed Til)", "category": "Spices", "aliases": ["sesame seeds", "til", "safed til", "ellu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 240, "allergen_group": "Sesame"},
    {"id": "black_sesame_seeds", "display_name": "Black Sesame Seeds (Kala Til)", "category": "Spices", "aliases": ["black sesame seeds", "kala til", "karuppu ellu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 260, "allergen_group": "Sesame"},
    {"id": "poppy_seeds", "display_name": "Poppy Seeds (Khus Khus)", "category": "Spices", "aliases": ["khus khus", "poppy seeds", "khas khas", "gasagase"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 1800, "allergen_group": None},
    {"id": "tamarind", "display_name": "Tamarind (Imli)", "category": "Spices", "aliases": ["tamarind", "imli", "puli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "dry_red_chillies", "display_name": "Dry Whole Red Chillies", "category": "Spices", "aliases": ["dry red chilli", "sukhi lal mirch", "kாய்ந்த மிளகாய்"], "default_unit": "piece", "grams_per_piece": 2, "price_inr_per_kg": 300, "allergen_group": None},
    {"id": "coriander_seeds", "display_name": "Whole Coriander Seeds (Sabut Dhania)", "category": "Spices", "aliases": ["coriander seeds", "sabut dhania", "malli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 180, "allergen_group": None},
    {"id": "sambar_powder", "display_name": "Sambar Powder", "category": "Spices", "aliases": ["sambar powder", "sambar podi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 400, "allergen_group": None},
    {"id": "rasam_powder", "display_name": "Rasam Powder", "category": "Spices", "aliases": ["rasam powder", "rasam podi"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 420, "allergen_group": None},
    {"id": "biryani_masala", "display_name": "Biryani Masala", "category": "Spices", "aliases": ["biryani masala"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 650, "allergen_group": None},
    {"id": "pav_bhaji_masala", "display_name": "Pav Bhaji Masala", "category": "Spices", "aliases": ["pav bhaji masala"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 450, "allergen_group": None},
    {"id": "chole_masala", "display_name": "Chole Masala", "category": "Spices", "aliases": ["chole masala", "chana masala powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 460, "allergen_group": None},
    {"id": "kitchen_king_masala", "display_name": "Kitchen King Masala", "category": "Spices", "aliases": ["kitchen king masala", "sabzi masala"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 480, "allergen_group": None},

    # Oils and Condiments (18)
    {"id": "mustard_oil", "display_name": "Mustard Oil (Kachi Ghani)", "category": "Oils and Condiments", "aliases": ["mustard oil", "sarson ka tel"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 160, "allergen_group": "Mustard"},
    {"id": "sunflower_oil", "display_name": "Sunflower Cooking Oil", "category": "Oils and Condiments", "aliases": ["cooking oil", "sunflower oil", "refined oil"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 135, "allergen_group": None},
    {"id": "groundnut_oil", "display_name": "Groundnut Oil (Peanut Oil)", "category": "Oils and Condiments", "aliases": ["groundnut oil", "peanut oil", "moongphali tel"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 180, "allergen_group": "Peanuts"},
    {"id": "sesame_oil", "display_name": "Gingelly / Sesame Oil", "category": "Oils and Condiments", "aliases": ["sesame oil", "til ka tel", "nalla ennai"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 350, "allergen_group": "Sesame"},
    {"id": "coconut_oil", "display_name": "Edible Coconut Oil", "category": "Oils and Condiments", "aliases": ["coconut oil", "nariyal tel", "thengai ennai"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 240, "allergen_group": None},
    {"id": "olive_oil", "display_name": "Olive Oil", "category": "Oils and Condiments", "aliases": ["olive oil", "jaitun tel"], "default_unit": "ml", "ml_per_piece": 1000, "price_inr_per_kg": 950, "allergen_group": None},
    {"id": "salt", "display_name": "Iodised Table Salt", "category": "Oils and Condiments", "aliases": ["salt", "namak", "uppu"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 25, "allergen_group": None},
    {"id": "black_salt", "display_name": "Black Salt (Kala Namak)", "category": "Oils and Condiments", "aliases": ["black salt", "kala namak", "sanchal"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "rock_salt", "display_name": "Rock Salt (Sendha Namak)", "category": "Oils and Condiments", "aliases": ["rock salt", "sendha namak", "vrat ka namak"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 75, "allergen_group": None},
    {"id": "sugar", "display_name": "Granulated White Sugar", "category": "Oils and Condiments", "aliases": ["sugar", "cheeni", "shakkar", "sakkarai"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 45, "allergen_group": None},
    {"id": "jaggery", "display_name": "Organic Jaggery (Gur)", "category": "Oils and Condiments", "aliases": ["jaggery", "gur", "gud", "vellam"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 70, "allergen_group": None},
    {"id": "honey", "display_name": "Pure Honey", "category": "Oils and Condiments", "aliases": ["honey", "shehad", "thaen"], "default_unit": "g", "grams_per_piece": 500, "price_inr_per_kg": 360, "allergen_group": None},
    {"id": "white_vinegar", "display_name": "White Cooking Vinegar", "category": "Oils and Condiments", "aliases": ["vinegar", "sirka"], "default_unit": "ml", "ml_per_piece": 500, "price_inr_per_kg": 60, "allergen_group": None},
    {"id": "tomato_ketchup", "display_name": "Tomato Ketchup", "category": "Oils and Condiments", "aliases": ["tomato ketchup", "tomato sauce"], "default_unit": "g", "grams_per_piece": 500, "price_inr_per_kg": 140, "allergen_group": None},
    {"id": "soy_sauce", "display_name": "Dark Soy Sauce", "category": "Oils and Condiments", "aliases": ["soy sauce", "dark soy sauce"], "default_unit": "ml", "ml_per_piece": 200, "price_inr_per_kg": 180, "allergen_group": "Soy"},
    {"id": "green_chilli_sauce", "display_name": "Green Chilli Sauce", "category": "Oils and Condiments", "aliases": ["green chilli sauce"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "rose_water", "display_name": "Rose Water (Gulab Jal)", "category": "Oils and Condiments", "aliases": ["rose water", "gulab jal"], "default_unit": "ml", "ml_per_piece": 200, "price_inr_per_kg": 300, "allergen_group": None},
    {"id": "kokum", "display_name": "Dried Kokum Rind", "category": "Oils and Condiments", "aliases": ["kokum", "amsul", "punarpuli"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 350, "allergen_group": None},
    {"id": "ginger_garlic_paste", "display_name": "Ginger Garlic Paste", "category": "Oils and Condiments", "aliases": ["ginger garlic paste", "adrak lehsun paste"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 150, "allergen_group": None},
    {"id": "tomato_puree", "display_name": "Tomato Puree", "category": "Oils and Condiments", "aliases": ["tomato puree", "tamatar puree"], "default_unit": "ml", "ml_per_piece": 200, "price_inr_per_kg": 120, "allergen_group": None},
    {"id": "tamarind_paste", "display_name": "Tamarind Paste", "category": "Oils and Condiments", "aliases": ["tamarind paste", "imli paste"], "default_unit": "g", "grams_per_piece": 200, "price_inr_per_kg": 180, "allergen_group": None},
    {"id": "anardana_powder", "display_name": "Pomegranate Seed Powder (Anardana)", "category": "Spices", "aliases": ["anardana", "pomegranate powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 500, "allergen_group": None},
    {"id": "bisi_bele_bath_powder", "display_name": "Bisi Bele Bath Masala Powder", "category": "Spices", "aliases": ["bisi bele bath powder", "bbb powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 450, "allergen_group": None},
    {"id": "makki_atta", "display_name": "Maize Flour (Makki Ka Atta)", "category": "Grains and Pulses", "aliases": ["makki atta", "makai ka atta", "corn meal"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 55, "allergen_group": None},
    {"id": "tinda", "display_name": "Apple Gourd (Tinda)", "category": "Vegetables", "aliases": ["tinda", "apple gourd", "dhemse"], "default_unit": "piece", "grams_per_piece": 80, "price_inr_per_kg": 50, "allergen_group": None},
    {"id": "chayote", "display_name": "Chayote Squash (Chow Chow)", "category": "Vegetables", "aliases": ["chayote", "chow chow", "seemebadnekai"], "default_unit": "piece", "grams_per_piece": 250, "price_inr_per_kg": 45, "allergen_group": None},

    # Other (Nuts, Seeds & Baking) (18)
    {"id": "cashews", "display_name": "Cashew Nuts (Kaju)", "category": "Other", "aliases": ["cashew", "kaju", "mundhiri"], "default_unit": "g", "grams_per_piece": 2, "price_inr_per_kg": 850, "allergen_group": "Tree Nuts"},
    {"id": "almonds", "display_name": "Almonds (Badam)", "category": "Other", "aliases": ["almond", "badam", "patham"], "default_unit": "g", "grams_per_piece": 2, "price_inr_per_kg": 800, "allergen_group": "Tree Nuts"},
    {"id": "raisins", "display_name": "Raisins (Kishmish)", "category": "Other", "aliases": ["raisins", "kishmish", "kismis", "dry grapes"], "default_unit": "g", "grams_per_piece": 1, "price_inr_per_kg": 350, "allergen_group": None},
    {"id": "pistachios", "display_name": "Pistachios (Pista)", "category": "Other", "aliases": ["pista", "pistachio"], "default_unit": "g", "grams_per_piece": 2, "price_inr_per_kg": 1200, "allergen_group": "Tree Nuts"},
    {"id": "walnuts", "display_name": "Walnuts (Akhrot)", "category": "Other", "aliases": ["walnut", "akhrot"], "default_unit": "g", "grams_per_piece": 5, "price_inr_per_kg": 1100, "allergen_group": "Tree Nuts"},
    {"id": "peanuts", "display_name": "Peanuts (Groundnuts)", "category": "Other", "aliases": ["peanuts", "moongphali", "verkadalai", "shengdana"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 130, "allergen_group": "Peanuts"},
    {"id": "desiccated_coconut", "display_name": "Desiccated Dry Coconut Powder", "category": "Other", "aliases": ["dry coconut", "desiccated coconut", "kopra"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 260, "allergen_group": None},
    {"id": "melon_seeds", "display_name": "Melon Seeds (Magaz)", "category": "Other", "aliases": ["magaz", "melon seeds", "charmagaz"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 600, "allergen_group": None},
    {"id": "tea_leaves", "display_name": "Black Tea Leaves (Chai Patti)", "category": "Other", "aliases": ["tea", "chai patti", "tea leaves"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 360, "allergen_group": None},
    {"id": "coffee_powder", "display_name": "Instant / Filter Coffee Powder", "category": "Other", "aliases": ["coffee", "coffee powder", "filter coffee"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 900, "allergen_group": None},
    {"id": "baking_soda", "display_name": "Baking Soda (Sodium Bicarbonate)", "category": "Other", "aliases": ["baking soda", "meetha soda"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 100, "allergen_group": None},
    {"id": "baking_powder", "display_name": "Baking Powder", "category": "Other", "aliases": ["baking powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 180, "allergen_group": None},
    {"id": "cornflour", "display_name": "Cornstarch (Cornflour)", "category": "Other", "aliases": ["cornflour", "corn starch"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 90, "allergen_group": None},
    {"id": "yeast", "display_name": "Active Dry Yeast", "category": "Other", "aliases": ["yeast", "dry yeast"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 400, "allergen_group": None},
    {"id": "vanilla_essence", "display_name": "Vanilla Extract / Essence", "category": "Other", "aliases": ["vanilla", "vanilla essence"], "default_unit": "ml", "ml_per_piece": 50, "price_inr_per_kg": 1200, "allergen_group": None},
    {"id": "cocoa_powder", "display_name": "Unsweetened Cocoa Powder", "category": "Other", "aliases": ["cocoa", "cocoa powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 650, "allergen_group": None},
    {"id": "custard_powder", "display_name": "Vanilla Custard Powder", "category": "Other", "aliases": ["custard powder"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 200, "allergen_group": None},
    {"id": "bread_crumbs", "display_name": "Bread Crumbs", "category": "Other", "aliases": ["bread crumbs"], "default_unit": "g", "grams_per_piece": None, "price_inr_per_kg": 150, "allergen_group": "Gluten"},
]

print(f"Total canonical ingredients defined: {len(INGREDIENTS)}")

# ---------------------------------------------------------------------------
# 2. SHELF LIFE (for all 215 ingredients across 4 storage locations)
# ---------------------------------------------------------------------------
SHELF_LIFE = []
for ing in INGREDIENTS:
    cat = ing["category"]
    ing_id = ing["id"]

    if cat == "Vegetables":
        if ing_id in ("onion", "potato", "garlic", "ginger", "sweet_potato", "elephant_foot_yam"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "PANTRY", "days": 30, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 14, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 45, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 180, "opened_days": None})
        elif ing_id in ("spinach", "coriander_leaves", "mint_leaves", "fenugreek_leaves", "radish_leaves", "dill_leaves", "amaranth_leaves"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 4, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 1, "opened_days": 1})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 30, "opened_days": None})
        elif ing_id in ("mushroom", "green_peas"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 5, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 180, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 2, "opened_days": 1})
        else:
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 7, "opened_days": 3})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 3, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "PANTRY", "days": 5, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 90, "opened_days": None})

    elif cat == "Fruits":
        if ing_id in ("banana", "papaya", "guava", "sweet_lime"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 4, "opened_days": 1})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 7, "opened_days": 2})
        elif ing_id in ("dates", "amla"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "PANTRY", "days": 90, "opened_days": 45})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 180, "opened_days": 60})
        else:
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 10, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 4, "opened_days": 1})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 90, "opened_days": None})

    elif cat == "Dairy and Eggs":
        if ing_id == "ghee":
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "PANTRY", "days": 180, "opened_days": 90})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 365, "opened_days": 180})
        elif ing_id == "milk":
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 4, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 1, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 60, "opened_days": None})
        elif ing_id in ("curd", "paneer", "buttermilk", "hung_curd"):
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 5, "opened_days": 2})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 60, "opened_days": None})
        elif ing_id == "eggs":
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 28, "opened_days": None})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 10, "opened_days": None})
        else:
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 14, "opened_days": 5})
            SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 90, "opened_days": None})

    elif cat == "Proteins":
        SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 2, "opened_days": 1})
        SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FREEZER", "days": 90, "opened_days": 30})

    elif cat in ("Grains and Pulses", "Spices", "Oils and Condiments", "Other"):
        SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "PANTRY", "days": 365, "opened_days": 180})
        SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "COUNTER", "days": 180, "opened_days": 90})
        SHELF_LIFE.append({"ingredient_id": ing_id, "storage": "FRIDGE", "days": 365, "opened_days": 180})

print(f"Total shelf-life records generated: {len(SHELF_LIFE)}")

# Write ingredients.json and shelf_life.json
with open(DATA_DIR / "ingredients.json", "w", encoding="utf-8") as f:
    json.dump(INGREDIENTS, f, indent=2, ensure_ascii=False)

with open(DATA_DIR / "shelf_life.json", "w", encoding="utf-8") as f:
    json.dump(SHELF_LIFE, f, indent=2, ensure_ascii=False)

print("Wrote ingredients.json and shelf_life.json!")
