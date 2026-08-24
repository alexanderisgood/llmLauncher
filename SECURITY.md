# Security policy

LLM Launcher starts local inference engines, creates authenticated loopback bridges, and can open coding agents inside user-selected project folders. Security reports are therefore taken seriously even during the alpha period.

## Supported versions

Only the latest tagged alpha release and the current `main` branch receive security fixes.

## Reporting a vulnerability

Do not publish suspected vulnerabilities, credentials, private prompts, model paths, logs, or exploit details in a public issue.

Use GitHub's private vulnerability reporting flow:

1. Open the repository's **Security** tab.
2. Choose **Advisories**.
3. Choose **Report a vulnerability**.

Include the affected version, macOS version, engine and work surface involved, impact, and the smallest safe reproduction you can provide. Remove API keys, prompts, generated text, usernames, and private filesystem paths.

Useful report categories include authentication bypasses, command or argument injection, unintended network exposure, credential disclosure, unsafe remote-endpoint handling, arbitrary file writes or deletion, symlink/path traversal, and stopping a process the launcher does not own.

Reports will be acknowledged and triaged on a best-effort basis. Please allow time for a coordinated fix before public disclosure.

## Security boundaries

- The browser controller and generated model routes bind to loopback addresses.
- A coding agent can access files allowed by that agent and operating-system account; LLM Launcher is not a sandbox.
- Models, runtimes, and agent extensions are third-party inputs and must be obtained from trusted sources.
- Remote FreeToken support is currently hidden from the interface.
