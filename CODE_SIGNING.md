# Code signing policy

Release binaries for this project are intended to be code-signed via
[SignPath Foundation](https://signpath.org/), which provides free certificates
to qualifying open-source projects. The signed binary is built from this public
repository by the GitHub Actions workflow in `.github/workflows/build.yml`.

- **Committers / reviewers:** project maintainers (see repository permissions).
- **Approvers:** repository owner(s).

Until signing is configured, release binaries are unsigned; verify the SHA-256
checksum published with each release (see the README).
