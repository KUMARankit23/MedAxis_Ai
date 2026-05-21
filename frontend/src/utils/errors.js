/**
 * Safely extract a human-readable string from any axios/API error.
 * Never returns an object — always returns a string.
 */
export function getErrorMessage(err, fallback = 'An error occurred') {
  if (!err) return fallback;
  try {
    const detail = err.response?.data?.detail;
    if (!detail) return err.message || fallback;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      // Pydantic validation errors: [{loc, msg, type}]
      return detail.map(d => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : 'field';
        return `${field}: ${d.msg}`;
      }).join('; ');
    }
    if (typeof detail === 'object') {
      return detail.error || detail.message || JSON.stringify(detail);
    }
    return String(detail);
  } catch {
    return fallback;
  }
}
