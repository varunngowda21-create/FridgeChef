import { test, expect } from '@playwright/test';

test.describe('Unauthenticated Route Protection & Auth Validation', () => {
  const protectedRoutes = [
    '/',
    '/inventory',
    '/scan',
    '/recommendations',
    '/plan',
    '/shopping',
    '/settings',
    '/onboarding',
  ];

  for (const route of protectedRoutes) {
    test(`redirects unauthenticated access from ${route} to /login`, async ({ page }) => {
      await page.goto(route);
      await page.waitForURL('**/login**');
      await expect(page).toHaveURL(/.*\/login/);
      await expect(page.getByRole('heading', { name: /Welcome to FridgeChef/i })).toBeVisible();
    });
  }

  test('validates login form required fields and error states', async ({ page }) => {
    await page.goto('/login');

    // Verify HTML5 required attributes prevent empty submission
    const emailInput = page.locator('#email');
    const passwordInput = page.locator('#password');
    await expect(emailInput).toHaveAttribute('required', '');
    await expect(passwordInput).toHaveAttribute('required', '');

    // Enter non-existent credentials
    await emailInput.fill('nonexistent_user_999@example.com');
    await passwordInput.fill('WrongPassword123');
    await page.getByRole('button', { name: /Sign In/i }).click();

    // Verify backend rejection error alert
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('alert')).toContainText(/Invalid email or password/i);
  });

  test('validates registration password complexity requirements', async ({ page }) => {
    await page.goto('/register');

    await page.locator('#name').fill('Test User');
    await page.locator('#reg-email').fill('test_complexity@example.com');

    // Short password without required complexity
    await page.locator('#reg-password').fill('short');
    await page.getByRole('button', { name: /Create Account/i }).click();

    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('alert')).toContainText(/at least 8 characters/i);
  });
});
