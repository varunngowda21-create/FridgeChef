import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Core User Journey: Registration to Meal Planning, Logout & Deletion', () => {
  test('executes complete end-to-end user journey across all functional areas', async ({ page }) => {
    const timestamp = Date.now();
    const testUser = {
      displayName: 'Aarav E2E',
      email: `e2e_user_${timestamp}@example.com`,
      password: 'Password123!',
    };

    // ------------------------------------------------------------------------
    // 1. REGISTRATION & SESSION ESTABLISHMENT
    // ------------------------------------------------------------------------
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: /Create your account/i })).toBeVisible();

    await page.locator('#name').fill(testUser.displayName);
    await page.locator('#reg-email').fill(testUser.email);
    await page.locator('#reg-password').fill(testUser.password);
    await page.getByRole('button', { name: /Create Account/i }).click();

    // Directs newly registered user to onboarding wizard
    await page.waitForURL('**/onboarding');
    await expect(page).toHaveURL(/.*\/onboarding/);

    // ------------------------------------------------------------------------
    // 2. ONBOARDING & PREFERENCES SETUP
    // ------------------------------------------------------------------------
    // Step 1: Household & Diet
    await expect(page.getByRole('heading', { name: /Household & Dietary Habits/i })).toBeVisible();
    await page.getByRole('button', { name: /^Vegetarian/i }).click();
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 2: Regional Cuisines & Spice Level
    await expect(page.getByRole('heading', { name: /Flavors & Regional Cuisines/i })).toBeVisible();
    await page.getByRole('button', { name: /Medium/i }).click();
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 3: Allergies & Time Constraints
    await expect(page.getByRole('heading', { name: /Allergies & Time Constraints/i })).toBeVisible();
    await page.getByRole('button', { name: /Complete Setup/i }).click();

    // Lands on Dashboard
    await page.waitForURL('**/');
    await expect(page.getByText(/FridgeChef/i).first()).toBeVisible();

    // ------------------------------------------------------------------------
    // 3. INGREDIENT SCAN USING DETERMINISTIC TEST FIXTURE (PRD Section 14.6)
    // ------------------------------------------------------------------------
    // Setup deterministic scan mock per PRD Section 14.6: "scan (fixture image with mocked backend response)"
    const mockScanId = 'e2e00000-0000-0000-0000-000000000001';
    const mockScanSession = {
      scan_id: mockScanId,
      status: 'PENDING_VERIFY',
      expires_at: new Date(Date.now() + 3600000).toISOString(),
      image_quality: 'GOOD',
      image_quality_note: null,
      candidates: [
        {
          candidate_id: '11111111-1111-1111-1111-111111111111',
          name: 'Tomato',
          canonical_id: 'tomato',
          quantity: 4,
          unit: 'piece',
          storage_guess: 'FRIDGE',
          confidence: 'HIGH',
          needs_review: false,
          visible_note: 'Fresh round red tomatoes',
        },
        {
          candidate_id: '22222222-2222-2222-2222-222222222222',
          name: 'Potato',
          canonical_id: 'potato',
          quantity: 3,
          unit: 'piece',
          storage_guess: 'FRIDGE',
          confidence: 'HIGH',
          needs_review: false,
          visible_note: 'Unpeeled potatoes',
        },
        {
          candidate_id: '33333333-3333-3333-3333-333333333333',
          name: 'Green Chilli',
          canonical_id: 'green_chilli',
          quantity: 6,
          unit: 'piece',
          storage_guess: 'FRIDGE',
          confidence: 'MEDIUM',
          needs_review: false,
          visible_note: 'Slender green chillies',
        },
        {
          candidate_id: '44444444-4444-4444-4444-444444444444',
          name: 'Onion',
          canonical_id: 'onion',
          quantity: 4,
          unit: 'piece',
          storage_guess: 'PANTRY',
          confidence: 'HIGH',
          needs_review: false,
          visible_note: 'Medium red onions',
        },
        {
          candidate_id: '55555555-5555-5555-5555-555555555555',
          name: 'Ginger',
          canonical_id: 'ginger',
          quantity: 50,
          unit: 'g',
          storage_guess: 'FRIDGE',
          confidence: 'HIGH',
          needs_review: false,
          visible_note: 'Fresh ginger root',
        },
        {
          candidate_id: '66666666-6666-6666-6666-666666666666',
          name: 'Curd',
          canonical_id: 'curd',
          quantity: 500,
          unit: 'g',
          storage_guess: 'FRIDGE',
          confidence: 'HIGH',
          needs_review: false,
          visible_note: 'Fresh plain curd',
        },
      ],
    };

    // Route scan endpoints to avoid live AI vision calls
    await page.route('**/api/v1/scans', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(mockScanSession),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(`**/api/v1/scans/${mockScanId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockScanSession),
      });
    });

    // When confirming candidates, populate real database inventory so downstream steps work seamlessly
    await page.route(`**/api/v1/scans/${mockScanId}/confirm`, async (route) => {
      const postData = route.request().postDataJSON();
      const authHeader = route.request().headers()['authorization'] || '';

      const createdItems = [];
      for (const item of postData.items) {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/v1/inventory', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': authHeader,
            },
            body: JSON.stringify({
              canonical_id: item.canonical_id,
              quantity: item.quantity,
              unit: item.unit,
              storage: item.storage,
            }),
          });
          if (res.ok) {
            createdItems.push(await res.json());
          }
        } catch {
          // ignore
        }
      }

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ created: createdItems, skipped: [] }),
      });
    });

    await page.goto('/scan');
    await expect(page.getByRole('heading', { name: /Scan Fridge or Pantry/i })).toBeVisible();

    // Upload real baseline fixture image through the file input
    const fixturePath = path.resolve(__dirname, 'fixtures/fridge_fixture.jpg');
    const fileInput = page.locator('input[aria-label="Upload photo from library"]');
    await fileInput.setInputFiles(fixturePath);

    // ------------------------------------------------------------------------
    // 4. SCAN CANDIDATE REVIEW & CONFIRMATION
    // ------------------------------------------------------------------------
    await page.waitForURL(`**/scan/${mockScanId}/verify`);
    await expect(page.getByRole('heading', { name: /Verify Items/i })).toBeVisible();

    // Verify candidates are rendered
    await expect(page.getByText('Tomato').first()).toBeVisible();
    await expect(page.getByText('Potato').first()).toBeVisible();
    await expect(page.getByText('Green Chilli').first()).toBeVisible();

    // Confirm scan candidates to fridge
    const saveButton = page.getByRole('button', { name: /Save.*to Fridge/i });
    await expect(saveButton).toBeVisible();
    await saveButton.click();

    // ------------------------------------------------------------------------
    // 5. INVENTORY VIEWING & MODIFICATION
    // ------------------------------------------------------------------------
    await page.waitForURL('**/inventory');
    await expect(page.getByRole('heading', { name: /Kitchen Inventory/i })).toBeVisible();

    // Verify confirmed items exist in inventory
    await expect(page.getByText('Tomato').first()).toBeVisible();
    await expect(page.getByText('Potato').first()).toBeVisible();
    await expect(page.getByText('Green Chilli').first()).toBeVisible();

    // Test Search input filtering
    const searchInput = page.getByPlaceholder(/Search items in your fridge/i);
    await searchInput.fill('Tomato');
    await expect(page.getByText('Tomato').first()).toBeVisible();
    await expect(page.getByText('Potato')).not.toBeVisible();
    await searchInput.clear();

    // Test Item Use flow
    const markUsedButton = page.getByRole('button', { name: /^Used$/i }).first();
    await markUsedButton.click();
    await expect(page.getByRole('heading', { name: /^Used /i })).toBeVisible();
    await page.locator('input[type="number"]').fill('1');
    await page.getByRole('button', { name: /^Confirm$/i }).click();

    // Test Manual Addition
    await page.getByRole('button', { name: /Add Item/i }).click();
    await expect(page.getByRole('heading', { name: /Add Fridge Item/i })).toBeVisible();
    await page.locator('input[placeholder*="Tomato, Paneer"]').fill('Paneer');
    await page.getByRole('dialog').getByRole('button', { name: 'Add Item' }).click();
    await expect(page.getByText('Paneer').first()).toBeVisible();

    // ------------------------------------------------------------------------
    // 6. RECIPE DISCOVERY & COOKING FLOW
    // ------------------------------------------------------------------------
    await page.goto('/recommendations');
    await expect(page.getByRole('heading', { name: /Recipe Recommendations/i })).toBeVisible();

    // Wait for ranked recipe cards to load and click the first recipe
    const firstRecipe = page.locator('h4').first();
    await expect(firstRecipe).toBeVisible();
    await firstRecipe.click();

    // Recipe detail modal
    await expect(page.getByRole('button', { name: /Cooked this!/i })).toBeVisible();

    // Adjust servings
    await page.locator('button[aria-label="Increase servings"]').click();

    // Record cooked event
    await page.locator('button[aria-label="Rate 5 stars"]').click();
    await page.getByRole('button', { name: /Cooked this!/i }).click();

    await expect(page.getByText(/Cooked! Inventory updated/i)).toBeVisible();
    await page.getByRole('button', { name: /Done/i }).click();

    // ------------------------------------------------------------------------
    // 7. MEAL PLANNING WITH 14 WEEKLY SLOTS & SLOT LOCKING
    // ------------------------------------------------------------------------
    await page.goto('/plan');

    // Wait for either the plan to be loaded or the "Generate 7-Day Plan" button to appear
    const planHeading = page.getByRole('heading', { name: /7-Day Meal Plan/i });
    const generatePlanBtn = page.getByRole('button', { name: /Generate 7-Day Plan/i });
    await expect(planHeading.or(generatePlanBtn)).toBeVisible({ timeout: 15000 });

    if (await generatePlanBtn.isVisible()) {
      await generatePlanBtn.click();
      await expect(planHeading).toBeVisible({ timeout: 15000 });
    }

    // Assert all 14 weekly meal slots exist (7 days × 2 meals: Lunch and Dinner)
    const lockButtons = page.locator('button[aria-label="Lock slot"]');
    await expect(lockButtons).toHaveCount(14);
    await expect(page.locator('button[aria-label="Regenerate this slot"]')).toHaveCount(14);

    // Assert slot-locking behavior: lock the first slot
    await lockButtons.first().click();
    // Exactly 1 slot is now locked with Unlock aria-label
    await expect(page.locator('button[aria-label="Unlock slot"]')).toHaveCount(1);
    // Exactly 13 slots remain unlocked
    await expect(page.locator('button[aria-label="Lock slot"]')).toHaveCount(13);
    // Locked slot's regenerate button is disabled
    await expect(page.locator('button:disabled[aria-label="Regenerate this slot"]')).toHaveCount(1);

    // Assert unlocked slot regeneration
    const regenButton = page.locator('button:not(:disabled)[aria-label="Regenerate this slot"]').first();
    await expect(regenButton).toBeVisible();
    await regenButton.click();
    // Verify regeneration retains the locked slot
    await expect(page.locator('button[aria-label="Unlock slot"]')).toHaveCount(1);

    // ------------------------------------------------------------------------
    // 8. SHOPPING LIST GENERATION & INTERACTION
    // ------------------------------------------------------------------------
    // Navigate via "Get Shopping List" button directly from the meal plan view
    const getShoppingBtn = page.getByRole('button', { name: /Get Shopping List/i });
    await expect(getShoppingBtn).toBeVisible();
    await getShoppingBtn.click();

    await page.waitForURL('**/shopping');
    await expect(page.getByRole('heading', { name: /Shopping List/i })).toBeVisible();

    // Verify aggregated total estimated cost is visible and calculated
    await expect(page.getByText(/Total Estimated Cost/i)).toBeVisible();

    // Toggle an item as bought and verify purchased count reflects the update
    const toggleBoughtCheckbox = page.locator('input[type="checkbox"][aria-label^="Mark "]').first();
    await expect(toggleBoughtCheckbox).toBeVisible();
    await toggleBoughtCheckbox.click();
    await expect(page.getByText(/1 of \d+ items purchased/i)).toBeVisible();

    // ------------------------------------------------------------------------
    // 9. SETTINGS, PREFERENCE PERSISTENCE & USER LOGOUT
    // ------------------------------------------------------------------------
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /Settings & Preferences/i })).toBeVisible();
    await expect(page.getByText(testUser.email)).toBeVisible();

    // Verify onboarding dietary preferences were persisted in backend database
    await expect(page.getByRole('button', { name: /^Vegetarian$/i })).toHaveClass(/border-brand-600/);
    await expect(page.getByRole('button', { name: /^MEDIUM$/i })).toHaveClass(/border-brand-600/);

    // Update spice level preference in settings
    await page.getByRole('button', { name: /^HOT$/i }).click();
    await page.getByRole('button', { name: /Save Preferences/i }).click();
    await expect(page.getByText(/Preferences updated successfully!/i)).toBeVisible();

    // Verify persistence across page reload
    await page.reload();
    await expect(page.getByRole('heading', { name: /Settings & Preferences/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /^HOT$/i })).toHaveClass(/border-brand-600/);

    // Test Sign Out (Logout)
    await page.getByRole('button', { name: /Sign Out/i }).click();
    await page.waitForURL('**/login');
    await expect(page).toHaveURL(/.*\/login/);

    // Verify unauthenticated access is immediately blocked after logout
    await page.goto('/inventory');
    await page.waitForURL('**/login');
    await expect(page).toHaveURL(/.*\/login/);

    // Re-authenticate with test credentials
    await page.locator('#email').fill(testUser.email);
    await page.locator('#password').fill(testUser.password);
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Verify returning authenticated user lands directly on Dashboard
    await page.waitForURL('**/');
    await expect(page).toHaveURL(/.*\/$/);

    // ------------------------------------------------------------------------
    // 10. PERMANENT ACCOUNT DELETION & DATABASE PURGE
    // ------------------------------------------------------------------------
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /Settings & Preferences/i })).toBeVisible();

    await page.getByRole('button', { name: /Delete Account Permanently/i }).click();
    await expect(page.getByRole('heading', { name: /Delete Account/i })).toBeVisible();

    await page.locator('input[type="password"]').fill(testUser.password);
    await page.getByRole('button', { name: /Delete My Account/i }).click();

    // Verifies account is purged and user is redirected to /login
    await page.waitForURL('**/login');
    await expect(page).toHaveURL(/.*\/login/);
    await expect(page.getByRole('heading', { name: /Welcome to FridgeChef/i })).toBeVisible();

    // Verify permanent database purge: attempting to log back in with deleted account fails
    await page.locator('#email').fill(testUser.email);
    await page.locator('#password').fill(testUser.password);
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('alert')).toContainText(/Invalid email or password/i);
  });
});
