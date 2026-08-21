# Publishing to Ansible Galaxy

## One-time setup

1. Sign in to [Ansible Galaxy](https://galaxy.ansible.com/) with the GitHub
   account that owns the `soupglasses` namespace.
2. Under **Collections → Namespaces**, create or claim the `soupglasses`
   namespace and ensure your Galaxy account is an owner.
3. Under **Collections → API token management**, generate an API token.
   Generating another token invalidates the previous one.
4. In the GitHub repository, create an Actions secret named
   `GALAXY_API_KEY` containing the token.

The repository's release workflow publishes to Galaxy whenever a GitHub
release is published.

## Release procedure

1. Update `version` in `galaxy.yml` using semantic versioning.
2. Add the release notes to `CHANGELOG.md`.
3. Run the sanity, unit, and integration tests.
4. Merge the release changes, tag the commit with the matching version (for
   example `1.0.0`), and publish a GitHub release for that tag.
5. Check the **Publish collection** workflow and Galaxy's import log.

Galaxy collection versions are immutable. Increment `galaxy.yml` before every
publication.

## Manual publication

To build and inspect the artifact locally:

```bash
ansible-galaxy collection build --output-path dist
tar -tzf dist/soupglasses-stow-1.0.0.tar.gz
```

Publish it without storing the token in the repository:

```bash
ansible-galaxy collection publish \
  dist/soupglasses-stow-1.0.0.tar.gz \
  --api-key "$GALAXY_API_KEY"
```
