/**
 * preferences.js - LocalStorage wrapper for user preferences
 *
 * Manages persistent user settings in browser LocalStorage
 */

const PREFERENCES_KEY = 'req-orchestrator-preferences'

/**
 * Get auto-validate preference
 * @returns {boolean} - True if auto-validate is enabled, false otherwise
 */
export const getAutoValidatePreference = () => {
  try {
    const prefs = localStorage.getItem(PREFERENCES_KEY)
    if (!prefs) return false // Default: OFF (for cost control)

    const parsed = JSON.parse(prefs)
    return parsed.autoValidate === true
  } catch (error) {
    console.error('[Preferences] Failed to read auto-validate preference:', error)
    return false // Fail-safe: default to OFF
  }
}

/**
 * Set auto-validate preference
 * @param {boolean} enabled - True to enable auto-validate, false to disable
 */
export const setAutoValidatePreference = (enabled) => {
  try {
    const prefs = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}')
    prefs.autoValidate = enabled
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs))
    console.log('[Preferences] Auto-validate preference saved:', enabled)
  } catch (error) {
    console.error('[Preferences] Failed to save auto-validate preference:', error)
  }
}

/**
 * Get all preferences
 * @returns {object} - All preferences object
 */
export const getAllPreferences = () => {
  try {
    const prefs = localStorage.getItem(PREFERENCES_KEY)
    return prefs ? JSON.parse(prefs) : {}
  } catch (error) {
    console.error('[Preferences] Failed to read preferences:', error)
    return {}
  }
}

/**
 * Clear all preferences (useful for debugging)
 */
export const clearAllPreferences = () => {
  try {
    localStorage.removeItem(PREFERENCES_KEY)
    console.log('[Preferences] All preferences cleared')
  } catch (error) {
    console.error('[Preferences] Failed to clear preferences:', error)
  }
}
