# Run184 note session capture: login method

Google may reject sign-in from automation-controlled browsers with a "browser or app may not be secure" screen. Do not retry Google OAuth inside the Playwright capture browser and do not attempt to bypass Google's security checks.

For the one-time session capture, use note's first-party login form with the account's registered email address (or note ID) and note password. note officially supports email/note ID + password login. If the password is unknown, reset it from a normal browser using the registered email address, then return to the capture helper.

The capture helper stores only the resulting note browser session as `note_storage_state.b64`; it does not print or persist the entered password.
