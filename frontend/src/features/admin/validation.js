// Client-side checks mirror the API's rules so most mistakes are caught
// before a request; the API validates everything again.

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateName(value, label = 'Name') {
  return value?.trim().length >= 2 ? null : `${label} must be at least 2 characters.`;
}

export function validateEmail(value) {
  return EMAIL_PATTERN.test(value?.trim() ?? '') ? null : 'Enter a valid email address.';
}

export function validatePassword(value) {
  if (!value || value.length < 8) return 'Password must be at least 8 characters.';
  if (value.length > 128) return 'Password must be at most 128 characters.';
  if (!/[A-Za-z]/.test(value)) return 'Password must contain at least one letter.';
  if (!/\d/.test(value)) return 'Password must contain at least one digit.';
  return null;
}

export function validateRange(value, min, max, label) {
  if (value === '' || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= min && number <= max
    ? null
    : `${label} must be a whole number from ${min} to ${max}.`;
}

export function validatePastDate(value) {
  if (!value) return null;
  return new Date(value) < new Date(new Date().toDateString())
    ? null
    : 'Date of birth must be in the past.';
}

/** Keep only the entries that hold an error message. */
export function onlyErrors(errors) {
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message));
}
