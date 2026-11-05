# ADR 0003: Use GitHub's own features for every interactive service

Date: 2026-11-05. Status: accepted.

## Context
The portal needs a contact route, a way to report page problems, a community space, release notes, health monitoring and hosting,
without relying on any other platform.

## Options
1. A separate form service and analytics. Adds suppliers, cookies and a privacy assessment.
2. GitHub only: issue forms for contact and problem reports, Discussions, releases, scheduled Actions for health, and Pages for hosting.

## Decision
Option 2. Progress tracking and display choices stay in the reader's browser. The contact form builds a pre-filled issue; nothing is stored by the portal.

## Consequences
People need a free GitHub account to send a message, and messages are public (open item OR-02). Everything else works without an account.
