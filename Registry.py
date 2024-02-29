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


def _get_link(headers):
    """Get URL from the Link header if rel is "next" and return it.
    Return none if no next link is found."""

    if 'Link' not in headers:
        return None

    links = headers['Link'].split(',')
    for link in links:
        if 'rel="next"' in link:
            return link.split('<')[1].split('>')[0]

    return None


def _json_get(url, tl_key):
        """Get URL and return the result as a array, supporting
        pagination.

        The fun way to do this is to return a itterable instead of the
        list.  To make it usefull the caller must also do a itterable
        in turn and then they could keep calling each other.

        For non-paginating requests tl_key may be None, and in this
        case the whole document is returned.
        """

        (scheme, _, host, _) = url.split('/', 3)
        rooturl = "%s//%s" % (scheme, host)

        r = requests.get(url)

        if r.status_code == 404:
            return []

        if r.status_code == 400:
            print("Error 400 on %s (%s), making empty return" % (url, r.text.rstrip()))
            return []

        if r.status_code != 200:
            sys.exit("Error: %s getting %s" % (r.status_code, url))

        if tl_key is None:
            return r.json()

        all_data = []

        while l := _get_link(r.headers):
            all_data.extend(r.json()[tl_key])
            url = f"{rooturl}/{l}"
            r = requests.get(url)

            if r.status_code != 200:
                print("Unexpected error in the middle of paginated request: %s getting %s" % (r.status_code, url))
                sys.exit(1)

        data = r.json()

        if tl_key in data and data[tl_key] is not None:
            all_data.extend(data[tl_key])

        return { tl_key: all_data }
    

class Registry:

    """Class to handle the docker registry API.

    Example:

       import Registry
       import sys

       try:
          reg = Registry("registry.example.com", true)
       except:
          sys.exit("Failed to connect to registry or registry is not version 2")

       repos = reg.get_repositories()
       for repo_name in repos:
           print("Repo: %s" % repo_name)

           tags = reg.get_tags(repo_name)

           for tag in tags:
               print("  Tag: %s" % tag)

               digest, manifest = reg.get_manifest(repo_name, tag)
               print("    Digest: %s" % digest)
               print("    Manifest: %s" % manifest)
    """

    def __init__(self, registry, do_delete = False):
        """Initialize the registry object with the registry server
        name.  If you want to actually delete manifests using the
        delete_manifest function you have to specify do_delete=True.

        The registry object has debug and verbose flags which you can
        set directly to possibly get useful information.
        """

        self.registry = registry
        self.do_delete = do_delete
        self.debug = False
        self.verbose = False

        # Check that the registry is there and version 2
        r = requests.get("https://%s/v2" % self.registry)
        if r.status_code == 200: return None

        r.raise_for_status()


    def get_repositories(self):
        """Returns a list of repositories in the registry.  The fun
        way to do this is to return a itterable instead of the list."""

        j = _json_get("https://%s/v2/_catalog" % self.registry, "repositories")
        if "repositories" not in j:
            return []

        return j["repositories"]


    def get_tags(self, repo):

        """Get all tags for a repo"""

        j = _json_get("https://%s/v2/%s/tags/list" % (self.registry, repo), "tags")
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
            mani = _json_get("https://%s/v2/%s/manifests/%s" % (self.registry, repo, tag), None)
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

        Silly example that will delete your whole registry:
        
            reg = Registry("registry.example.com", true)
            repos = reg.get_repositories()
            for repo_name in repos:
                tags = reg.get_tags(repo_name)

                for tag in tags:
                    digest, manifest = reg.get_manifest(repo_name, tag)
                    if digest == "":
                        print("Error getting manifest for %s:%s" % (repo_name, tag))
                        continue

                    reg.delete_manifest(repo_name, digest)
        """

        if not self.do_delete:
            if self.verbose:
                print("-- (not really) Deleting manifest for %s:%s" % (repo, digest))
            return

        if self.verbose:
            print("-- Deleting manifest for %s:%s" % (repo, digest))

        r = requests.delete("https://%s/v2/%s/manifests/%s" % (self.registry, repo, digest))
        if r.status_code != 200 and r.status_code != 202:
            print("--- Error? Result: %s: %s" % (r.status_code, r.text.rstrip()))
            return

        if self.debug:
            print("--- Result: %s: %s" % (r.status_code, r.text.rstrip()))
