# Technical Troubleshooting Guide

## First steps for any technical report

Before escalating, collect:

- The exact error message, if any
- What the customer was doing when it happened
- The device, operating system and app or browser version
- Whether the issue happens every time or intermittently

Ask the customer to sign out and back in, clear the app cache, and retry. This
resolves a large share of issues caused by stale tokens or cached assets.

## The app will not load or shows a blank screen

1. Confirm the customer has a working internet connection.
2. Ask them to force-close and reopen the app, or hard-refresh the browser.
3. Clear the cache and stored data for the app, then sign in again.
4. Check the status page for an ongoing incident before investigating further.

If the app still fails to load after these steps, capture the browser console
errors or the app's error screen and escalate as a technical issue with high
priority.

## Payments fail or are declined

Payment failures are almost always issued by the bank or payment gateway, not by
the platform. Review the payment error code on the order:

- A "declined" code means the bank refused the charge; the customer should try
  another method or contact their bank.
- A "pending" code means the gateway has not settled the charge; it usually
  resolves within 30 minutes, after which the order can be retried.
- A "timeout" code means the gateway never received a response; the order should
  be retried and any duplicate charge refunded.

Never advise a customer to retry a payment more than twice; repeated retries can
create duplicate holds.

## Sync and data issues

If recent changes are not showing, ask the customer to pull to refresh, then check
whether the change was saved on another device. Intermittent sync problems that
persist across devices should be escalated with the account email and the
approximate time of the missing change.

## Push notifications not arriving

Confirm notifications are enabled for the app in the device settings, that the
app has permission, and that "Do not disturb" is off. Notification delivery is
best-effort and can be delayed by the operating system's battery optimisation.

## File uploads failing

Uploads fail when a file exceeds 25 MB or is in an unsupported format. Supported
formats are PDF, PNG, JPG and CSV. Ask the customer to compress or convert the
file and retry. If a supported file under the limit still fails, escalate with the
file type and size.
