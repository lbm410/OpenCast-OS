#ifndef OPENCAST_LIFECYCLE_H
#define OPENCAST_LIFECYCLE_H

/* OpenCast ownership model, not a vendor protocol or recovered ABI. */
typedef enum {
    OC_NEW, OC_ADMITTED, OC_REGISTERED, OC_WINDOW, OC_SURFACE, OC_READY, OC_FOCUSED,
    OC_RETURN_PENDING, OC_RETURNED, OC_CLOSED, OC_FAILED
} oc_state;

typedef enum {
    OC_OK, OC_BAD_ARGUMENT, OC_BAD_STATE, OC_BUSY, OC_STALE,
    OC_ADAPTER_FAILURE, OC_TIMEOUT
} oc_result;

typedef enum {
    OC_STAGE_NONE, OC_STAGE_REGISTER, OC_STAGE_WINDOW, OC_STAGE_SURFACE, OC_STAGE_READY,
    OC_STAGE_FOCUS, OC_STAGE_RELEASE, OC_STAGE_RELEASE_WINDOW, OC_STAGE_UNREGISTER, OC_STAGE_RETURN
} oc_stage;

/* Return zero only on success. An acquisition failure must leave no resource.
 * Window acquisition success requires an independently verified service-bound
 * lease, not merely a numeric ID or success reply. Parent resources remain held
 * while a dependent child has unresolved ownership.
 * Operations must return within an adapter-enforced deadline. Queue callbacks
 * until the public call returns; inline/reentrant delivery is rejected.
 * Context and operation code must outlive the instance and queued callbacks. */
typedef struct {
    int (*register_client)(void *, unsigned long);
    int (*acquire_window)(void *, unsigned long);
    int (*acquire_surface)(void *, unsigned long);
    int (*announce_ready)(void *, unsigned long);
    int (*request_focus)(void *, unsigned long, unsigned long);
    int (*release_surface)(void *, unsigned long);
    int (*release_window)(void *, unsigned long);
    int (*unregister_client)(void *, unsigned long);
    /* Independent restoration request; must not implicitly revoke retained
     * parents/children. A positive ack never clears unresolved ownership. */
    int (*request_return)(void *, unsigned long, unsigned long);
} oc_ops;

typedef struct {
    oc_ops ops;
    void *context;
    unsigned long generation;
    unsigned long serial;
    unsigned long focus_token;
    unsigned long return_token;
    oc_state state;
    oc_stage failure_stage;
    unsigned int registered;
    unsigned int window_owned;
    unsigned int surface_owned;
    unsigned int release_attempted;
    unsigned int window_release_attempted;
    unsigned int unregister_attempted;
    unsigned int cleanup_failed;
    unsigned int focus_pending;
    unsigned int busy;
    unsigned int initialized;
} oc_lifecycle;

/* Zero-initialize the struct, then initialize once before use. Reinitialization
 * is rejected; do not clear or reuse an instance while callbacks can exist. Caller
 * supplies a nonzero generation not reused while any old callbacks can exist.
 * This is serialized/event-loop code, not a thread-safe synchronization API. */
oc_result oc_lifecycle_init(oc_lifecycle *, const oc_ops *, void *, unsigned long);
/* Caller has independently established execution admission and framework access.
 * This declaration does not perform or verify admission itself. */
oc_result oc_lifecycle_admit(oc_lifecycle *);
oc_result oc_lifecycle_start(oc_lifecycle *);
oc_result oc_lifecycle_request_focus(oc_lifecycle *);
oc_result oc_lifecycle_close(oc_lifecycle *);
oc_result oc_lifecycle_focus_changed(oc_lifecycle *, unsigned long, unsigned long, int);
oc_result oc_lifecycle_return_ack(oc_lifecycle *, unsigned long, unsigned long, int);
/* Events echo both instance generation and operation token. Focus-loss events
 * use the latest focus token. Timeout applies only to that pending operation;
 * the caller owns timer scheduling and enforces adapter operation deadlines. */
oc_result oc_lifecycle_timeout(oc_lifecycle *, unsigned long, unsigned long);

#endif
