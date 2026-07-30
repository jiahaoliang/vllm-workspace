# Mooncake Layerwise Read Lease Expiry Validation Plan

## Objective

Validate the Mooncake ranged-session behavior used by layerwise KVPool without
changing vLLM, vLLM-Ascend, or Mooncake production source:

- a long delay between ranged puts must not be treated as read-lease expiry;
- a get session held past the Master read lease TTL must fail its next ranged
  read with `-707 LEASE_EXPIRED`;
- lease expiry must invalidate only that get session, so a fresh
  `batch_get_session_start` can acquire a new lease while the committed object remains;
- both layer ranges must match their original bytes after recovery.

## Fixture

- one unique Mooncake key;
- one 8 KiB object containing two 4 KiB layer ranges;
- deterministic layer-sensitive bytes in two registered Ascend NPU buffers;
- active Master `default_kv_lease_ttl=30000ms`;
- each deliberate wait is `31500ms`;
- Prefill and Decode vLLM engines remain stopped.

The Master read lease TTL and the PutStart staging timeout are separate. This
test does not lower or otherwise modify either runtime setting.

## Call Sequence And Gates

### P1: slow put control

1. `batch_put_session_start(key, 8192)` must return `[0]`.
2. Put layer 0 at object offset `0`; result must be `[4096]`.
3. Wait at least `31500ms`, longer than the read lease TTL.
4. Put layer 1 at object offset `4096`; result must be `[4096]`.
5. `batch_put_session_end(key)` must return `[0]`.

There is no `batch_get_session_start` before `batch_put_session_end`. No read lease exists
during P1, and the successful layer 1 write is the control proving that the
read TTL is not a PutStart timeout.

### G1: expired get session

1. After commit, call `batch_get_session_start(key)` once; it must return `[0]`.
2. Read layer 0 from offset `0`; result must be `[4096]`.
3. Wait at least `31500ms` without ending or reopening the get session.
4. Read layer 1 from offset `4096` on the same session; it must return
   `[-707]`.

The `-707` ranged result is the hard lease-expiry gate. A missing key,
pre-commit result, HTTP error, exception, timeout, or other negative code does
not satisfy it.

### G2: fresh lease recovery

1. Call a fresh `batch_get_session_start(key)`; it must return `[0]`.
2. Read layer 1 from offset `4096`; result must be `[4096]`.
3. `batch_get_session_end(key)` must return `0`.
4. The complete destination buffer must equal the source buffer byte for byte.

This proves that expiration invalidates the old read session rather than
deleting the committed object.

## Cleanup And Evidence

- force-remove the unique test key;
- unregister both NPU buffers and close the client;
- require all cleanup results to succeed;
- verify Master metrics return to zero allocated bytes;
- archive exact executed sources, structured summary, runtime log, Master
  before/after metrics, Master test-window log, Deployment/Pod state, source
  identities, and `SHA256SUMS` under a new UTC run ID;
- discard superseded lease-test plans, reports, and evidence rather than
  retaining a misleading history.
