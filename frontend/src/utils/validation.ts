/** Client-side validation. It improves feedback only; the backend validates everything again. */

export const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export const MIN_PASSWORD_LENGTH = 12;

export type FieldErrors = Record<string, string>;

export function validateLogin(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!email.trim()) errors.email = "Enter your email address.";
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = "Enter a valid email address, such as name@college.edu.";
  if (!password) errors.password = "Enter your password.";
  return errors;
}

export function validateNewPassword(
  currentPassword: string,
  newPassword: string,
  confirmation: string,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!currentPassword) errors.currentPassword = "Enter your current password.";
  if (newPassword.length < MIN_PASSWORD_LENGTH) {
    errors.newPassword = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  } else if (newPassword === currentPassword) {
    errors.newPassword = "Choose a password different from your current one.";
  } else {
    const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((pattern) => pattern.test(newPassword));
    if (classes.length < 3) {
      errors.newPassword = "Mix at least three of: lower case, upper case, digits and symbols.";
    }
  }
  if (confirmation !== newPassword) errors.confirmation = "The two passwords do not match.";
  return errors;
}

export function validateNewUser(input: {
  email: string;
  fullName: string;
  initialPassword: string;
}): FieldErrors {
  const errors: FieldErrors = {};
  if (!EMAIL_PATTERN.test(input.email.trim())) errors.email = "Enter a valid email address.";
  if (input.fullName.trim().length < 2) errors.fullName = "Enter the person's full name.";
  if (input.initialPassword.length < MIN_PASSWORD_LENGTH) {
    errors.initialPassword = `The temporary password needs at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return errors;
}
