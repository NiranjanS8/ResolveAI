# Password Reset and Two-Factor Authentication

## Resetting a forgotten password

1. Open the login page and select "Forgot password".
2. Enter the email address on the account.
3. Open the reset email and follow the link within 30 minutes.
4. Choose a new password of at least 10 characters.

Reset links expire after 30 minutes and can be used only once. If the link has
expired, request a new one. Customers can request at most 5 reset emails per hour;
beyond that, the account is locked for 1 hour as a precaution.

If no reset email arrives within 10 minutes, ask the customer to check spam and
confirm that the address matches the one on the account. Support cannot reveal
whether a given email is registered; instead, ask the customer to try signing in
with each address they may have used.

## Two-factor authentication

2FA can be enabled from Settings → Security. We support authenticator apps (TOTP)
and SMS one-time codes. Recovery codes are issued once when 2FA is enabled; each
code works a single time and customers should store them somewhere safe.

## Lost 2FA device

If a customer has lost both their 2FA device and recovery codes, identity must be
verified before 2FA is reset. Verification requires two of the following:

- A recent order number
- The last four digits of the payment method on file
- The billing address on the account

If the customer cannot satisfy two checks, the request must be escalated to the
account security team. Support must never disable 2FA on the strength of a single
check.

## Locked accounts

Accounts lock for 30 minutes after 10 failed sign-in attempts. Locked accounts
unlock automatically; support cannot unlock them early. Repeated lockouts should be
escalated, as they may indicate an attempted compromise.

## Suspicious sign-in alerts

Customers receive an email whenever a sign-in happens from a new device. If a
customer reports an alert they do not recognise, advise them to change their
password immediately, enable 2FA, and sign out of all other sessions from
Settings → Security → Active sessions.
