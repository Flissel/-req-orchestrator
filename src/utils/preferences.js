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
 * Get LLM provider preference
 * @returns {string} - Provider ('openai' or 'openrouter'), defaults to 'openai'
 */
export const getProviderPreference = () => {
  try {
    const prefs = localStorage.getItem(PREFERENCES_KEY)
    if (!prefs) return 'openai' // Default: OpenAI

    const parsed = JSON.parse(prefs)
    return parsed.provider || 'openai'
  } catch (error) {
    console.error('[Preferences] Failed to read provider preference:', error)
    return 'openai' // Fail-safe: default to OpenAI
  }
}

/**
 * Set LLM provider preference
 * @param {string} provider - Provider ('openai' or 'openrouter')
 */
export const setProviderPreference = (provider) => {
  try {
    const prefs = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}')
    prefs.provider = provider
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs))
    console.log('[Preferences] Provider preference saved:', provider)
  } catch (error) {
    console.error('[Preferences] Failed to save provider preference:', error)
  }
}

/**
 * Get model preference
 * @returns {string} - Model ID (e.g., 'gpt-4o-mini', 'anthropic/claude-haiku-4.5')
 */
export const getModelPreference = () => {
  try {
    const prefs = localStorage.getItem(PREFERENCES_KEY)
    if (!prefs) return 'gpt-4o-mini' // Default: OpenAI gpt-4o-mini

    const parsed = JSON.parse(prefs)
    return parsed.model || 'gpt-4o-mini'
  } catch (error) {
    console.error('[Preferences] Failed to read model preference:', error)
    return 'gpt-4o-mini' // Fail-safe: default to gpt-4o-mini
  }
}

/**
 * Set model preference
 * @param {string} model - Model ID (e.g., 'gpt-4o-mini', 'anthropic/claude-haiku-4.5')
 */
export const setModelPreference = (model) => {
  try {
    const prefs = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}')
    prefs.model = model
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs))
    console.log('[Preferences] Model preference saved:', model)
  } catch (error) {
    console.error('[Preferences] Failed to save model preference:', error)
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
