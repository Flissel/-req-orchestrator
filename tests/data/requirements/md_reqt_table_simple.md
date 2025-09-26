# Requirements Table (Simple)

| ID      | Title               | Description                                                    | Priority | Acceptance                                                              |
|---------|---------------------|----------------------------------------------------------------|----------|-------------------------------------------------------------------------|
| REQ-001 | Login               | User can log in with email and password                       | MUST     | Given valid creds, When login, Then dashboard is shown                 |
| REQ-002 | Logout              | User can logout from any page                                  | MUST     | Given logged in, When logout, Then session is destroyed                 |
| REQ-003 | Password Reset      | User requests password reset via email                         | SHOULD   | Given email, When reset requested, Then mail sent with token            |
| REQ-004 | Session Timeout     | Auto-logout after inactivity                                   | SHOULD   | Given idle 30m, When no activity, Then user is logged out              |
| REQ-005 | 2FA                 | Optional two-factor authentication                             | COULD    | Given 2FA enabled, When login, Then OTP requested                      |
| REQ-006 | Rate Limiting       | Limit login attempts                                            | MUST     | Given > 5 failed attempts, When next attempt, Then block 15m           |
| REQ-007 | Audit Log           | Record auth events                                              | SHOULD   | Given auth events, When occur, Then persisted with user/timestamp      |
| REQ-008 | i18n                | UI supports DE and EN                                           | COULD    | Given language preference, When set, Then UI labels localized          |
| REQ-009 | Accessibility       | WCAG AA basics                                                  | SHOULD   | Given keyboard only, When navigating, Then controls operable           |
| REQ-010 | Password Policy     | Min length 12, complexity rules                                 | MUST     | Given new password, When set, Then policy validated                    |
| REQ-011 | Account Lock        | Lock account after repeated failures                            | MUST     | Given 10 failures/24h, When threshold hit, Then lock until admin unlock|
| REQ-012 | Email Verify        | Verify email on signup                                          | SHOULD   | Given signup, When verify link clicked, Then account active            |