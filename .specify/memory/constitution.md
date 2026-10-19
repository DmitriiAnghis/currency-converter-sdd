<!--
Sync Impact Report
Version change: unversioned scaffold -> 1.0.0
Modified principles:
- Template principle 1 (unnamed) -> I. Python Desktop Application
- Template principle 2 (unnamed) -> II. GUI-Independent Core
- Template principle 3 (unnamed) -> III. Resilient Offline Operation
- Template principle 4 (unnamed) -> IV. Exact Monetary Arithmetic
- Template principle 5 (unnamed) -> V. Test-First Quality
Added sections: Additional Constraints; Development Workflow
Removed sections: None
Follow-up TODOs: None.
-->
# Currency Converter Constitution

## Core Principles

### I. Python Desktop Application
The application MUST use Python 3.12 and a Tkinter desktop GUI; it MUST NOT provide a console UI.
Use the Python standard library by default. Non-standard dependencies are limited to requests or
httpx for HTTP access and pytest for tests.

### II. GUI-Independent Core
The rate source client, XML parser, cache, conversion logic, and validation MUST be separate from
the GUI and MUST NOT import GUI modules. Parsing, conversion, and validation logic MUST be pure;
the rate client and cache MUST encapsulate network and filesystem I/O. The GUI MUST call these
modules rather than implement their responsibilities.

### III. Resilient Offline Operation
Recoverable network, parsing, and file errors MUST NOT terminate the application. The application
MUST show the user a clear message when these errors occur. The last successful source response
MUST be cached on disk and retained across restarts. Whenever cached data is used, its date MUST
be shown to the user.

### IV. Exact Monetary Arithmetic
Conversion calculations MUST use `decimal.Decimal`. Rates MUST retain the precision supplied by
the source; conversion results MUST be rounded to two decimal places using a documented and
consistent rounding rule.

### V. Test-First Quality
Every GUI-independent core module MUST have pytest unit tests. Tests MUST be written before
implementation of the behavior they cover. The complete test suite MUST run with
`python -m pytest`, and the README MUST document this command.

## Additional Constraints

The runtime dependency limit in Principle I applies to production and test dependencies. A GUI
dependency MUST NOT be introduced outside Tkinter. The separation in Principle II applies to all
modules: GUI code owns presentation and user interaction, while non-GUI modules own source access,
XML parsing, caching, conversion, and input validation.

## Development Workflow

Work MUST use a separate Git branch for each spec, implementation, and tests stage. Commits MUST
have meaningful messages. Changes MUST be merged into `main` only through a Pull Request.

## Governance

This constitution governs project decisions and supersedes conflicting informal practices.
Amendments MUST be proposed in a Pull Request with their rationale and impact on existing
principles. A change MUST NOT be treated as an approved amendment until the Pull Request is
reviewed and merged.

Constitution versions use semantic versioning. Increment MAJOR for backward-incompatible changes
to principles or governance, MINOR for new principles or materially expanded requirements, and
PATCH for clarifications and non-semantic edits. Update the version and last-amended date whenever
an amendment is merged.

Every Pull Request and review MUST check relevant changes for compliance with this constitution.
If a proposal conflicts with a principle, resolve the conflict by amending the constitution
through its Pull Request process before merging the implementation.

**Version**: 1.0.0 | **Ratified**: 2026-10-19 | **Last Amended**: 2026-10-19
