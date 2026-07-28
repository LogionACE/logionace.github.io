/*
 * Approved-artifact verification, in the browser.
 *
 * Every public number on this site and every report it hands out has to come
 * from a file whose SHA-256 was recorded when the snapshot was approved. This
 * module is the only way a page reads one.
 *
 * The first thing it does is prove the manifest is the pinned one. It fetches
 * the raw bytes, hashes them, and compares that digest to
 * `ACE_APPROVED_PIN.MANIFEST_SHA256` -- before parsing a field, before reading a
 * state, before trusting a provenance commit. Only then does it parse, re-derive
 * the canonical serialization to confirm the bytes it hashed are the canonical
 * ones, and apply the state / provenance / path / digest rules. Every artifact it
 * later hands out is re-hashed against that manifest.
 *
 * Checking the contents without checking the identity would only prove the
 * document is well-formed. A manifest rebuilt from any tree would be well-formed.
 * The pin is what makes the rest of the checks mean "the approved snapshot", and
 * moving it is a reviewed one-line commit -- see `ace-approved-pin.js` for what
 * that does and does not defend against.
 *
 * It fails closed, always. There is no fallback to the raw leaderboard JSON, no
 * "render what we have", no cached last-known-good: if verification cannot be
 * completed -- bad digest, missing file, unparseable manifest, or a browser
 * with no SubtleCrypto because the page was opened over plain http -- callers
 * get a rejected promise and show `AceArtifacts.UNAVAILABLE_MESSAGE`. A number
 * we cannot prove is worse than no number, because a reader cannot tell the
 * difference.
 *
 * The path and shape rules below deliberately mirror `tools/ace_artifacts.py`
 * line for line. Two implementations of one rule is a risk; two
 * implementations that disagree is the bug this pairing exists to catch, and
 * the test suite asserts they agree.
 */
(function () {
  'use strict';

  var CONFIG = window.ACE_CONFIG;
  var PIN = window.ACE_APPROVED_PIN;
  var MANIFEST_VERSION = 1;
  var APPROVED_STATE = 'approved';
  var REQUIRED_ROLES = ['leaderboard_llm', 'leaderboard_agent'];

  var SHA256_RE = /^[0-9a-f]{64}$/;
  var COMMIT_RE = /^[0-9a-f]{40}$/;
  var SAFE_PATH_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*(?:\/[A-Za-z0-9][A-Za-z0-9._-]*)*$/;

  var UNAVAILABLE_MESSAGE = 'Published reports unavailable.';

  /* Resolved once per page load. A second caller waits on the same check
   * rather than starting a second one; a third does not get a different
   * answer from the second. */
  var manifestPromise = null;

  function VerificationError(message) {
    var error = new Error(message);
    error.name = 'AceVerificationError';
    /* What a page may show a visitor. The detail goes to the console for
     * whoever is debugging, and never into the DOM. */
    error.publicMessage = UNAVAILABLE_MESSAGE;
    return error;
  }

  function isSafeRelativePath(path) {
    if (typeof path !== 'string' || !path || path.length > 300) return false;
    if (path !== path.trim()) return false;
    if (path.indexOf('\\') !== -1) return false;
    if (path.indexOf('..') !== -1) return false;
    if (path.indexOf('//') !== -1) return false;
    if (path.charAt(0) === '/' || path.charAt(0) === '.') return false;
    if (path.indexOf(':') !== -1) return false;
    return SAFE_PATH_RE.test(path);
  }

  function validateManifest(manifest) {
    if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
      throw VerificationError('manifest is not an object');
    }
    if (manifest.manifest_version !== MANIFEST_VERSION) {
      throw VerificationError('unsupported manifest_version');
    }
    /* A draft manifest is not a manifest with a flag set differently -- it is
     * a manifest this site refuses. */
    if (manifest.state !== APPROVED_STATE) {
      throw VerificationError('manifest state is not "approved"');
    }

    var provenance = manifest.provenance;
    if (!provenance || typeof provenance !== 'object') {
      throw VerificationError('manifest has no provenance');
    }
    if (provenance.kind !== 'git_commit') {
      throw VerificationError('provenance is not a git commit');
    }
    if (!COMMIT_RE.test(String(provenance.commit || ''))) {
      throw VerificationError('provenance commit is not a git sha');
    }
    if (provenance.commit !== PIN.PROVENANCE_COMMIT) {
      /* Right shape, wrong snapshot: some other tree's manifest, or this one
       * rebuilt against a commit nobody pinned the site to. */
      throw VerificationError('provenance commit is not the approved snapshot');
    }

    var artifacts = manifest.artifacts;
    if (!Array.isArray(artifacts) || !artifacts.length) {
      throw VerificationError('manifest lists no artifacts');
    }

    var seenPaths = Object.create(null);
    var roles = Object.create(null);
    for (var i = 0; i < artifacts.length; i += 1) {
      var entry = artifacts[i];
      if (!entry || typeof entry !== 'object') {
        throw VerificationError('artifact entry is not an object');
      }
      if (!isSafeRelativePath(entry.path)) {
        throw VerificationError('artifact path is not a safe relative path');
      }
      if (seenPaths[entry.path]) {
        throw VerificationError('artifact listed twice');
      }
      seenPaths[entry.path] = true;
      if (!SHA256_RE.test(String(entry.sha256 || ''))) {
        throw VerificationError('artifact has no usable sha256');
      }
      if (typeof entry.bytes !== 'number' || !isFinite(entry.bytes) ||
          entry.bytes <= 0 || Math.floor(entry.bytes) !== entry.bytes) {
        throw VerificationError('artifact has no usable byte length');
      }
      var role = String(entry.role || '');
      if (!role) throw VerificationError('artifact declares no role');
      if (role.indexOf('leaderboard_') === 0) {
        if (roles[role]) throw VerificationError('two artifacts claim one role');
        roles[role] = entry;
      }
    }
    for (var r = 0; r < REQUIRED_ROLES.length; r += 1) {
      if (!roles[REQUIRED_ROLES[r]]) {
        throw VerificationError('manifest is missing ' + REQUIRED_ROLES[r]);
      }
    }
    return manifest;
  }

  /* The manifest's canonical serialization, byte-for-byte what
   * `tools/ace_artifacts.py::canonical_bytes` writes: keys sorted, two-space
   * indent, non-ASCII left alone, one trailing newline.
   *
   * Re-deriving it here is how the digest keeps meaning one document. Hashing
   * the received bytes alone would let a reformatted manifest be re-pinned and
   * accepted; requiring the received bytes to *be* the canonical bytes means the
   * pin identifies contents, not a formatting accident.
   *
   * Anything the builder cannot emit -- a float, a NaN, an undefined -- throws
   * rather than being serialized on a guess, because a guess that differs from
   * Python's would fail closed later anyway, with a worse error. */
  function canonicalJson(value, indent) {
    var pad = indent || '';
    var inner = pad + '  ';
    var i;
    var parts;

    if (value === null) return 'null';
    var type = typeof value;
    if (type === 'boolean') return value ? 'true' : 'false';
    if (type === 'number') {
      if (!isFinite(value) || Math.floor(value) !== value) {
        throw VerificationError('manifest holds a number we cannot canonicalize');
      }
      return String(value);
    }
    if (type === 'string') return JSON.stringify(value);
    if (Array.isArray(value)) {
      if (!value.length) return '[]';
      parts = [];
      for (i = 0; i < value.length; i += 1) {
        parts.push(inner + canonicalJson(value[i], inner));
      }
      return '[\n' + parts.join(',\n') + '\n' + pad + ']';
    }
    if (type === 'object') {
      var keys = Object.keys(value).sort();
      if (!keys.length) return '{}';
      parts = [];
      for (i = 0; i < keys.length; i += 1) {
        parts.push(
          inner + JSON.stringify(keys[i]) + ': ' + canonicalJson(value[keys[i]], inner)
        );
      }
      return '{\n' + parts.join(',\n') + '\n' + pad + '}';
    }
    throw VerificationError('manifest holds a value we cannot canonicalize');
  }

  function canonicalBytesText(manifest) {
    return canonicalJson(manifest, '') + '\n';
  }

  function loadManifest() {
    if (manifestPromise) return manifestPromise;
    manifestPromise = fetch(CONFIG.APPROVED_MANIFEST_PATH, { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) {
          throw VerificationError('manifest request failed: ' + response.status);
        }
        /* Bytes, not `response.json()`: the digest is over what arrived. */
        return response.arrayBuffer();
      })
      .then(function (buffer) {
        var pinned = PIN && String(PIN.MANIFEST_SHA256 || '');
        if (!SHA256_RE.test(pinned)) {
          throw VerificationError('no approved manifest digest is pinned');
        }
        return digestHex(buffer).then(function (actual) {
          if (actual !== pinned) {
            /* Could be a rebuild nobody approved, a draft copied over the
             * snapshot, a stale cache, or a manifest from somewhere else. From
             * here they are the same thing: not the approved manifest. */
            throw VerificationError('manifest digest does not match the pin');
          }
          return new TextDecoder('utf-8').decode(buffer);
        });
      })
      .then(function (text) {
        var parsed;
        try {
          parsed = JSON.parse(text);
        } catch (error) {
          throw VerificationError('approved manifest is not valid JSON');
        }
        if (canonicalBytesText(parsed) !== text) {
          throw VerificationError('manifest is not in its canonical form');
        }
        return validateManifest(parsed);
      })
      .catch(function (error) {
        /* Do not cache the failure as a value: a transient network problem
         * should be retryable by reloading, and a real one fails again. */
        manifestPromise = null;
        throw error.publicMessage ? error : VerificationError(String(error && error.message));
      });
    return manifestPromise;
  }

  function toHex(buffer) {
    var bytes = new Uint8Array(buffer);
    var out = '';
    for (var i = 0; i < bytes.length; i += 1) {
      out += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return out;
  }

  function digestHex(buffer) {
    /* SubtleCrypto needs a secure context. If there is not one, we cannot
     * verify, so we do not render -- rather than rendering unverified bytes
     * and hoping. */
    if (!window.crypto || !window.crypto.subtle || !window.crypto.subtle.digest) {
      return Promise.reject(
        VerificationError('SubtleCrypto is unavailable; cannot verify artifacts')
      );
    }
    return window.crypto.subtle.digest('SHA-256', buffer).then(toHex);
  }

  function entryFor(manifest, predicate, description) {
    for (var i = 0; i < manifest.artifacts.length; i += 1) {
      if (predicate(manifest.artifacts[i])) return manifest.artifacts[i];
    }
    throw VerificationError('no approved artifact for ' + description);
  }

  /* Fetch one declared artifact and prove it is the one that was approved.
   * Returns the raw bytes, never a URL: a caller that received a URL could
   * hand it to the DOM without the check having happened. */
  function verifiedBytes(manifest, entry) {
    if (!isSafeRelativePath(entry.path)) {
      return Promise.reject(VerificationError('refusing an unsafe artifact path'));
    }
    return fetch(entry.path, { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) {
          throw VerificationError('artifact request failed: ' + response.status);
        }
        return response.arrayBuffer();
      })
      .then(function (buffer) {
        if (buffer.byteLength !== entry.bytes) {
          throw VerificationError('artifact length does not match the manifest');
        }
        return digestHex(buffer).then(function (actual) {
          if (actual !== entry.sha256) {
            throw VerificationError('artifact sha256 does not match the manifest');
          }
          return buffer;
        });
      });
  }

  function leaderboard(role) {
    return loadManifest().then(function (manifest) {
      var entry = entryFor(
        manifest,
        function (candidate) { return candidate.role === role; },
        role
      );
      return verifiedBytes(manifest, entry).then(function (buffer) {
        var text = new TextDecoder('utf-8').decode(buffer);
        var parsed;
        try {
          parsed = JSON.parse(text);
        } catch (error) {
          throw VerificationError('approved leaderboard is not valid JSON');
        }
        return { data: parsed, entry: entry, manifest: manifest };
      });
    });
  }

  /* Report downloads go through the same gate. The bytes are verified first,
   * then handed over as a blob, so what lands in the visitor's downloads
   * folder is provably the approved file and not whatever the path happens to
   * serve today. */
  function downloadReport(relativePath, suggestedName) {
    return loadManifest().then(function (manifest) {
      var entry = entryFor(
        manifest,
        function (candidate) {
          return candidate.role === 'report' && candidate.path === relativePath;
        },
        relativePath
      );
      return verifiedBytes(manifest, entry).then(function (buffer) {
        var blob = new Blob([buffer], { type: 'application/pdf' });
        var url = URL.createObjectURL(blob);
        var anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = suggestedName || relativePath.split('/').pop();
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        /* Given back late enough for the download to have started, and always,
         * so a page that offers several reports does not leak a blob each. */
        window.setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
        return entry;
      });
    });
  }

  function hasReport(manifest, relativePath) {
    for (var i = 0; i < manifest.artifacts.length; i += 1) {
      var entry = manifest.artifacts[i];
      if (entry.role === 'report' && entry.path === relativePath) return true;
    }
    return false;
  }

  /*
   * The public figures, derived from the verified leaderboard every time they
   * are shown. Storing them -- in the manifest, in the HTML, anywhere -- is how
   * a homepage ends up claiming 47 critical failures about a file that records
   * 56.
   */
  function publicCounts(leaderboardData) {
    var models = (leaderboardData && leaderboardData.models) || [];
    var scored = [];
    var domains = Object.create(null);
    var domainCount = 0;
    var critical = 0;
    var ready = 0;
    for (var i = 0; i < models.length; i += 1) {
      var model = models[i];
      if (!model || typeof model !== 'object' || !model.bare) continue;
      scored.push(model);
      critical += Number(model.bare.critical_exception_count || 0);
      if (String(model.bare.verdict || '') === 'ACE Ready') ready += 1;
      var modelDomains = model.bare.domains || {};
      for (var key in modelDomains) {
        if (Object.prototype.hasOwnProperty.call(modelDomains, key) && !domains[key]) {
          domains[key] = true;
          domainCount += 1;
        }
      }
    }
    return {
      systems_evaluated: scored.length,
      critical_failures: critical,
      ace_ready: ready,
      trust_domains: domainCount
    };
  }

  window.AceArtifacts = {
    UNAVAILABLE_MESSAGE: UNAVAILABLE_MESSAGE,
    isSafeRelativePath: isSafeRelativePath,
    canonicalJson: canonicalJson,
    loadManifest: loadManifest,
    leaderboard: leaderboard,
    downloadReport: downloadReport,
    hasReport: hasReport,
    publicCounts: publicCounts
  };
})();
