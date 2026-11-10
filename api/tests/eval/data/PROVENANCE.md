# Vision Evaluation Dataset: Provenance, Taxonomy & Metadata

**Version:** 1.0  
**Total Scenarios:** 42  
**Target Ingredients Evaluated:** 30 common Indian ingredients per PRD Section 14.4  

---

## 1. Dataset Design & Taxonomy

The dataset models realistic home kitchen ingredient scanning scenarios across four primary environments:
- **FRIDGE**: Crisper drawers, wire/glass shelves, door racks.
- **FREEZER**: Frozen vegetables, poultry, ice trays.
- **PANTRY**: Dry onion/garlic wire baskets, dry root bins, ghee/oil shelves.
- **COUNTER**: Chopping boards, prep bowls, fruit baskets.

### 1.1 Environmental Variations
- **Lighting Conditions**:
  - `GOOD_LIGHT`: Direct overhead kitchen lighting or daylight.
  - `DIM_INTERIOR`: Weak internal refrigerator bulb lighting.
  - `HARSH_GLARE`: High-contrast reflections from plastic packaging or freezer frost.
  - `SHADOW`: Items partially shaded in corners or deep drawers.
- **Clutter Levels**:
  - `SPARSE`: 1–3 well-separated items.
  - `MODERATE`: 4–5 items grouped together.
  - `CLUTTERED`: Tightly packed items with partial occlusions and condiment jars.

### 1.2 Edge Cases and Challenges Included
1. **Visually Similar Pairs**:
   - Mint leaves (`mint_leaves`) vs Coriander leaves (`coriander_leaves`) (Scenario 5).
   - Fenugreek leaves (`fenugreek_leaves`) vs Spinach (`spinach`) (Scenario 7).
   - Ginger root (`ginger`) vs Turmeric root.
   - Cabbage (`cabbage`) vs Lettuce/Cauliflower florets.
2. **Partial Occlusions**:
   - Scenario 14: Green chillies hidden behind shadows in a dim drawer (simulating false negatives).
   - Scenario 31: Carrots partially hidden behind a water pitcher (false negative challenge).
3. **Uncertainty & Unmapped Items**:
   - Scenario 15: An unlabeled homemade pickle jar in a crowded door rack (triggering user review).
   - Scenario 35: A translucent container with cooked leftovers (unmapped item).
4. **Negative Controls**:
   - Scenario 40: Clean empty refrigerator glass shelf (zero hallucination verification).
   - Scenario 41: Clean empty granite kitchen counter with only utensils (zero hallucination verification).

---

## 2. Image Asset Provenance

- **Origin**: Generated programmatically using Pillow under `api/scripts/generate_eval_dataset.py`.
- **Licensing & Legal Status**: 100% synthetic and proprietary to the FridgeChef project. Completely free of copyright restrictions, external web scraping, or third-party proprietary data.
- **Format**: Conforms strictly to PRD Section 6.3 / FR-023:
  - Resolution: 800x600 pixels (well within the <= 1600px long edge limit).
  - Format: Standard baseline JPEG, quality 85.
  - Metadata: EXIF stripped.
  - Size: ~30-40 KB per image (far below the 4MB limit).

---

## 3. Coverage of 30 Common Indian Ingredients

| Canonical ID | Display Name | Scenario Occurrences (Support) |
| :--- | :--- | :--- |
| `onion` | Onion | 10 |
| `green_chilli` | Green Chilli | 9 |
| `tomato` | Tomato | 8 |
| `ginger` | Ginger | 7 |
| `curd` | Curd (Dahi) | 7 |
| `lemon` | Lemon | 7 |
| `garlic` | Garlic | 6 |
| `curry_leaves` | Curry Leaves | 5 |
| `paneer` | Paneer | 5 |
| `milk` | Milk | 5 |
| `butter` | Butter | 5 |
| `potato` | Potato | 4 |
| `capsicum` | Capsicum | 4 |
| `carrot` | Carrot | 4 |
| `green_peas` | Green Peas | 4 |
| `ghee` | Ghee | 4 |
| `cucumber` | Cucumber | 4 |
| `mint_leaves` | Mint Leaves | 4 |
| `spinach` | Spinach | 3 |
| `okra` | Okra (Bhindi) | 3 |
| `eggs` | Eggs | 3 |
| `chicken_curry_cut` | Chicken Curry Cut | 3 |
| `mushroom` | Mushroom | 3 |
| `coconut_fresh` | Fresh Coconut | 3 |
| `apple` | Apple | 3 |
| `banana` | Banana | 3 |
| `coriander_leaves` | Coriander Leaves | 2 |
| `cauliflower` | Cauliflower | 2 |
| `cabbage` | Cabbage | 2 |
| `fenugreek_leaves` | Fenugreek Leaves (Methi) | 2 |

**Total Unique Common Ingredients:** 30 / 30 (100% Coverage).
