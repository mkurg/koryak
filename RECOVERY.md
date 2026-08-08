# Project recovery

The authoritative Git-tracked project history and versioned files are on
GitHub.

Files intentionally excluded from Git—including raw inputs, large generated
artifacts, local analysis environments, and local-only Git recovery
metadata—are in a timestamped project backup on Google Drive. That backup
contains an inventory, SHA-256 checksums, restore instructions, and a verified
archive of every ignored or untracked path present when this repository was
archived.

To recover the project:

1. Clone the repository from GitHub.
2. Retrieve the latest timestamped project backup from Google Drive.
3. Follow the backup's `README.md` to verify and restore the non-GitHub files.

The repository and the Google Drive backup together form the complete project
recovery set.
