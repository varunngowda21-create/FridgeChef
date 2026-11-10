/**
 * User-facing error message mapping for all backend error codes per PRD Section 11 and 12.5.
 */

export const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: 'Please check the information you entered and try again.',
  UNAUTHORIZED: 'Your session has expired or you are not logged in. Please sign in.',
  FORBIDDEN: 'You do not have permission to access this resource.',
  NOT_FOUND: 'The requested resource was not found.',
  USER_NOT_FOUND: 'Account not found with this email.',
  INCORRECT_PASSWORD: 'Email or password is incorrect.',
  EMAIL_EXISTS: 'An account with this email address already exists.',
  INVALID_TOKEN: 'Your session token is invalid. Please sign in again.',
  REFRESH_TOKEN_EXPIRED: 'Your login session has expired. Please log in again.',
  REFRESH_TOKEN_REVOKED: 'This session has been logged out. Please sign in again.',
  IMAGE_TOO_LARGE: 'Image is too large. Maximum allowed size is 8MB.',
  UNSUPPORTED_MEDIA_TYPE: 'Unsupported format. Please upload a JPEG, PNG, WEBP, or HEIC image.',
  IMAGE_UNREADABLE: 'The photo could not be processed. Please try another shot with better lighting.',
  SCAN_LIMIT_REACHED: 'You have reached the daily limit of 20 scans.',
  SCAN_SESSION_EXPIRED: 'This scan session has expired. Please take a new photo.',
  VISION_UNAVAILABLE: 'AI vision recognition is temporarily unavailable. You can add items manually below.',
  CANONICAL_ID_REQUIRED: 'Item requires a valid ingredient from the catalogue.',
  STORAGE_NOT_APPLICABLE: 'The selected storage location is not suitable for this ingredient. Please choose another storage type.',
  INVENTORY_ITEM_NOT_FOUND: 'Inventory item not found.',
  RECIPE_NOT_FOUND: 'Recipe not found.',
  MEAL_PLAN_NOT_FOUND: 'No meal plan found.',
  SHOPPING_LIST_NOT_FOUND: 'Shopping list not found.',
  PLAN_ID_REQUIRED: 'A valid meal plan is required to generate a shopping list.',
  RECIPES_REQUIRED: 'Please select at least one recipe.',
  MANUAL_ITEMS_REQUIRED: 'Please add at least one item.',
  INVALID_DATE: 'Date is invalid.',
  INTERNAL_SERVER_ERROR: 'An unexpected server error occurred. Please try again later.',
};

export function getErrorMessage(code?: string, fallbackMessage?: string): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return fallbackMessage || 'An unexpected error occurred. Please try again.';
}

