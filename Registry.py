#
# Docker registry API for python - because the internet failed me!
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
#
# Docker registry API:
# https://docs.docker.com/registry/spec/api/
#

# Some REST helpers
# We should have one that understands pagination, but whatever

import requests

def json_get(url):
    """Get URL and return json or empty list on error"""

    r = requests.get(url)

    if r.status_code == 200:
        return r.json()

    if r.status_code == 404:
        return []

    if r.status_code == 400:
        print("Error 400 on %s (%s), making empty return" % (url, r.text.rstrip()))
        return []

    print("Error: %s (%s) getting %s" % (r.status_code, r.text.rstrip(), url))
    sys.exit(1)
    

class Registry:
    def __init__(self, registry, do_delete = False):
        self.registry = registry
        self.do_delete = do_delete
        self.debug = False
        self.verbose = False


    def get_repositories(self):
        return json_get("https://%s/v2/_catalog?n=10000" % self.registry)["repositories"]


    def get_tags(self, repo):
        """Get all tags for a repo"""

        j = json_get("https://%s/v2/%s/tags/list?n=10000" % (self.registry, repo))
        if "tags" not in j:
            return []

        return j["tags"]


    def get_manifest(self, repo, tag):
        """Get the manifest for a tag.  This requires two queries to
        the registry.  The first one gets the digest, the second one
        gets the manifest itself.  The digest will be needed if you
        want to delete the manifest.

        Return a tuple: digest, { manifest }

        On error returns: "", {}

        Bugs: No error information escapes from this function.

        """

        r = requests.get("https://%s/v2/%s/manifests/%s" % (self.registry, repo, tag), \
                         headers={"Accept": \
                                  "application/vnd.docker.distribution.manifest.v2+json"})

        if r.status_code == 200:
            dcd = r.headers['Docker-Content-Digest']
            mani = json_get("https://%s/v2/%s/manifests/%s" % (self.registry, repo, tag))
            if r.status_code == 200:
                return dcd, mani
            # The error will already have been reported in json_get so don't bother
            # here

        return "", {}


    ## Delete functions

    def delete_manifest(self, repo, digest):
        """Delete the manifest for a given digest in a repo.  The API
        does not support delting by repository:tag only by
        repository:digest.
        """

        if not self.do_delete:
            if self.verbose:
                print("-- (not really) Deleting manifest for %s:%s" % (repo, digest))
            return
    
        if self.verbose:
            print("-- Deleting manifest for %s:%s" % (repo, dig))
        r = requests.delete("https://%s/v2/%s/manifests/%s" % (self.registry, repo, digest))
        if r.status_code != 200 and r.status_code != 202:
            print("--- Error? Result: %s: %s" % (r.status_code, r.text.rstrip()))
            return

        if self.debug:
            print("--- Result: %s: %s" % (r.status_code, r.text.rstrip()))
            




